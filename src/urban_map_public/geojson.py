"""Canonicalize field-survey GeoJSON without application storage dependencies."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

MAX_FEATURES = 10_000
MAX_VERTICES = 100_000
MAX_PROPERTIES_BYTES = 64 * 1024


class GeoJSONValidationError(ValueError):
    """Raised when a survey FeatureCollection is malformed or too large."""


def _position(value: object) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) not in (2, 3):
        raise GeoJSONValidationError(
            "A position must contain longitude, latitude, and optional altitude."
        )

    coordinates: list[float] = []
    for coordinate in value:
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
            raise GeoJSONValidationError("Position coordinates must be numeric.")
        numeric = float(coordinate)
        if not math.isfinite(numeric):
            raise GeoJSONValidationError("Position coordinates must be finite.")
        coordinates.append(numeric)

    longitude, latitude = coordinates[:2]
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise GeoJSONValidationError("Longitude or latitude is outside its valid range.")
    return coordinates


def _line(
    value: object,
    *,
    minimum: int,
    vertex_count: list[int],
) -> list[list[float]]:
    if not isinstance(value, (list, tuple)) or len(value) < minimum:
        raise GeoJSONValidationError("A path has too few vertices.")
    vertex_count[0] += len(value)
    if vertex_count[0] > MAX_VERTICES:
        raise GeoJSONValidationError("The FeatureCollection exceeds the vertex limit.")
    return [_position(point) for point in value]


def _geometry(value: object, vertex_count: list[int]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeoJSONValidationError("Each survey feature must have a geometry object.")

    geometry_type = value.get("type")
    coordinates = value.get("coordinates")

    if geometry_type == "Point":
        normalized: Any = _position(coordinates)
        vertex_count[0] += 1
    elif geometry_type == "LineString":
        normalized = _line(coordinates, minimum=2, vertex_count=vertex_count)
    elif geometry_type == "Polygon":
        if not isinstance(coordinates, (list, tuple)) or not coordinates:
            raise GeoJSONValidationError("A polygon must contain at least one linear ring.")
        rings: list[list[list[float]]] = []
        for raw_ring in coordinates:
            ring = _line(raw_ring, minimum=3, vertex_count=vertex_count)
            if ring[0] != ring[-1]:
                ring.append(list(ring[0]))
                vertex_count[0] += 1
            if len(ring) < 4:
                raise GeoJSONValidationError(
                    "A polygon ring must contain at least four positions."
                )
            if vertex_count[0] > MAX_VERTICES:
                raise GeoJSONValidationError("The FeatureCollection exceeds the vertex limit.")
            rings.append(ring)
        normalized = rings
    else:
        raise GeoJSONValidationError(
            "Only Point, LineString, and Polygon survey geometries are supported."
        )

    if vertex_count[0] > MAX_VERTICES:
        raise GeoJSONValidationError("The FeatureCollection exceeds the vertex limit.")
    return {"type": geometry_type, "coordinates": normalized}


def _feature(value: object, vertex_count: list[int]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("type") != "Feature":
        raise GeoJSONValidationError("Every collection item must be a GeoJSON Feature.")

    geometry = _geometry(value.get("geometry"), vertex_count)
    raw_properties = value.get("properties")
    if raw_properties is None:
        properties: dict[str, Any] = {}
    elif isinstance(raw_properties, Mapping):
        try:
            encoded = json.dumps(
                dict(raw_properties),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            if len(encoded.encode("utf-8")) > MAX_PROPERTIES_BYTES:
                raise GeoJSONValidationError("Feature properties exceed the size limit.")
            properties = json.loads(encoded)
        except (TypeError, ValueError, UnicodeEncodeError) as error:
            if isinstance(error, GeoJSONValidationError):
                raise
            raise GeoJSONValidationError(
                "Feature properties must contain valid JSON values."
            ) from error
    else:
        raise GeoJSONValidationError("Feature properties must be an object or null.")

    normalized: dict[str, Any] = {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }

    if "id" in value:
        feature_id = value["id"]
        if isinstance(feature_id, bool) or not isinstance(feature_id, (str, int)):
            raise GeoJSONValidationError("Feature id must be a string or integer.")
        if isinstance(feature_id, str) and (
            not feature_id.strip() or len(feature_id) > 128
        ):
            raise GeoJSONValidationError("Feature id is empty or too long.")
        normalized["id"] = feature_id

    return normalized


def normalize_feature_collection(payload: object) -> dict[str, Any]:
    """Validate and return a canonical GeoJSON FeatureCollection.

    The result keeps feature IDs and properties, normalizes coordinates to finite
    numbers, closes polygon rings when needed, and drops collection-level fields.
    It does not store, upload, or anonymize the supplied data.
    """
    if not isinstance(payload, Mapping) or payload.get("type") != "FeatureCollection":
        raise GeoJSONValidationError("A GeoJSON FeatureCollection is required.")

    raw_features = payload.get("features")
    if not isinstance(raw_features, Sequence) or isinstance(raw_features, (str, bytes)):
        raise GeoJSONValidationError("FeatureCollection features must be an array.")
    if len(raw_features) > MAX_FEATURES:
        raise GeoJSONValidationError("The FeatureCollection exceeds the feature limit.")

    vertex_count = [0]
    features = [_feature(item, vertex_count) for item in raw_features]
    return {"type": "FeatureCollection", "features": features}
