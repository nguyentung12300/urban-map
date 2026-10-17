from __future__ import annotations

import math
from typing import Any

import geopandas as gpd
from pyproj import CRS
from shapely import make_valid
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


def _repair_geometry(
    geometry: BaseGeometry | None,
) -> BaseGeometry | None:
    if geometry is None or geometry.is_empty:
        return None

    try:
        repaired = geometry if geometry.is_valid else make_valid(geometry)
    except Exception:
        try:
            repaired = geometry.buffer(0)
        except Exception:
            return None

    if repaired is None or repaired.is_empty:
        return None

    return repaired


def _clip_features(
    gdf: gpd.GeoDataFrame | None,
    *,
    study_area: BaseGeometry,
    study_crs: CRS,
) -> list[BaseGeometry]:
    if gdf is None or gdf.empty:
        return []

    if gdf.crs is None:
        raise ValueError(
            "GeoDataFrame must define a CRS before metrics are calculated."
        )

    projected = (
        gdf
        if CRS.from_user_input(gdf.crs) == study_crs
        else gdf.to_crs(study_crs)
    )
    clipped: list[BaseGeometry] = []

    for geometry in projected.geometry:
        repaired = _repair_geometry(geometry)
        if repaired is None:
            continue

        try:
            intersection = repaired.intersection(study_area)
        except Exception:
            repaired = _repair_geometry(repaired.buffer(0))
            if repaired is None:
                continue

            try:
                intersection = repaired.intersection(study_area)
            except Exception:
                continue

        intersection = _repair_geometry(intersection)
        if intersection is not None:
            clipped.append(intersection)

    return clipped


def _polygon_parts(
    geometry: BaseGeometry,
) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry]

    if isinstance(geometry, MultiPolygon):
        return [
            polygon
            for polygon in geometry.geoms
            if not polygon.is_empty
        ]

    parts: list[Polygon] = []
    children = getattr(geometry, "geoms", ())

    for child in children:
        parts.extend(_polygon_parts(child))

    return parts


def _union_area(
    geometries: list[BaseGeometry],
) -> float:
    polygons = [
        polygon
        for geometry in geometries
        for polygon in _polygon_parts(geometry)
    ]

    if not polygons:
        return 0.0

    return max(0.0, float(unary_union(polygons).area))


def calculate_st01_blue_green_metrics(
    *,
    study_area: BaseGeometry,
    study_crs: Any,
    green_gdf: gpd.GeoDataFrame | None,
    water_gdf: gpd.GeoDataFrame | None,
) -> dict[str, object]:
    """Calculate ST01 coverage metrics in a projected CRS.

    Polygon areas are clipped to the study area and dissolved per layer so
    overlapping OSM features are not counted more than once. Feature counts
    represent valid source rows that intersect the study area; linear water
    features count as features but contribute zero polygon area.
    """

    target_crs = CRS.from_user_input(study_crs)
    horizontal_axes = target_crs.axis_info[:2]
    if (
        not target_crs.is_projected
        or len(horizontal_axes) < 2
        or any(
            axis.unit_conversion_factor is None
            or not math.isclose(
                float(axis.unit_conversion_factor),
                1.0,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
            for axis in horizontal_axes
        )
    ):
        raise ValueError("ST01 area metrics require a projected CRS in metres.")

    repaired_study_area = _repair_geometry(study_area)
    if repaired_study_area is None:
        raise ValueError("ST01 study area must contain a valid geometry.")

    study_area_m2 = float(repaired_study_area.area)
    if study_area_m2 <= 0:
        raise ValueError("ST01 study area must have a positive area.")

    green_features = _clip_features(
        green_gdf,
        study_area=repaired_study_area,
        study_crs=target_crs,
    )
    water_features = _clip_features(
        water_gdf,
        study_area=repaired_study_area,
        study_crs=target_crs,
    )

    green_area_m2 = min(study_area_m2, _union_area(green_features))
    water_area_m2 = min(study_area_m2, _union_area(water_features))

    return {
        "map_id": "ST01",
        "metrics": {
            "study_area_m2": study_area_m2,
            "green_area_m2": green_area_m2,
            "water_area_m2": water_area_m2,
            "green_percent": green_area_m2 / study_area_m2 * 100,
            "water_percent": water_area_m2 / study_area_m2 * 100,
            "green_feature_count": len(green_features),
            "water_feature_count": len(water_features),
        },
    }

