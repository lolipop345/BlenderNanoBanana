"""
BlenderNanoBanana - 3D Model Analyzer (pure Python)
"""

from typing import Optional, Dict, Any

from ..utils.mesh_utils import get_active_mesh_data
from ..utils.geometry import mesh_bounding_box, check_symmetry_x
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "ModelAnalyzer"


def analyze_active_mesh(context) -> Optional[Dict[str, Any]]:
    """
    Analyze the active mesh object.

    Returns:
        {
            "vertex_count": int,
            "face_count": int,
            "has_symmetry": bool,
            "symmetry_axis": str | None,
            "bounds": {"min": [...], "max": [...]},
            "is_manifold": bool,
            "object_name": str,
            "seam_count": int,
            "uv_islands_estimated": int,
        }
        or None if no active mesh.
    """
    mesh_data = get_active_mesh_data(context)
    if mesh_data is None:
        log_debug("No active mesh found.", _MODULE)
        return None

    log_debug(f"Analyzing mesh '{mesh_data['object_name']}' "
              f"({mesh_data['vertex_count']} verts, {mesh_data['face_count']} faces)", _MODULE)

    return _python_analyze(mesh_data)


def _python_analyze(mesh_data: dict) -> dict:
    vertices = mesh_data["vertices"]
    faces = mesh_data["faces"]
    seams = mesh_data["seams"]

    bounds = mesh_bounding_box(vertices)
    has_sym = check_symmetry_x(vertices)

    uv_islands_est = max(1, len(seams) // 4 + 1)

    edge_face_count: Dict[tuple, int] = {}
    for face in faces:
        n = len(face)
        for i in range(n):
            edge = tuple(sorted([face[i], face[(i + 1) % n]]))
            edge_face_count[edge] = edge_face_count.get(edge, 0) + 1
    is_manifold = all(v == 2 for v in edge_face_count.values())

    return {
        "vertex_count": mesh_data["vertex_count"],
        "face_count": mesh_data["face_count"],
        "has_symmetry": has_sym,
        "symmetry_axis": "X" if has_sym else None,
        "bounds": bounds,
        "is_manifold": is_manifold,
        "object_name": mesh_data["object_name"],
        "seam_count": len(seams),
        "uv_islands_estimated": uv_islands_est,
    }
