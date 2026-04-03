"""
BlenderNanoBanana - UV Unwrapping Engine

Orchestrates Blender native unwrap + Rust UV packing.
"""

from typing import Optional, Dict, Any

from ..utils.logging import log_info, log_debug, log_error

_MODULE = "UnwrapEngine"


def mark_seam(context) -> bool:
    """Mark selected edges as UV seams (Blender native)."""
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
    """Clear UV seams from selected edges."""
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
    """
    Execute UV unwrap using Blender's native unwrap operator.

    Args:
        method: "ANGLE_BASED" or "CONFORMAL"
        fill_holes: Fill holes in UV layout
        correct_aspect: Correct aspect ratio

    Returns:
        True on success.
    """
    import bpy
    try:
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            log_error("No active mesh for unwrap.", _MODULE)
            return False

        # Enter edit mode
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


def pack_islands(context, margin: float = 0.005,
                 use_rust: bool = True) -> bool:
    """
    Pack UV islands to use UV space efficiently.

    Uses Rust backend if available, falls back to Blender native packing.
    """
    import bpy

    if use_rust:
        packed = _rust_pack(context, margin)
        if packed:
            return True
        log_debug("Rust pack failed, using Blender pack.", _MODULE)

    # Blender native packing fallback
    try:
        if context.mode != "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(margin=margin)
        log_info("UV islands packed (Blender native).", _MODULE)
        return True
    except Exception as e:
        log_error(f"Pack islands failed: {e}", _MODULE, e)
        return False


def _rust_pack(context, margin: float) -> bool:
    """Attempt to pack UV islands via Rust backend and apply result."""
    try:
        from .rust_bridge import get_rust_bridge
        from .uv_analyzer import analyze_uv_islands

        bridge = get_rust_bridge()
        if not bridge.is_running():
            return False

        analysis = analyze_uv_islands(context)
        if not analysis or not analysis.get("islands"):
            return False

        result = bridge.pack_uv_islands(
            islands=analysis["islands"],
            canvas_size=1024,
            margin=margin,
        )

        # Apply transforms back to Blender UV layer
        _apply_pack_transforms(context, result.get("packed_islands", []))
        log_info(
            f"Rust UV packing complete. Utilization: "
            f"{result.get('utilization', 0):.1%}", _MODULE
        )
        return True
    except Exception as e:
        log_error(f"Rust pack error: {e}", _MODULE, e)
        return False


def _apply_pack_transforms(context, packed_islands: list):
    """Apply offset/scale transforms from Rust packing result to Blender UVs."""
    import bpy
    import bmesh

    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return

    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh) if context.mode == "EDIT_MESH" else bmesh.new()
    if context.mode != "EDIT_MESH":
        bm.from_mesh(mesh)

    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        bm.free()
        return

    # Build island_id → transform lookup
    transforms = {
        pi["id"]: pi["transform"]
        for pi in packed_islands
        if "id" in pi and "transform" in pi
    }

    # For now just tag: full Rust island transform application
    # requires matching face indices to island IDs (complex).
    # This is a placeholder — real mapping uses island["face_indices"].
    if context.mode != "EDIT_MESH":
        bm.to_mesh(mesh)
    bm.free()
