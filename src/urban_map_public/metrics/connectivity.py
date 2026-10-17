from __future__ import annotations

import networkx as nx
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from .traffic import physical_undirected_graph


def _empty_metrics() -> dict[str, float | int]:
    return {
        "node_count": 0,
        "edge_count": 0,
        "average_node_degree": 0.0,
        "dead_end_count": 0,
        "dead_end_ratio": 0.0,
        "connected_component_count": 0,
    }


def calculate_kh01_connectivity_metrics(
    graph: nx.MultiDiGraph | None,
    study_area: BaseGeometry | None = None,
) -> dict[str, float | int]:
    """Calculate physical network topology from an existing graph.

    When ``study_area`` is provided, topology is calculated from the induced
    graph whose nodes are covered by that metric geometry. Query and display
    extents therefore cannot expand the reported research scope.
    Edge count and average degree use a physical undirected graph so reverse
    directions of the same road do not count twice. A dead end is a node with degree one in the induced physical graph.
    """

    if graph is None or graph.number_of_nodes() == 0:
        return _empty_metrics()

    scoped_graph = graph
    if study_area is not None:
        included_nodes = []
        for node, data in graph.nodes(data=True):
            try:
                point = Point(float(data["x"]), float(data["y"]))
            except (KeyError, TypeError, ValueError):
                continue
            if study_area.covers(point):
                included_nodes.append(node)
        scoped_graph = graph.subgraph(included_nodes).copy()
        if scoped_graph.number_of_nodes() == 0:
            return _empty_metrics()

    physical_graph = physical_undirected_graph(scoped_graph)
    node_count = physical_graph.number_of_nodes()
    edge_count = physical_graph.number_of_edges()
    degree_total = sum(
        degree
        for _, degree in physical_graph.degree()
    )
    dead_end_count = sum(
        degree == 1
        for _, degree in physical_graph.degree()
    )

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "average_node_degree": degree_total / node_count,
        "dead_end_count": dead_end_count,
        "dead_end_ratio": dead_end_count / node_count,
        "connected_component_count": (
            nx.number_connected_components(physical_graph)
        ),
    }

