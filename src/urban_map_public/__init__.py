"""Privacy-conscious, standalone helpers for Urban Map integrations."""

from .depthmapx import DepthmapXError, DepthmapXResult, run_depthmapx
from .geojson import GeoJSONValidationError, normalize_feature_collection

__all__ = [
    "DepthmapXError",
    "DepthmapXResult",
    "GeoJSONValidationError",
    "normalize_feature_collection",
    "run_depthmapx",
]

__version__ = "0.1.0"
