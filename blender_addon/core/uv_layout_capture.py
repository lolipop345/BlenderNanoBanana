"""
BlenderNanoBanana - UV Layout Capture

Exports the active mesh's UV layout as a PNG wireframe and optionally stamps
each UV island with a small ID label (e.g. "uv_025") so that Gemini Image
can correlate the visual island positions on the wireframe with the material
assignments described in the text prompt ("uv_025=Metal, uv_013=Skin, ...").

Only island IDs are drawn — no colors, no material tags, no debug overlay.

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
    Draw island ID + material tag labels onto the exported UV layout image,
    and fill the UV island polygons with distinct colors per material tag!

    Uses Pillow (PIL). If Pillow is not installed this function returns False
    and the image is left unchanged.

    Args:
        image_path: Path to the PNG file to annotate (modified in-place)
        islands:    Island list from nb_uv_analysis["islands"]
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
        # Load the raw wireframe exported from Blender
        img = Image.open(image_path).convert("RGBA")
        img_w, img_h = img.size

        # Create a blank image for filled polygons (drawn BEHIND the wireframe)
        poly_img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        poly_draw = ImageDraw.Draw(poly_img)

        # Palette of distinct RGBA colors (with 180 alpha for visibility)
        palette = [
            (255, 75, 75, 180),   # Red
            (75, 200, 75, 180),   # Green
            (75, 125, 255, 180),  # Blue
            (255, 200, 50, 180),  # Yellow
            (240, 100, 240, 180), # Magenta
            (50, 210, 210, 180),  # Cyan
            (255, 150, 50, 180),  # Orange
            (180, 100, 255, 180), # Purple
            (180, 255, 75, 180),  # Lime
            (255, 150, 150, 180), # Pink
            (120, 180, 255, 180), # Light Blue
            (210, 210, 120, 180), # Khaki
        ]
        
        # Map unique tags to palette colors
        unique_tags = list(sorted(set(t for t in island_tags.values() if t)))
        tag_colors = {tag: palette[i % len(palette)] for i, tag in enumerate(unique_tags)}
        base_color = (100, 100, 100, 80) # Grey for untagged

        # 1. Draw polygons
        for island in islands:
            iid = island.get("id", "?")
            tag_name = island_tags.get(iid, "")
            color = tag_colors.get(tag_name, base_color)
            
            for poly in island.get("face_polygons", []):
                # (u, v) -> (x, y) where Y is inverted
                px_coords = [(int(u * img_w), int((1.0 - v) * img_h)) for u, v in poly]
                if len(px_coords) >= 3:
                    poly_draw.polygon(px_coords, fill=color)

        # Composite wireframe over the filled polygons
        out_img = Image.alpha_composite(poly_img, img)
        draw = ImageDraw.Draw(out_img)

        # Try to get a readable font; fall back to default bitmap font
        font_label = font_tag = None
        try:
            font_label = ImageFont.truetype("arial.ttf", 15)
            font_tag   = ImageFont.truetype("arial.ttf", 13)
        except Exception:
            font_label = ImageFont.load_default()
            font_tag   = font_label

        # 2. Draw text labels on top
        for island in islands:
            iid    = island.get("id", "?")
            center = island.get("label_center", island.get("bbox_center", island.get("center", [0.5, 0.5])))

            px = int(center[0] * img_w)
            py = int((1.0 - center[1]) * img_h)

            tag = island_tags.get(iid, "")
            label_line1 = iid
            label_line2 = tag if tag else ""

            w1 = _text_width(draw, label_line1, font_label)
            w2 = _text_width(draw, label_line2, font_tag) if label_line2 else 0
            box_w = max(w1, w2) + 12
            box_h = 16 + (16 if label_line2 else 0) + 6

            # Background box
            bx0, by0 = px - 4, py - 4
            bx1, by1 = bx0 + box_w, by0 + box_h
            draw.rectangle([bx0, by0, bx1, by1], fill=(0, 0, 0, 200), outline=(255, 255, 255, 100))

            # Island ID text
            draw.text((px + 2, py - 2), label_line1, fill=(255, 255, 255, 255), font=font_label)

            # Tag text
            if label_line2:
                # Use the tag color for the text too, to make it super obvious
                text_col = tag_colors.get(tag, (255, 220, 0, 255))
                # Boost alpha to max for text
                text_col = (text_col[0], text_col[1], text_col[2], 255)
                draw.text((px + 2, py + 14), label_line2, fill=text_col, font=font_tag)

            # Small center dot
            draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(0, 255, 255, 255))

        out_img.save(image_path, "PNG")
        log_debug(f"UV layout annotated with {len(islands)} colored island(s).", _MODULE)
        return True

    except Exception as e:
        log_error(f"UV layout coloring failed: {e}", _MODULE, e)
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


def annotate_uv_with_ids(
    image_path: str,
    islands: List[Dict],
) -> bool:
    """
    Stamp each UV island with ONLY its short ID label (e.g. "uv_025").

    No colors. No material tags. No polygon fills. No debug boxes.
    Just a small white text label at each island's centroid so that Gemini
    can match the label to the mesh region when it reads the text prompt
    ("uv_025=Metal, uv_013=Skin, ...").

    Args:
        image_path: Path to the UV wireframe PNG (modified in-place).
        islands:    Island list from nb_uv_analysis["islands"].

    Returns True on success, False if Pillow unavailable or error.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log_debug("Pillow not available — UV ID annotation skipped.", _MODULE)
        return False

    try:
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        img_w, img_h = img.size

        # Small but legible font
        try:
            font = ImageFont.truetype("arial.ttf", 11)
        except Exception:
            font = ImageFont.load_default()

        for island in islands:
            iid    = island.get("id", "?")
            # label_center is guaranteed inside a real face polygon (not just bbox midpoint)
            center = island.get("label_center", island.get("bbox_center", island.get("center", [0.5, 0.5])))

            # UV → image pixel coords (Y-flip)
            cx = int(center[0] * img_w)
            cy = int((1.0 - center[1]) * img_h)

            tw = _text_width(draw, iid, font)
            th = 11  # approximate text height for small font

            # Center text on the island centroid (not top-left aligned)
            tx = cx - tw // 2
            ty = cy - th // 2

            # Tiny semi-transparent black backing so text is readable on white wireframe
            draw.rectangle(
                [tx - 2, ty - 1, tx + tw + 2, ty + th + 1],
                fill=(0, 0, 0, 180),
            )
            # White label text, centered on island
            draw.text((tx, ty), iid, fill=(255, 255, 255, 255), font=font)

        img.save(image_path, "PNG")
        log_debug(f"UV layout stamped with {len(islands)} ID label(s).", _MODULE)
        return True

    except Exception as e:
        log_error(f"UV ID annotation failed: {e}", _MODULE, e)
        return False

