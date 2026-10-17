"""Optional GIS analytics with lazy imports so schema-only use stays lightweight."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "calculate_gt01_traffic_metrics": ".traffic",
    "calculate_kh01_connectivity_metrics": ".connectivity",
    "calculate_st01_blue_green_metrics": ".blue_green",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a GIS implementation only when its public function is requested."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module_name, __name__), name)
