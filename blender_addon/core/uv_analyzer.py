"""
BlenderNanoBanana - UV Island Analyzer

Detects UV islands and their properties via Rust backend.
Falls back to Blender's built-in UV data if Rust is unavailable.
"""

import os
from typing import Optional, List, Dict, Any

from ..utils.mesh_utils import get_active_mesh_data
from ..utils.geometry import uv_bounding_box, uv_area, uv_center
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "UVAnalyzer"


def analyze_uv_islands(context) -> Optional[Dict[str, Any]]:
    """
    Detect UV islands for the active mesh.

    Returns:
        {
            "islands": [
                {
                    "id": str,
                    "area": float,
                    "center": [u, v],
                    "bounds": {"min": [u,v], "max": [u,v]},
                    "face_count": int,
                    "symmetrical_to": str | None,
                }
            ],
            "total_uv_area": float,
            "island_count": int,
        }
        or None if no mesh / UV data.
    """
    mesh_data = get_active_mesh_data(context)
    if mesh_data is None or not mesh_data.get("uv_coords"):
        log_debug("No UV data found on active mesh.", _MODULE)
        return None

    # Try Rust
    try:
        from .rust_bridge import get_rust_bridge
        bridge = get_rust_bridge()
        if bridge.is_running():
            result = bridge.analyze_uv_islands(
                uv_coordinates=mesh_data["uv_coords"],
                seams=mesh_data["seams"],
            )
            log_debug(f"Rust UV analysis: {result.get('island_count', '?')} islands", _MODULE)
            return result
    except Exception as e:
        log_error(f"Rust UV analysis failed, using fallback: {e}", _MODULE, e)

    # Python fallback: treat entire UV map as one island
    return _python_uv_fallback(mesh_data)


def _python_uv_fallback(mesh_data: dict) -> dict:
    """Simple Python fallback: one island per mesh."""
    uv_coords = mesh_data["uv_coords"]
    if not uv_coords:
        return {"islands": [], "total_uv_area": 0.0, "island_count": 0}

    min_u, min_v, max_u, max_v = uv_bounding_box(uv_coords)
    center = uv_center(uv_coords)
    island_id = f"uv_{mesh_data.get('object_name', 'obj')}_001"

    island = {
        "id": island_id,
        "area": (max_u - min_u) * (max_v - min_v),
        "center": list(center),
        "bounds": {"min": [min_u, min_v], "max": [max_u, max_v]},
        "face_count": mesh_data["face_count"],
        "symmetrical_to": None,
    }

    return {
        "islands": [island],
        "total_uv_area": island["area"],
        "island_count": 1,
    }


def get_island_for_face(context, face_index: int, uv_analysis: dict) -> Optional[str]:
    """Return the island ID containing the given face index, or None."""
    for island in uv_analysis.get("islands", []):
        if face_index in island.get("face_indices", []):
            return island["id"]
    return None
