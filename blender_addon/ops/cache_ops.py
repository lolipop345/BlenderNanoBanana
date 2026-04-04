"""
BlenderNanoBanana - Cache Management Operators

BrowseCache: Open the project cache folder.
ClearRegionCache: Delete cache for the active UV region.
ClearProjectCache: Delete all project cache.
"""

import bpy
import os
from bpy.types import Operator
from bpy.props import BoolProperty

from ..core.cache_manager import (
    clear_region_cache,
    clear_project_cache,
    get_cache_base_path,
    get_project_name,
)


class NANOBANANA_OT_browse_cache(Operator):
    """Open the project cache directory in the OS file manager"""
    bl_idname = "nanobanana.browse_cache"
    bl_label = "Browse Cache"
    bl_options = {"REGISTER"}

    def execute(self, context):
        base = get_cache_base_path(context)
        project = get_project_name(context)
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in project)
        proj_dir = os.path.join(base, safe)

        os.makedirs(proj_dir, exist_ok=True)
        bpy.ops.wm.path_open(filepath=proj_dir)
        return {"FINISHED"}


class NANOBANANA_OT_clear_region_cache(Operator):
    """Delete all cached data for the active UV region"""
    bl_idname = "nanobanana.clear_region_cache"
    bl_label = "Clear Region Cache"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event,
        )

    def execute(self, context):
        props = context.scene.nano_banana
        uv_region_id = props.active_uv_region_id
        if not uv_region_id:
            self.report({"WARNING"}, "No UV region selected.")
            return {"CANCELLED"}

        clear_region_cache(context, uv_region_id)
        # Clear stale map paths that belonged to this region
        props.last_generated_maps_json = "{}"
        try:
            from ..utils.preview_manager import clear as _clear_previews
            _clear_previews()
        except Exception:
            pass
        self.report({"INFO"}, f"Cache cleared for region '{uv_region_id}'.")
        return {"FINISHED"}


class NANOBANANA_OT_clear_project_cache(Operator):
    """Delete ALL cached data for the current project (cannot be undone)"""
    bl_idname = "nanobanana.clear_project_cache"
    bl_label = "Clear Project Cache"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event,
        )

    def execute(self, context):
        clear_project_cache(context)
        # Clear stale scene props
        props = context.scene.nano_banana
        props.last_generated_maps_json = "{}"
        try:
            from ..utils.preview_manager import clear as _clear_previews
            _clear_previews()
        except Exception:
            pass
        self.report({"INFO"}, "Project cache cleared.")
        return {"FINISHED"}


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_browse_cache,
    NANOBANANA_OT_clear_region_cache,
    NANOBANANA_OT_clear_project_cache,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
