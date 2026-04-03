"""
BlenderNanoBanana - Viewport 2D Overlay

Draws UV island highlights and semantic tag labels in the 3D viewport
using Blender's GPU API (gpu.shader + blf text).

Registration adds a persistent draw handler on the VIEW_3D space.
"""

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from typing import Optional

from ..config.constants import (
    OVERLAY_UV_HIGHLIGHT_COLOR,
    OVERLAY_SEAM_COLOR,
    OVERLAY_TAG_LABEL_COLOR,
    OVERLAY_OPACITY,
)

_draw_handler = None


def register():
    global _draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback, (), "WINDOW", "POST_PIXEL"
        )


def unregister():
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, "WINDOW")
        _draw_handler = None


def _draw_callback():
    """Main draw callback — called every viewport redraw."""
    context = bpy.context
    if context is None:
        return

    props = getattr(context.scene, "nano_banana", None)
    if props is None or not props.show_uv_overlay:
        return

    # Draw UV island bounds if analysis data is available
    _draw_uv_bounds(context, props)

    # Draw semantic tag labels
    if props.show_semantic_labels:
        _draw_tag_labels(context, props)


def _draw_uv_bounds(context, props):
    """Draw UV island bounding boxes as 2D screen-space rectangles."""
    # UV bounds are stored per-region in scene custom properties
    islands_data = context.scene.get("nb_uv_islands")
    if not islands_data:
        return

    try:
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        r, g, b, a = OVERLAY_UV_HIGHLIGHT_COLOR
        a *= OVERLAY_OPACITY

        gpu.state.blend_set("ALPHA")

        for island in islands_data:
            screen_rect = island.get("screen_rect")
            if not screen_rect:
                continue

            x0, y0, x1, y1 = screen_rect
            verts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            indices = [(0, 1), (1, 2), (2, 3), (3, 0)]

            batch = batch_for_shader(shader, "LINES",
                                     {"pos": verts},
                                     indices=indices)
            shader.bind()
            shader.uniform_float("color", (r, g, b, a))
            batch.draw(shader)

        gpu.state.blend_set("NONE")

    except Exception:
        pass


def _draw_tag_labels(context, props):
    """Draw semantic tag name labels on UV islands."""
    islands_data = context.scene.get("nb_uv_islands")
    if not islands_data:
        return

    try:
        font_id = 0
        r, g, b, a = OVERLAY_TAG_LABEL_COLOR

        for island in islands_data:
            tag_name = island.get("tag_name")
            screen_pos = island.get("screen_center")
            if not tag_name or not screen_pos:
                continue

            blf.size(font_id, 14)
            blf.color(font_id, r, g, b, a)
            blf.position(font_id, screen_pos[0], screen_pos[1], 0)
            blf.draw(font_id, tag_name)

    except Exception:
        pass


def update_island_display_data(context, uv_analysis: dict, tag_map: dict):
    """
    Store UV island screen positions for the draw callback.

    Args:
        uv_analysis: Output from uv_analyzer.analyze_uv_islands()
        tag_map: {uv_region_id: tag_name}
    """
    if not uv_analysis:
        context.scene["nb_uv_islands"] = []
        return

    islands_display = []
    for island in uv_analysis.get("islands", []):
        iid = island.get("id", "")
        bounds = island.get("bounds", {})
        center = island.get("center", [0.5, 0.5])

        # Convert UV (0-1) to screen space
        region = _get_uv_region(context)
        if region:
            screen_rect = _uv_to_screen(bounds, region)
            screen_center = _uv_point_to_screen(center, region)
        else:
            screen_rect = None
            screen_center = None

        islands_display.append({
            "id": iid,
            "screen_rect": screen_rect,
            "screen_center": screen_center,
            "tag_name": tag_map.get(iid, ""),
        })

    context.scene["nb_uv_islands"] = islands_display


def _get_uv_region(context):
    """Return the IMAGE_EDITOR region if open, else None."""
    for area in context.screen.areas:
        if area.type == "IMAGE_EDITOR":
            for region in area.regions:
                if region.type == "WINDOW":
                    return region
    return None


def _uv_to_screen(bounds: dict, region) -> Optional[tuple]:
    """Convert UV bounding box to screen pixel rect."""
    if not bounds:
        return None
    try:
        min_u, min_v = bounds["min"]
        max_u, max_v = bounds["max"]
        w, h = region.width, region.height
        return (
            int(min_u * w), int(min_v * h),
            int(max_u * w), int(max_v * h),
        )
    except Exception:
        return None


def _uv_point_to_screen(uv_point, region) -> Optional[tuple]:
    if not uv_point or not region:
        return None
    try:
        return (int(uv_point[0] * region.width), int(uv_point[1] * region.height))
    except Exception:
        return None
