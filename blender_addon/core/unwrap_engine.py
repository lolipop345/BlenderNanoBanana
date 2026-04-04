"""
BlenderNanoBanana - UV Unwrapping Engine (Blender native, pure Python)
"""

from ..utils.logging import log_info, log_debug, log_error

_MODULE = "UnwrapEngine"


def mark_seam(context) -> bool:
    import bpy
    try:
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            return False
        if context.mode != "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.mark_seam(clear=False)
        log_debug("Seams marked.", _MODULE)
        return True
    except Exception as e:
        log_error(f"Mark seam failed: {e}", _MODULE, e)
        return False


def clear_seam(context) -> bool:
    import bpy
    try:
        if context.mode != "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.mark_seam(clear=True)
        return True
    except Exception as e:
        log_error(f"Clear seam failed: {e}", _MODULE, e)
        return False


def unwrap_uv(context, method: str = "ANGLE_BASED",
              fill_holes: bool = True,
              correct_aspect: bool = True) -> bool:
    import bpy
    try:
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            log_error("No active mesh for unwrap.", _MODULE)
            return False

        was_object_mode = context.mode == "OBJECT"
        if was_object_mode:
            bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.unwrap(
            method=method,
            fill_holes=fill_holes,
            correct_aspect=correct_aspect,
            use_subsurf_data=False,
            margin=0.001,
        )

        log_info(f"UV unwrap complete ({method}).", _MODULE)

        if was_object_mode:
            bpy.ops.object.mode_set(mode="OBJECT")

        return True
    except Exception as e:
        log_error(f"Unwrap failed: {e}", _MODULE, e)
        return False


def pack_islands(context, margin: float = 0.005) -> bool:
    import bpy
    try:
        if context.mode != "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(margin=margin)
        log_info("UV islands packed.", _MODULE)
        return True
    except Exception as e:
        log_error(f"Pack islands failed: {e}", _MODULE, e)
        return False
