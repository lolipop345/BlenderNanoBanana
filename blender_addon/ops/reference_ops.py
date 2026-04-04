"""
BlenderNanoBanana - Reference Image Operators

GenerateReferences: Generate reference images for the active UV region.
  Runs in a background thread so Blender doesn't freeze.
BrowseReferences: Open the cache folder in the OS file manager.
"""

import threading
import bpy
import os
from bpy.types import Operator
from bpy.props import BoolProperty, IntProperty

from ..core.reference_generator import generate_references
from ..core.semantic_manager import get_tag_for_region
from ..core.cache_manager import (
    get_project_name, get_cache_base_path,
    get_region_dir, set_thread_overrides,
)
from ..preferences import get_preferences


class NANOBANANA_OT_generate_references(Operator):
    """Generate reference images for the active UV region (runs in background)"""
    bl_idname = "nanobanana.generate_references"
    bl_label = "Generate References"
    bl_options = {"REGISTER"}

    count: IntProperty(
        name="Count",
        description="Number of reference images to generate",
        default=3, min=1, max=10,
    )
    force: BoolProperty(
        name="Force Regenerate",
        description="Generate new references even if cached ones exist",
        default=False,
    )

    _timer = None
    _thread: threading.Thread = None
    _done: bool = False
    _count: int = 0
    _error: str = None

    def execute(self, context):
        prefs = get_preferences(context)
        props = context.scene.nano_banana

        if not prefs.google_api_key:
            self.report({"ERROR"}, "Google API Key not configured in Addon Preferences.")
            return {"CANCELLED"}

        uv_region_id = props.active_uv_region_id
        if not uv_region_id:
            self.report({"WARNING"}, "No UV region selected. Use Analyze UV Islands first.")
            return {"CANCELLED"}

        project_name = get_project_name(context)
        tag_data = get_tag_for_region(context, uv_region_id, project_name)

        if tag_data is None:
            # Fallback: use active_semantic_tag from scene props
            from ..core.semantic_manager import get_tag, apply_tag_to_region
            active_tag_id = props.active_semantic_tag
            if not active_tag_id or active_tag_id == "none":
                self.report({"WARNING"},
                            "Select a semantic tag first (Semantic Tags panel).")
                return {"CANCELLED"}
            tag_def = get_tag(active_tag_id)
            if tag_def is None:
                self.report({"ERROR"}, f"Unknown tag: '{active_tag_id}'")
                return {"CANCELLED"}
            # Auto-save tag so future lookups work
            apply_tag_to_region(context, uv_region_id, active_tag_id, project_name)
        else:
            tag_def = tag_data.get("tag_definition", {})

        # Pre-compute bpy values for background thread
        api_key = prefs.google_api_key
        count = self.count
        cache_base = get_cache_base_path(context)
        set_thread_overrides(cache_base, project_name)

        self._done = False
        self._count = 0
        self._error = None

        props.is_generating = True
        props.generation_status = f"Generating {count} reference images..."
        props.generation_progress = 0.0

        def _run():
            try:
                saved = generate_references(
                    context=context,
                    api_key=api_key,
                    uv_region_id=uv_region_id,
                    tag_definition=tag_def,
                    project_name=project_name,
                    count=count,
                )
                self._count = len(saved)
            except Exception as e:
                self._error = str(e)
            finally:
                self._done = True
                set_thread_overrides(None, None)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

        self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        for area in context.screen.areas:
            if area.type in ("VIEW_3D", "IMAGE_EDITOR"):
                area.tag_redraw()

        if not self._done:
            return {"RUNNING_MODAL"}

        context.window_manager.event_timer_remove(self._timer)
        props = context.scene.nano_banana
        props.is_generating = False

        if self._error:
            props.generation_status = "Reference generation failed"
            self.report({"ERROR"}, f"Reference generation failed: {self._error}")
            return {"CANCELLED"}

        props.generation_status = f"Done: {self._count} reference(s) saved"
        props.generation_progress = 1.0
        self.report({"INFO"}, f"Generated {self._count} reference images.")
        return {"FINISHED"}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        context.scene.nano_banana.is_generating = False
        context.scene.nano_banana.generation_status = "Reference generation cancelled"


class NANOBANANA_OT_browse_references(Operator):
    """Open the reference image cache folder in the OS file manager"""
    bl_idname = "nanobanana.browse_references"
    bl_label = "Browse References"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.nano_banana
        uv_region_id = props.active_uv_region_id
        if not uv_region_id:
            self.report({"WARNING"}, "No UV region selected.")
            return {"CANCELLED"}

        region_dir = get_region_dir(context, uv_region_id)
        ref_dir = os.path.join(region_dir, "references")

        if not os.path.isdir(ref_dir):
            self.report({"INFO"}, "No references cached yet.")
            return {"CANCELLED"}

        bpy.ops.wm.path_open(filepath=ref_dir)
        return {"FINISHED"}


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_generate_references,
    NANOBANANA_OT_browse_references,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
