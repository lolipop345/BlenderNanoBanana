"""
BlenderNanoBanana - UV Layout Capture

Exports the active mesh's UV layout as a PNG image so it can be sent to Gemini
as additional visual context (alongside the viewport screenshot).

Must be called on Blender's main thread — uses bpy operators.
"""

import os
from typing import Optional

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

    # Ensure the object has UV data
    mesh = obj.data
    if not mesh.uv_layers:
        log_debug("UV layout capture skipped: mesh has no UV layers.", _MODULE)
        return None

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    except Exception:
        pass

    try:
        # export_layout works in EDIT and OBJECT mode
        # We need to be in EDIT mode with all faces selected for a full layout export.
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

        # Restore previous mode
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
