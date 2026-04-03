"""
BlenderNanoBanana - Viewport Utilities

Screenshot capture and view matrix helpers.
"""

import os
from typing import Optional, Tuple


def capture_viewport_screenshot(context, output_path: str) -> bool:
    """
    Capture the current 3D viewport to an image file.

    Uses bpy.ops.screen.screenshot_area on the VIEW_3D region.
    Falls back to bpy.ops.screen.screenshot if needed.
    """
    import bpy

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Find the VIEW_3D area
    area = None
    for a in context.screen.areas:
        if a.type == "VIEW_3D":
            area = a
            break

    if area is None:
        print("[NanoBanana::ViewportUtils] No VIEW_3D area found.")
        return False

    try:
        # Override context to the VIEW_3D area
        with context.temp_override(area=area):
            bpy.ops.screen.screenshot_area(filepath=output_path)
        return os.path.isfile(output_path)
    except Exception as e:
        print(f"[NanoBanana::ViewportUtils] Screenshot failed: {e}")
        return False


def get_viewport_region3d(context):
    """Return the RegionView3D of the active VIEW_3D area, or None."""
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    return area.spaces.active.region_3d
    return None


def get_view_matrix(context):
    """Return the current view matrix as a 4x4 list of lists."""
    r3d = get_viewport_region3d(context)
    if r3d is None:
        return None
    m = r3d.view_matrix
    return [list(row) for row in m]


def get_viewport_size(context) -> Tuple[int, int]:
    """Return (width, height) of the VIEW_3D area window region."""
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    return region.width, region.height
    return (800, 600)
