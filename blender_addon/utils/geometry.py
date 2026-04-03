"""
BlenderNanoBanana - UV / 3D Geometry Math Utilities
"""

from typing import Tuple, List


# ── UV Space ──────────────────────────────────────────────────────────────────

def uv_bounding_box(uv_coords: List[Tuple[float, float]]):
    """Return (min_u, min_v, max_u, max_v) for a list of UV coordinates."""
    if not uv_coords:
        return 0.0, 0.0, 1.0, 1.0
    us = [uv[0] for uv in uv_coords]
    vs = [uv[1] for uv in uv_coords]
    return min(us), min(vs), max(us), max(vs)


def uv_area(uv_coords: List[Tuple[float, float]], face_indices: List[List[int]]) -> float:
    """Calculate total UV area for a set of triangulated faces."""
    total = 0.0
    for tri in face_indices:
        if len(tri) < 3:
            continue
        a, b, c = uv_coords[tri[0]], uv_coords[tri[1]], uv_coords[tri[2]]
        # Cross product magnitude / 2
        area = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0
        total += area
    return total


def uv_center(uv_coords: List[Tuple[float, float]]) -> Tuple[float, float]:
    if not uv_coords:
        return 0.5, 0.5
    return (
        sum(uv[0] for uv in uv_coords) / len(uv_coords),
        sum(uv[1] for uv in uv_coords) / len(uv_coords),
    )


# ── 3D Space ──────────────────────────────────────────────────────────────────

def vec3_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec3_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vec3_length(v):
    return (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5


def vec3_normalize(v):
    l = vec3_length(v)
    if l < 1e-8:
        return (0.0, 0.0, 1.0)
    return (v[0] / l, v[1] / l, v[2] / l)


def mesh_bounding_box(vertices):
    """Return {"min": [x,y,z], "max": [x,y,z]} for a vertex list."""
    if not vertices:
        return {"min": [0, 0, 0], "max": [0, 0, 0]}
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
    }


def check_symmetry_x(vertices, tolerance: float = 0.001) -> bool:
    """Quick check: does the mesh have approximate X-axis symmetry?"""
    if not vertices:
        return False
    mirrored = set()
    vset = {(round(v[0], 3), round(v[1], 3), round(v[2], 3)) for v in vertices}
    for v in vset:
        mirror = (-v[0], v[1], v[2])
        mirrored.add(mirror)
    overlap = len(vset & mirrored)
    return overlap > len(vset) * 0.8
