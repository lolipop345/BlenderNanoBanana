"""
BlenderNanoBanana - UV Island Analyzer

Detects UV islands via bmesh flood-fill (seam-boundary connected components).
Each group of faces connected by non-seam edges is one UV island.
"""

import bmesh
from typing import Optional, Dict, Any

from ..utils.logging import log_info, log_debug, log_error

_MODULE = "UVAnalyzer"


def analyze_uv_islands(context) -> Optional[Dict[str, Any]]:
    """
    Detect UV islands for the active mesh using bmesh flood-fill.

    Two faces belong to the same island if they share an edge that is NOT a seam.

    Returns:
        {
            "islands": [
                {
                    "id": str,
                    "area": float,
                    "center": [u, v],
                    "bounds": {"min": [u,v], "max": [u,v]},
                    "face_count": int,
                    "face_indices": [int, ...],
                    "symmetrical_to": None,
                }
            ],
            "total_uv_area": float,
            "island_count": int,
        }
        or None if no mesh / UV data.
    """
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return None

    return _detect_islands_bmesh(obj)


def _detect_islands_bmesh(obj) -> Dict[str, Any]:
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        bm.free()
        log_debug("No active UV layer on mesh.", _MODULE)
        return {"islands": [], "total_uv_area": 0.0, "island_count": 0}

    visited = set()
    islands = []

    for start_face in bm.faces:
        if start_face.index in visited:
            continue

        # BFS: expand through non-seam edges
        island_indices = []
        queue = [start_face]
        visited.add(start_face.index)

        while queue:
            face = queue.pop()
            island_indices.append(face.index)
            for edge in face.edges:
                if edge.seam:
                    continue
                for linked_face in edge.link_faces:
                    if linked_face.index not in visited:
                        visited.add(linked_face.index)
                        queue.append(linked_face)

        # Compute UV bounding box for this island
        uvs = []
        face_polygons = []
        for fi in island_indices:
            poly = []
            for loop in bm.faces[fi].loops:
                uv_val = loop[uv_layer].uv
                uvs.append(uv_val.copy())
                poly.append((uv_val.x, uv_val.y))
            face_polygons.append(poly)

        if uvs:
            min_u = min(u.x for u in uvs)
            max_u = max(u.x for u in uvs)
            min_v = min(u.y for u in uvs)
            max_v = max(u.y for u in uvs)
            area = (max_u - min_u) * (max_v - min_v)
            center = [(min_u + max_u) / 2, (min_v + max_v) / 2]
        else:
            min_u = min_v = max_u = max_v = 0.0
            area = 0.0
            center = [0.0, 0.0]

        islands.append({
            "id": f"uv_{len(islands) + 1:03d}",
            "area": area,
            "center": center,
            "bounds": {"min": [min_u, min_v], "max": [max_u, max_v]},
            "face_count": len(island_indices),
            "face_indices": island_indices,
            "face_polygons": face_polygons,
            "symmetrical_to": None,
        })

    bm.free()

    total_area = sum(i["area"] for i in islands)
    log_info(f"Detected {len(islands)} UV islands via bmesh flood-fill.", _MODULE)
    return {
        "islands": islands,
        "total_uv_area": total_area,
        "island_count": len(islands),
    }


def get_island_for_face(context, face_index: int, uv_analysis: dict) -> Optional[str]:
    """Return the island ID containing the given face index, or None."""
    for island in uv_analysis.get("islands", []):
        if face_index in island.get("face_indices", []):
            return island["id"]
    return None
