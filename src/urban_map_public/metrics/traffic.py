from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import networkx as nx
import osmnx as ox
from pyproj import CRS
from shapely import make_valid
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry


RoadClassifier = Callable[[Any], str]


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


def _fallback_osmid(
    u: Any,
    v: Any,
    key: Any,
) -> str:
    endpoints = sorted((str(u), str(v)))
    return (
        "__missing_osmid__:"
        f"{endpoints[0]}:{endpoints[1]}:{key}"
    )


def physical_undirected_graph(
    graph: nx.MultiDiGraph,
) -> nx.MultiGraph:
    """Return one edge per physical street segment.

    OSMnx's converter removes reverse-direction duplicates only when their
    OSM IDs and geometries match. True parallel streets remain separate.
    The input graph is never mutated.
    """

    prepared = graph.copy()

    for u, v, key, data in prepared.edges(
        keys=True,
        data=True,
    ):
        data.setdefault(
            "osmid",
            _fallback_osmid(u, v, key),
        )

    return ox.convert.to_undirected(prepared)


def physical_street_counts(
    graph: nx.MultiDiGraph,
) -> dict[Any, int]:
    """Return OSMnx physical street counts for every graph node."""

    calculated = ox.stats.count_streets_per_node(graph)
    counts: dict[Any, int] = {}

    for node, data in graph.nodes(data=True):
        value = data.get("street_count")

        try:
            counts[node] = int(value)
        except (TypeError, ValueError, OverflowError):
            counts[node] = int(calculated.get(node, 0))

    return counts


def _edge_geometry(
    graph: nx.MultiGraph,
    u: Any,
    v: Any,
    data: dict[str, Any],
) -> BaseGeometry | None:
    geometry = data.get("geometry")

    if geometry is None:
        try:
            geometry = LineString(
                [
                    (
                        float(graph.nodes[u]["x"]),
                        float(graph.nodes[u]["y"]),
                    ),
                    (
                        float(graph.nodes[v]["x"]),
                        float(graph.nodes[v]["y"]),
                    ),
                ]
            )
        except (KeyError, TypeError, ValueError):
            return None

    return _repair_geometry(geometry)


def _empty_metrics() -> dict[str, float | int]:
    return {
        "total_road_length_km": 0.0,
        "road_density_km_per_km2": 0.0,
        "primary_road_length_km": 0.0,
        "secondary_road_length_km": 0.0,
        "local_road_length_km": 0.0,
        "intersection_count": 0,
        "intersection_density_per_km2": 0.0,
    }


def calculate_gt01_traffic_metrics(
    *,
    graph: nx.MultiDiGraph | None,
    study_area: BaseGeometry,
    road_classifier: RoadClassifier,
) -> dict[str, float | int]:
    """Calculate GT01 metrics without downloading or mutating a graph.

    Road length is the sum of projected edge-geometry lengths after clipping
    them to ``study_area``. Bidirectional mirror edges are collapsed with
    OSMnx's physical-undirected conversion before summing. Intersections are
    nodes covered by the study area with at least three incident physical
    streets according to OSMnx's ``street_count`` semantics.
    """

    repaired_study_area = _repair_geometry(study_area)
    if repaired_study_area is None:
        raise ValueError("GT01 study area must contain valid geometry.")

    study_area_m2 = float(repaired_study_area.area)
    if study_area_m2 <= 0:
        raise ValueError("GT01 study area must have a positive area.")

    if graph is None or graph.number_of_nodes() == 0:
        return _empty_metrics()

    graph_crs = graph.graph.get("crs")
    if graph_crs is None:
        raise ValueError("GT01 metrics require a projected CRS in metres.")
    parsed_graph_crs = CRS.from_user_input(graph_crs)
    horizontal_axes = parsed_graph_crs.axis_info[:2]
    if (
        not parsed_graph_crs.is_projected
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
        raise ValueError("GT01 metrics require a projected CRS in metres.")

    physical_graph = physical_undirected_graph(graph)
    length_by_class_m = {
        "major": 0.0,
        "secondary": 0.0,
        "local": 0.0,
    }
    total_length_m = 0.0

    for u, v, data in physical_graph.edges(data=True):
        geometry = _edge_geometry(
            physical_graph,
            u,
            v,
            data,
        )
        if geometry is None:
            continue

        try:
            clipped = geometry.intersection(
                repaired_study_area
            )
        except Exception:
            continue

        clipped = _repair_geometry(clipped)
        if clipped is None:
            continue

        length_m = max(0.0, float(clipped.length))
        if length_m == 0:
            continue

        road_class = road_classifier(data.get("highway"))
        if road_class not in length_by_class_m:
            road_class = "local"

        total_length_m += length_m
        length_by_class_m[road_class] += length_m

    street_counts = physical_street_counts(graph)
    intersection_count = 0

    for node, data in graph.nodes(data=True):
        try:
            point = Point(
                float(data["x"]),
                float(data["y"]),
            )
        except (KeyError, TypeError, ValueError):
            continue

        if (
            repaired_study_area.covers(point)
            and street_counts.get(node, 0) >= 3
        ):
            intersection_count += 1

    area_km2 = study_area_m2 / 1_000_000
    total_length_km = total_length_m / 1000

    return {
        "total_road_length_km": total_length_km,
        "road_density_km_per_km2": (
            total_length_km / area_km2
        ),
        "primary_road_length_km": (
            length_by_class_m["major"] / 1000
        ),
        "secondary_road_length_km": (
            length_by_class_m["secondary"] / 1000
        ),
        "local_road_length_km": (
            length_by_class_m["local"] / 1000
        ),
        "intersection_count": intersection_count,
        "intersection_density_per_km2": (
            intersection_count / area_km2
        ),
    }

