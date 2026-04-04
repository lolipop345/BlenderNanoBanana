"""
BlenderNanoBanana - UV Layout Capture

Exports the active mesh's UV layout as a PNG image so it can be sent to Gemini
as additional visual context (alongside the viewport screenshot).

Optionally annotates the exported image with island ID labels + material tags
at each island's UV centroid (requires Pillow; gracefully skipped if not installed).

Must be called on Blender's main thread — uses bpy operators.
"""

import os
from typing import Optional, List, Dict

from ..utils.logging import log_debug, log_error

_MODULE = "UVLayoutCapture"


def capture_uv_layout(context, output_path: str) -> Optional[str]:
    """
    Export the active mesh's UV layout to a PNG file using bpy.ops.uv.export_layout.

    Args:
        context: Blender context (main thread only)
        output_path: Full path for the output PNG file

    Returns:
        output_path if successful, None on failure.
    """
    import bpy

    obj = context.active_object
    if obj is None or obj.type != "MESH":
        log_debug("UV layout capture skipped: no active mesh.", _MODULE)
        return None

    mesh = obj.data
    if not mesh.uv_layers:
        log_debug("UV layout capture skipped: mesh has no UV layers.", _MODULE)
        return None

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    except Exception:
        pass

    try:
        prev_mode = obj.mode
        bpy.ops.object.mode_set(mode="EDIT")

        # Select all UV faces so the full layout is exported
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.export_layout(
            filepath=output_path,
            export_all=True,
            modified=False,
            mode="PNG",
            size=(1024, 1024),
            opacity=1.0,
            check_existing=False,
        )

        bpy.ops.object.mode_set(mode=prev_mode)

        if os.path.exists(output_path):
            log_debug(f"UV layout exported to: {output_path}", _MODULE)
            return output_path

        log_error("UV layout export produced no file.", _MODULE)
        return None

    except Exception as e:
        log_error(f"UV layout export failed: {e}", _MODULE, e)
        try:
            bpy.ops.object.mode_set(mode=prev_mode)
        except Exception:
            pass
        return None


def annotate_uv_layout(
    image_path: str,
    islands: List[Dict],
    island_tags: Dict[str, str],
) -> bool:
    """
    Draw island ID + material tag labels onto the exported UV layout image.

    Uses Pillow (PIL). If Pillow is not installed this function returns False
    and the image is left unchanged.

    Args:
        image_path: Path to the PNG file to annotate (modified in-place)
        islands:    Island list from nb_uv_analysis["islands"]
                    Each island has {"id": str, "center": [u, v], ...}
        island_tags: Dict of island_id → tag string

    Returns:
        True if annotation succeeded, False otherwise.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log_debug("Pillow not available — UV layout annotation skipped.", _MODULE)
        return False

    try:
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        img_w, img_h = img.size

        # Try to get a readable font; fall back to default bitmap font
        font_label = font_tag = None
        try:
            font_label = ImageFont.truetype("arial.ttf", 13)
            font_tag   = ImageFont.truetype("arial.ttf", 11)
        except Exception:
            font_label = ImageFont.load_default()
            font_tag   = font_label

        for island in islands:
            iid    = island.get("id", "?")
            center = island.get("center", [0.5, 0.5])

            # UV (0,0) = bottom-left in Blender, but image (0,0) = top-left
            px = int(center[0] * img_w)
            py = int((1.0 - center[1]) * img_h)

            tag = island_tags.get(iid, "")
            label_line1 = iid
            label_line2 = tag if tag else ""

            # Measure text width for background rectangle
            w1 = _text_width(draw, label_line1, font_label)
            w2 = _text_width(draw, label_line2, font_tag) if label_line2 else 0
            box_w = max(w1, w2) + 8
            box_h = 14 + (13 if label_line2 else 0) + 4

            # Background box (semi-transparent dark)
            bx0, by0 = px - 2, py - 2
            bx1, by1 = bx0 + box_w, by0 + box_h
            draw.rectangle([bx0, by0, bx1, by1], fill=(0, 0, 0, 180))

            # Island ID in white
            draw.text((px + 2, py), label_line1, fill=(255, 255, 255, 255), font=font_label)

            # Tag in yellow (if present)
            if label_line2:
                draw.text((px + 2, py + 14), label_line2, fill=(255, 220, 0, 255), font=font_tag)

            # Small dot at the centroid
            draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(0, 220, 255, 220))

        img.save(image_path, "PNG")
        log_debug(f"UV layout annotated with {len(islands)} island label(s).", _MODULE)
        return True

    except Exception as e:
        log_error(f"UV layout annotation failed: {e}", _MODULE, e)
        return False


def _text_width(draw, text: str, font) -> int:
    """Return pixel width of text given a font (handles both old and new Pillow APIs)."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    except AttributeError:
        # Older Pillow: textsize
        w, _ = draw.textsize(text, font=font)
        return w
