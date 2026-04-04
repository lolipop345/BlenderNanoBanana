"""
BlenderNanoBanana - Viewport Log Display

Draws recent log messages in the bottom-right corner of the 3D viewport.
Max 6 lines, auto-fades old messages after 8 seconds.
"""

import bpy
import blf
import gpu
import time
from gpu_extras.batch import batch_for_shader
from collections import deque
from typing import List, Tuple

# ── Message store ─────────────────────────────────────────────────────────────

_MAX_MESSAGES = 6
_FADE_AFTER = 8.0       # seconds before message fades out
_REMOVE_AFTER = 12.0    # seconds before message is removed
_MAX_BOX_WIDTH = 420    # max pixel width of the log box

# Each entry: (timestamp, level, text)
# level: "INFO" | "WARN" | "ERROR" | "OK"
_messages: deque = deque(maxlen=_MAX_MESSAGES)

_draw_handler = None


def push(text: str, level: str = "INFO"):
    """Add a message to the viewport log."""
    _messages.append((time.time(), level, text))
    # Trigger a redraw so the message appears immediately
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:
        pass


# ── Level colors ──────────────────────────────────────────────────────────────

_COLORS = {
    "INFO":  (0.85, 0.85, 0.85, 1.0),
    "OK":    (0.4,  0.9,  0.4,  1.0),
    "WARN":  (1.0,  0.75, 0.2,  1.0),
    "ERROR": (1.0,  0.35, 0.35, 1.0),
}

_ICONS = {
    "INFO":  "•",
    "OK":    "✓",
    "WARN":  "!",
    "ERROR": "✗",
}

# ── Draw ──────────────────────────────────────────────────────────────────────

def _draw_callback():
    if not _messages:
        return

    context = bpy.context
    region = context.region
    if region is None or region.type != "WINDOW":
        return

    now = time.time()
    font_id = 0
    font_size = 13
    line_height = 18
    padding_x = 12
    padding_y = 8
    margin_right = 16
    margin_bottom = 36     # above the timeline bar

    # Filter and collect visible messages
    visible = []
    for ts, level, text in _messages:
        age = now - ts
        if age > _REMOVE_AFTER:
            continue
        alpha = 1.0 if age < _FADE_AFTER else max(0.0, 1.0 - (age - _FADE_AFTER) / (_REMOVE_AFTER - _FADE_AFTER))
        visible.append((level, text, alpha))

    if not visible:
        return

    blf.size(font_id, font_size)

    # Truncate lines that exceed max box width
    max_content_w = _MAX_BOX_WIDTH - padding_x * 2 - 4
    truncated = []
    for level, text, alpha in visible:
        line = f"{_ICONS.get(level, '•')}  {text}"
        w, _ = blf.dimensions(font_id, line)
        if w > max_content_w:
            # Binary-search for the longest substring that fits with "…"
            lo, hi = 0, len(line)
            while lo < hi - 1:
                mid = (lo + hi) // 2
                tw, _ = blf.dimensions(font_id, line[:mid] + "…")
                if tw <= max_content_w:
                    lo = mid
                else:
                    hi = mid
            line = line[:lo] + "…"
        truncated.append((level, line, alpha))
    visible = truncated

    # Measure max text width (now guaranteed to fit)
    max_w = 0
    for _, line, _ in visible:
        w, _ = blf.dimensions(font_id, line)
        if w > max_w:
            max_w = w

    box_w = min(max_w + padding_x * 2, _MAX_BOX_WIDTH)
    box_h = len(visible) * line_height + padding_y * 2

    x0 = region.width - box_w - margin_right
    y0 = margin_bottom
    x1 = x0 + box_w
    y1 = y0 + box_h

    # Draw background box (semi-transparent black)
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")

    verts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, "TRIS", {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", (0.06, 0.06, 0.06, 0.78))
    batch.draw(shader)

    # Draw left accent line
    accent_verts = [(x0, y0), (x0 + 2, y0), (x0 + 2, y1), (x0, y1)]
    accent_batch = batch_for_shader(shader, "TRIS", {"pos": accent_verts}, indices=indices)
    shader.uniform_float("color", (0.3, 0.7, 1.0, 0.9))
    accent_batch.draw(shader)

    gpu.state.blend_set("NONE")

    # Draw text lines (newest at top)
    for i, (level, line, alpha) in enumerate(reversed(visible)):
        r, g, b, a = _COLORS.get(level, (1, 1, 1, 1))

        text_x = x0 + padding_x + 4
        text_y = y0 + padding_y + i * line_height

        blf.color(font_id, r, g, b, a * alpha)
        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, line)


# ── Registration ───────────────────────────────────────────────────────────────

def register():
    global _draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback, (), "WINDOW", "POST_PIXEL"
        )
    push("Nano Banana ready", "OK")


def unregister():
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, "WINDOW")
        _draw_handler = None
    _messages.clear()
