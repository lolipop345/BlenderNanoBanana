"""
BlenderNanoBanana - Model Operators

AutoDescribe: Captures viewport + UV layout on main thread, then calls
Gemini in a background thread (modal + timer) so Blender never freezes.
"""

import os
import threading

import bpy
from bpy.types import Operator

from ..core.model_analyzer import analyze_active_mesh
from ..core.viewport_handler import capture_and_store
from ..core.cache_manager import get_project_name, get_cache_base_path


class NANOBANANA_OT_read_model(Operator):
    """Analyze the active mesh and display info in the Model panel"""
    bl_idname = "nanobanana.read_model"
    bl_label = "Read Model"
    bl_options = {"REGISTER"}

    def execute(self, context):
        result = analyze_active_mesh(context)
        if result is None:
            self.report({"WARNING"}, "No active mesh found. Select a mesh object.")
            return {"CANCELLED"}

        context.scene["nb_model_data"] = result
        self.report({"INFO"},
                    f"Model: {result['vertex_count']} verts, "
                    f"{result['face_count']} faces, "
                    f"symmetry={result['has_symmetry']}")
        return {"FINISHED"}


class NANOBANANA_OT_capture_viewport(Operator):
    """Capture the current 3D viewport as a reference context image"""
    bl_idname = "nanobanana.capture_viewport"
    bl_label = "Capture Viewport"
    bl_options = {"REGISTER"}

    def execute(self, context):
        project_name = get_project_name(context)
        path = capture_and_store(context, project_name)
        if path:
            self.report({"INFO"}, f"Viewport captured: {path}")
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, "Viewport capture failed.")
            return {"CANCELLED"}


class NANOBANANA_OT_auto_describe(Operator):
    """Analyse the active mesh with AI and fill in the texture description (non-blocking)"""
    bl_idname = "nanobanana.auto_describe"
    bl_label = "Auto Describe"
    bl_options = {"REGISTER"}

    _timer = None
    _thread: threading.Thread = None
    _result: str = None
    _error: str = None
    _done: bool = False

    def execute(self, context):
        from ..preferences import get_preferences
        prefs = get_preferences(context)

        if not prefs.google_api_key:
            self.report({"ERROR"}, "Set your Google API Key in Preferences.")
            return {"CANCELLED"}

        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object.")
            return {"CANCELLED"}

        # ── Main thread: capture images (bpy.ops required) ─────────────────────
        project_name = get_project_name(context)
        cache_base   = get_cache_base_path(context)

        viewport_path = capture_and_store(context, project_name)

        from ..core.uv_layout_capture import capture_uv_layout
        uv_out  = os.path.join(cache_base, project_name, f"uv_{obj.name}", "uv_layout.png")
        uv_path = capture_uv_layout(context, uv_out)

        api_key = prefs.google_api_key

        # ── Background thread: Gemini API call ─────────────────────────────────
        self._result = None
        self._error  = None
        self._done   = False

        def _run():
            try:
                from ..core.prompt_engineer import get_mesh_description
                desc = get_mesh_description(
                    api_key=api_key,
                    viewport_image_path=viewport_path,
                    uv_layout_path=uv_path,
                )
                self._result = desc or ""
            except Exception as e:
                self._error = str(e)
            finally:
                self._done = True

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

        # Show a status hint
        context.scene.nano_banana.generation_status = "Describing mesh..."

        self._timer = context.window_manager.event_timer_add(0.2, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        if not self._done:
            return {"RUNNING_MODAL"}

        # ── Done ───────────────────────────────────────────────────────────────
        context.window_manager.event_timer_remove(self._timer)
        context.scene.nano_banana.generation_status = "Ready"

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        if self._error:
            self.report({"ERROR"}, f"Auto describe failed: {self._error[:120]}")
            return {"CANCELLED"}

        if self._result:
            context.scene.nano_banana.generation_prompt = self._result
            self.report({"INFO"}, f"Description: {self._result[:80]}...")
        else:
            self.report({"WARNING"}, "AI returned no description.")

        return {"FINISHED"}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        context.scene.nano_banana.generation_status = "Ready"


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_read_model,
    NANOBANANA_OT_capture_viewport,
    NANOBANANA_OT_auto_describe,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
