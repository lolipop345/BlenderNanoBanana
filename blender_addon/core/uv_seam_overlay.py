"""
BlenderNanoBanana - UV Editor Seam Tag Overlay

Draws colored edge lines and tag labels in the Image Editor (UV editor) for
edges that have been assigned a semantic tag via seam_tag_ops.

Works in both Object Mode (mesh.polygons) and Edit Mode (bmesh.from_edit_mesh).
Registration adds a persistent draw handler on the IMAGE_EDITOR space.
"""

import colorsys
import json

import bpy
import bmesh
import gpu
import blf
from gpu_extras.batch import batch_for_shader

from ..config.constants import SEAM_TAG_COLORS

_draw_handler = None


# ── Color Helper ──────────────────────────────────────────────────────────────

def _tag_color(tag_id: str) -> tuple:
    """
    Return RGBA color for a tag_id.
    Known keywords → fixed color. Unknown → deterministic hash-based hue.
    """
    tag_lower = tag_id.lower()
    for key, color in SEAM_TAG_COLORS.items():
        if key in tag_lower:
            return color

    # Hash-based color: same tag_id always gives same color, good saturation/brightness
    h = hash(tag_id) & 0xFFFFFF
    hue = (h % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
    return (r, g, b, 1.0)


# ── UV Coordinate Helpers ─────────────────────────────────────────────────────

def _build_edge_uv_map_bmesh(obj):
    """
    Build edge_index → (uv_a, uv_b) map using bmesh (Edit Mode safe).
    Returns (uv_map_dict, None) — second value kept for API parity.
    """
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    bm.edges.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        return {}, None

    edge_uvs = {}
    for edge in bm.edges:
        uv_a = uv_b = None
        for face in edge.link_faces:
            for loop in face.loops:
                if loop.edge == edge:
                    if uv_a is None:
                        uv_a = tuple(loop[uv_layer].uv)
                    elif uv_b is None:
                        uv_b = tuple(loop[uv_layer].uv)
            if uv_a is not None and uv_b is not None:
                break
        if uv_a is not None and uv_b is not None:
            edge_uvs[edge.index] = (uv_a, uv_b)

    return edge_uvs


def _build_edge_uv_map_object(mesh):
    """
    Build edge_index → (uv_a, uv_b) map using mesh.polygons (Object Mode).
    Single pass: O(loops) total.
    """
    uv_layers = mesh.uv_layers
    if not uv_layers:
        return {}
    uv_layer = uv_layers.active
    if uv_layer is None:
        return {}

    # Build vert → (loop_idx, uv) fast lookup
    vert_to_uv = {}
    for loop in mesh.loops:
        vert_to_uv.setdefault(loop.vertex_index, []).append(
            (loop.index, tuple(uv_layer.data[loop.index].uv))
        )

    # Build polygon edge membership: (v0,v1) → True
    poly_edge_verts = set()
    for poly in mesh.polygons:
        verts = list(poly.vertices)
        for i in range(len(verts)):
            a, b = verts[i], verts[(i + 1) % len(verts)]
            poly_edge_verts.add((min(a, b), max(a, b)))

    edge_uvs = {}
    for edge in mesh.edges:
        v0, v1 = edge.vertices[0], edge.vertices[1]
        key = (min(v0, v1), max(v0, v1))
        if key not in poly_edge_verts:
            continue
        uvs0 = vert_to_uv.get(v0, [])
        uvs1 = vert_to_uv.get(v1, [])
        if uvs0 and uvs1:
            edge_uvs[edge.index] = (uvs0[0][1], uvs1[0][1])

    return edge_uvs


def _uv_to_screen(uv, view2d):
    """Convert a (u, v) coordinate to screen pixel (x, y)."""
    x, y = view2d.view_to_region(uv[0], uv[1], clip=False)
    return (x, y)


# ── Draw Callback ─────────────────────────────────────────────────────────────

def _draw_callback():
    """Called every IMAGE_EDITOR redraw."""
    context = bpy.context
    if context is None:
        return

    props = getattr(context.scene, "nano_banana", None)
    if props is None:
        return

    if not props.show_uv_overlay:
        return

    tags_json = getattr(props, "seam_tags_json", "{}")
    try:
        all_tags = json.loads(tags_json or "{}")
    except Exception:
        return

    if not all_tags:
        return

    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return

    mesh = obj.data
    mesh_key = mesh.name

    mesh_tags = all_tags.get(mesh_key)
    if not mesh_tags:
        return

    # Need region + view2d from the current IMAGE_EDITOR area
    region = context.region
    if region is None or region.type != "WINDOW":
        return
    view2d = region.view2d

    # ── Build edge→UV map (mode-aware) ───────────────────────────────────────
    try:
        if obj.mode == 'EDIT':
            edge_uv_map = _build_edge_uv_map_bmesh(obj)
        else:
            edge_uv_map = _build_edge_uv_map_object(mesh)
    except Exception:
        return

    if not edge_uv_map:
        return

    # ── Collect lines to draw ─────────────────────────────────────────────────
    color_lines: dict = {}       # color_tuple → [((x0,y0), (x1,y1)), ...]
    label_positions: list = []   # [(mx, my, text, color)]

    for edge_idx_str, tag_id in mesh_tags.items():
        try:
            edge_idx = int(edge_idx_str)
        except ValueError:
            continue

        uv_pair = edge_uv_map.get(edge_idx)
        if uv_pair is None:
            continue

        uv_a, uv_b = uv_pair
        sx0, sy0 = _uv_to_screen(uv_a, view2d)
        sx1, sy1 = _uv_to_screen(uv_b, view2d)

        color = _tag_color(tag_id)
        color_lines.setdefault(color, []).append(((sx0, sy0), (sx1, sy1)))

        # Label at edge midpoint
        mx = (sx0 + sx1) / 2
        my = (sy0 + sy1) / 2
        try:
            from ..core.semantic_manager import get_tag as _get_tag
            tag_def = _get_tag(tag_id)
            tag_name = tag_def["name"] if tag_def else tag_id
        except Exception:
            tag_name = tag_id
        label_positions.append((mx, my, f"Tag: {tag_name}", color))

    if not color_lines:
        return

    # ── Draw lines ────────────────────────────────────────────────────────────
    try:
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(2.5)

        for color, segments in color_lines.items():
            verts = []
            for (x0, y0), (x1, y1) in segments:
                verts.append((x0, y0))
                verts.append((x1, y1))

            indices = [(i * 2, i * 2 + 1) for i in range(len(segments))]
            batch = batch_for_shader(shader, "LINES", {"pos": verts}, indices=indices)
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)

        gpu.state.line_width_set(1.0)
        gpu.state.blend_set("NONE")
    except Exception:
        pass

    # ── Draw labels ───────────────────────────────────────────────────────────
    try:
        font_id = 0
        for mx, my, text, color in label_positions:
            r, g, b, a = color
            blf.size(font_id, 11)
            blf.color(font_id, r, g, b, 0.95)
            blf.position(font_id, mx + 4, my + 4, 0)
            blf.draw(font_id, text)
    except Exception:
        pass


# ── Registration ──────────────────────────────────────────────────────────────

def register():
    global _draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceImageEditor.draw_handler_add(
            _draw_callback, (), "WINDOW", "POST_PIXEL"
        )


def unregister():
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_draw_handler, "WINDOW")
        _draw_handler = None
