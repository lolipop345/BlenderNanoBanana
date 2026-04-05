"""
BlenderNanoBanana - UV Island Analyzer

Detects UV islands via bmesh flood-fill (seam-boundary connected components).
Each group of faces connected by non-seam edges is one UV island.
"""

import math
import bmesh
from typing import Optional, Dict, Any, List, Tuple

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
            center = [
                sum(u.x for u in uvs) / len(uvs),
                sum(u.y for u in uvs) / len(uvs),
            ]
            # Bounding-box center: reliable visual center for all island shapes,
            # including L-shaped or non-convex islands. Derived from Blender UV data.
            bbox_center = [
                (min_u + max_u) / 2.0,
                (min_v + max_v) / 2.0,
            ]
        else:
            min_u = min_v = max_u = max_v = 0.0
            area = 0.0
            center = [0.0, 0.0]
            bbox_center = [0.0, 0.0]

        is_flipped   = _compute_is_flipped(face_polygons)
        label_center = _find_label_center(face_polygons, center)
        
        # Use 3D-aware Z-gradient to compute actual rotation
        rotation_deg = _compute_rotation_from_3d(bm, island_indices, uv_layer)
        if rotation_deg is None:
            # Fallback
            rotation_deg = _compute_rotation_deg_pca(uvs)

        islands.append({
            "id": f"uv_{len(islands) + 1:03d}",
            "area": area,
            "center": center,
            "bbox_center": bbox_center,
            "label_center": label_center,
            "bounds": {"min": [min_u, min_v], "max": [max_u, max_v]},
            "face_count": len(island_indices),
            "face_indices": island_indices,
            "face_polygons": face_polygons,
            "rotation_deg": rotation_deg,
            "is_flipped": is_flipped,
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


def _compute_rotation_from_3d(bm, island_indices, uv_layer) -> Optional[float]:
    """
    Compute rotation of the UV island by analyzing how the local 3D axes map to UV space.
    We prefer Z-axis as 'UP'. If the island is perfectly flat along Z, we fallback to Y, then X.
    Returns rotation in degrees (-180 to 180).
    """
    sum_du_z, sum_dv_z = 0.0, 0.0
    sum_du_y, sum_dv_y = 0.0, 0.0
    sum_du_x, sum_dv_x = 0.0, 0.0
    
    for fi in island_indices:
        face = bm.faces[fi]
        if len(face.loops) < 3:
            continue
            
        l0, l1, l2 = face.loops[0], face.loops[1], face.loops[2]
        u0, v0 = l0[uv_layer].uv.x, l0[uv_layer].uv.y
        u1, v1 = l1[uv_layer].uv.x, l1[uv_layer].uv.y
        u2, v2 = l2[uv_layer].uv.x, l2[uv_layer].uv.y
        
        du1 = u1 - u0
        dv1 = v1 - v0
        du2 = u2 - u0
        dv2 = v2 - v0
        
        det = du1 * dv2 - dv1 * du2
        if abs(det) < 1e-8:
            continue
            
        area = 0.5 * abs(det)
        
        def calc_grad(val0, val1, val2):
            d1 = val1 - val0
            d2 = val2 - val0
            g_u = (dv2 * d1 - dv1 * d2) / det
            g_v = (-du2 * d1 + du1 * d2) / det
            return g_u, g_v

        pz0, pz1, pz2 = l0.vert.co.z, l1.vert.co.z, l2.vert.co.z
        gu_z, gv_z = calc_grad(pz0, pz1, pz2)
        sum_du_z += gu_z * area
        sum_dv_z += gv_z * area
        
        py0, py1, py2 = l0.vert.co.y, l1.vert.co.y, l2.vert.co.y
        gu_y, gv_y = calc_grad(py0, py1, py2)
        sum_du_y += gu_y * area
        sum_dv_y += gv_y * area
        
        px0, px1, px2 = l0.vert.co.x, l1.vert.co.x, l2.vert.co.x
        gu_x, gv_x = calc_grad(px0, px1, px2)
        sum_du_x += gu_x * area
        sum_dv_x += gv_x * area
        
    len_z = math.hypot(sum_du_z, sum_dv_z)
    len_y = math.hypot(sum_du_y, sum_dv_y)
    len_x = math.hypot(sum_du_x, sum_dv_x)
    
    best_du, best_dv = sum_du_z, sum_dv_z
    if len_z < 1e-4:
        if len_y > len_x:
            best_du, best_dv = sum_du_y, sum_dv_y
        elif len_x > 1e-4:
            best_du, best_dv = sum_du_x, sum_dv_x
        else:
            return None
            
    # Angle of the "up" gradient measured from +V (UV-up axis).
    # Using atan2(dv, du) gives angle from +U; subtracting from 90 converts to angle from +V.
    # Sign convention: positive = CW = tilted-right, negative = CCW = tilted-left.
    # NOTE: negated vs the naive 90-angle formula because in the exported UV PNG the
    # gradient direction and the visual tilt direction are opposite (empirically confirmed).
    angle = math.atan2(best_dv, best_du)
    rot_deg = math.degrees(angle) - 90.0

    while rot_deg > 180.0: rot_deg -= 360.0
    while rot_deg < -180.0: rot_deg += 360.0
    
    return round(rot_deg, 1)


def _compute_rotation_deg_pca(uvs) -> float:
    """
    Returns the angle (degrees) of the dominant axis relative to the horizontal.
      0   → island is mainly wide (horizontal layout)
      ±90 → island is mainly tall (vertical layout)

    The sign distinguishes CW vs CCW tilt.
    """
    n = len(uvs)
    if n < 3:
        return 0.0

    cx = sum(u.x for u in uvs) / n
    cy = sum(u.y for u in uvs) / n

    cxx = sum((u.x - cx) ** 2 for u in uvs) / n
    cyy = sum((u.y - cy) ** 2 for u in uvs) / n
    cxy = sum((u.x - cx) * (u.y - cy) for u in uvs) / n

    angle = 0.5 * math.atan2(2.0 * cxy, cxx - cyy)
    return round(math.degrees(angle), 1)


def _compute_is_flipped(face_polygons: List[List[Tuple[float, float]]]) -> bool:
    """
    Return True if the island's UV faces have CW winding (i.e. mirrored/flipped).

    Uses the shoelace formula: positive signed area → CCW (normal),
    negative → CW (flipped).
    """
    total = 0.0
    for poly in face_polygons:
        n = len(poly)
        if n < 3:
            continue
        sa = sum(
            poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1]
            for i in range(n)
        )
        total += sa
    return total < 0.0


def _find_label_center(
    face_polygons: List[List[Tuple[float, float]]],
    centroid: List[float],
) -> List[float]:
    """
    Return a UV position that is guaranteed to lie INSIDE an actual face polygon.

    Strategy: find the face whose centroid is closest to the island's centroid,
    then use that face's centroid as the label position.  This avoids placing
    labels at the bbox centre, which can fall OUTSIDE the island for L-shaped
    or concave islands.
    """
    if not face_polygons:
        return centroid

    cx, cy = centroid
    best_fc  = None
    best_dist = float("inf")

    for poly in face_polygons:
        if not poly:
            continue
        fc_x = sum(p[0] for p in poly) / len(poly)
        fc_y = sum(p[1] for p in poly) / len(poly)
        d = (fc_x - cx) ** 2 + (fc_y - cy) ** 2
        if d < best_dist:
            best_dist = d
            best_fc   = [fc_x, fc_y]

    return best_fc if best_fc is not None else centroid


def get_island_for_face(context, face_index: int, uv_analysis: dict) -> Optional[str]:
    """Return the island ID containing the given face index, or None."""
    for island in uv_analysis.get("islands", []):
        if face_index in island.get("face_indices", []):
            return island["id"]
    return None
