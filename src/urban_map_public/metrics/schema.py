"""Privacy-minimized, versioned metric payload contract.

Project names, study coordinates, entrance details, and source records are
intentionally outside this public metric schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    model_validator,
)

SCHEMA_VERSION = "1.1"
MapId = Literal["ST01", "LH01", "GT01", "KH01"]
MapStatus = Literal["success", "partial", "failed", "not_available"]
MAP_IDS: tuple[MapId, ...] = ("ST01", "LH01", "GT01", "KH01")

CONNECTIVITY_METRIC_UNITS = {
    "node_count": "count",
    "edge_count": "count",
    "average_node_degree": "degree",
    "dead_end_count": "count",
    "dead_end_ratio": "ratio",
    "connected_component_count": "count",
}

METRIC_UNITS: dict[MapId, dict[str, str]] = {
    "ST01": {
        "study_area_m2": "m²",
        "green_area_m2": "m²",
        "water_area_m2": "m²",
        "green_percent": "%",
        "water_percent": "%",
        "green_feature_count": "count",
        "water_feature_count": "count",
    },
    "LH01": {
        "poi_total": "count",
        "poi_density_per_km2": "count/km²",
        "count_by_category": "count",
        "nearest_education_m": "m",
        "nearest_healthcare_m": "m",
        "nearest_public_space_m": "m",
        "nearest_transport_m": "m",
        "nearest_commercial_m": "m",
    },
    "GT01": {
        "total_road_length_km": "km",
        "road_density_km_per_km2": "km/km²",
        "primary_road_length_km": "km",
        "secondary_road_length_km": "km",
        "local_road_length_km": "km",
        "intersection_count": "count",
        "intersection_density_per_km2": "count/km²",
        **CONNECTIVITY_METRIC_UNITS,
    },
    # KH01 currently represents sun/wind visualization and has no numeric
    # metrics in schema 1.1.
    "KH01": {},
}

MetricPayload = StrictInt | StrictFloat | dict[str, StrictInt] | None


class MetricValue(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    value: MetricPayload
    unit: str = Field(min_length=1)


class MapMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MapStatus = "not_available"
    metrics: dict[str, MetricValue] = Field(default_factory=dict)
    error: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "MapMetrics":
        if self.status == "success" and self.error is not None:
            raise ValueError("Successful map metrics cannot have an error.")
        if self.status == "failed" and (not self.error or self.metrics):
            raise ValueError("Failed map metrics require an error and no metrics.")
        if self.status == "partial" and (not self.error or not self.metrics):
            raise ValueError("Partial map metrics require an error and some metrics.")
        if self.status == "not_available" and (self.error is not None or self.metrics):
            raise ValueError("Unavailable map metrics cannot contain data or an error.")
        return self


class MetricsDocument(BaseModel):
    """Canonical map metrics without project metadata or raw spatial inputs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.1"] = SCHEMA_VERSION
    maps: dict[MapId, MapMetrics]

    @model_validator(mode="after")
    def validate_maps_and_units(self) -> "MetricsDocument":
        if set(self.maps) != set(MAP_IDS):
            raise ValueError("A canonical document requires ST01, LH01, GT01, and KH01.")
        for map_id, map_data in self.maps.items():
            expected_units = METRIC_UNITS[map_id]
            for metric_name, metric_value in map_data.metrics.items():
                expected_unit = expected_units.get(metric_name)
                if expected_unit is None:
                    raise ValueError(f"Unknown {map_id} metric: {metric_name}.")
                if metric_value.unit != expected_unit:
                    raise ValueError(
                        f"{map_id}.{metric_name} must use unit {expected_unit!r}."
                    )
        return self
