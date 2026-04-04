"""
BlenderNanoBanana - Texture Generation Operators

GenerateTextures: Captures viewport + UV layout, then runs pipeline in background.
CancelGeneration: Sets the cancel flag so the pipeline stops at next checkpoint.
ApplyCachedMaterial: Re-applies latest cached textures as a Blender material.
"""

import threading
import json
import os

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty

from ..core.texture_generator import run_generation_pipeline, request_cancel
from ..core.cache_manager import (
    get_project_name,
    get_cache_base_path,
    set_thread_overrides,
    get_latest_texture_version,
    get_texture_maps_from_version,
)
from ..core.viewport_handler import capture_and_store
from ..core.uv_layout_capture import capture_uv_layout, annotate_uv_layout
from ..utils.mesh_utils import create_pbr_material, apply_material_to_object
from ..utils.preview_manager import load_map_previews
from ..preferences import get_preferences


# Guard: only one generation modal at a time
_modal_active = False


class NANOBANANA_OT_generate_textures(Operator):
    """Generate PBR textures for the active object (runs in background)"""
    bl_idname = "nanobanana.generate_textures"
    bl_label = "Generate Textures"
    bl_options = {"REGISTER"}

    _timer = None
    _thread: threading.Thread = None
    _done: bool = False
    _result = None
    _error: str = None
    _progress: dict = None
    _uv_region_id: str = None

    def execute(self, context):
        prefs = get_preferences(context)
        props = context.scene.nano_banana

        # ── Validate ───────────────────────────────────────────────────────────
        if not prefs.google_api_key:
            self.report({"ERROR"}, "Set your Google API Key in Addon Preferences.")
            return {"CANCELLED"}

        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object.")
            return {"CANCELLED"}

        prompt = props.generation_prompt.strip()
        if not prompt:
            self.report({"WARNING"}, "Enter a texture description.")
            return {"CANCELLED"}

        enabled_maps = [
            m for m in ["albedo", "normal", "roughness", "metallic",
                        "ao", "emission", "height", "displacement"]
            if getattr(props, f"map_{m}", False)
        ]
        if not enabled_maps:
            self.report({"WARNING"}, "Enable at least one map.")
            return {"CANCELLED"}

        # ── Pre-compute everything on main thread ──────────────────────────────
        api_key      = prefs.google_api_key
        engine_id    = props.engine_preset
        project_name = get_project_name(context)
        cache_base   = get_cache_base_path(context)

        # UV region: use selected island if set, otherwise whole-object fallback
        uv_region_id = props.active_uv_region_id or f"uv_{obj.name}"

        # Island tags (persistent, survive prompt changes)
        import json as _json
        try:
            island_tags = _json.loads(props.island_tags_json or "{}")
        except Exception:
            island_tags = {}

        # Build enriched prompt: global description + active island tag
        island_tag = island_tags.get(uv_region_id, "")
        if island_tag:
            enriched_prompt = f"{prompt} — Material zone: {island_tag}"
        elif island_tags:
            zones = ", ".join(f"{k}={v}" for k, v in island_tags.items())
            enriched_prompt = f"{prompt} — UV zones: {zones}"
        else:
            enriched_prompt = prompt

        # Auto-capture viewport screenshot
        viewport_path = capture_and_store(context, project_name)

        # Auto-export UV layout image
        uv_layout_out  = os.path.join(cache_base, project_name, uv_region_id, "uv_layout.png")
        uv_layout_path = capture_uv_layout(context, uv_layout_out)

        # Annotate UV layout with island ID + tag labels (requires Pillow)
        if uv_layout_path:
            uv_data = context.scene.get("nb_uv_analysis")
            if uv_data:
                annotate_uv_layout(
                    image_path=uv_layout_path,
                    islands=uv_data.get("islands", []),
                    island_tags=island_tags,
                )

        set_thread_overrides(cache_base, project_name)

        self._uv_region_id = uv_region_id
        self._done = False
        self._result = None
        self._error = None
        self._progress = {"frac": 0.0, "msg": "Starting..."}

        props.is_generating = True
        props.generation_progress = 0.0
        props.generation_status = "Starting..."

        def progress_cb(frac: float, msg: str):
            self._progress["frac"] = frac
            self._progress["msg"] = msg

        def _run():
            try:
                self._result = run_generation_pipeline(
                    context=context,
                    api_key=api_key,
                    prompt=enriched_prompt,
                    uv_region_id=uv_region_id,
                    engine_id=engine_id,
                    enabled_maps=enabled_maps,
                    progress_cb=progress_cb,
                    viewport_path=viewport_path,
                    uv_layout_path=uv_layout_path,
                )
            except Exception as e:
                self._error = str(e)
            finally:
                self._done = True
                set_thread_overrides(None, None)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

        self._timer = context.window_manager.event_timer_add(0.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        props = context.scene.nano_banana

        if self._progress:
            props.generation_progress = self._progress["frac"]
            props.generation_status   = self._progress["msg"]

        for area in context.screen.areas:
            if area.type in ("VIEW_3D", "IMAGE_EDITOR"):
                area.tag_redraw()

        if not self._done:
            return {"RUNNING_MODAL"}

        # ── Done ──────────────────────────────────────────────────────────────
        context.window_manager.event_timer_remove(self._timer)

        # Don't overwrite if user already cancelled (is_generating already False)
        if props.is_generating:
            props.is_generating = False

        if self._error:
            # Trim to a UI-friendly length
            short = self._error[:180]
            props.generation_status = f"Error: {short}"
            self.report({"ERROR"}, short)
            return {"CANCELLED"}

        if not self._result:
            props.generation_status = "Cancelled"
            return {"CANCELLED"}

        # Apply material
        try:
            mat_name = f"NB_{self._uv_region_id}"
            mat = create_pbr_material(mat_name, self._result)
            obj = context.active_object
            if obj:
                apply_material_to_object(context, obj, mat)
        except Exception as e:
            self.report({"WARNING"}, f"Textures saved but material apply failed: {e}")

        # Store paths + load thumbnails
        props.last_generated_maps_json = json.dumps(self._result)
        try:
            load_map_previews(self._result)
        except Exception:
            pass

        # Auto-load albedo into Image Editor
        _auto_load_to_image_editor(context, self._result)

        maps_str = ", ".join(self._result.keys())
        props.generation_status = f"Done: {maps_str}"
        self.report({"INFO"}, f"Generated: {maps_str}")
        return {"FINISHED"}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        props = context.scene.nano_banana
        props.is_generating = False
        props.generation_status = "Cancelled"


class NANOBANANA_OT_cancel_generation(Operator):
    """Stop the running texture generation — resets UI immediately"""
    bl_idname = "nanobanana.cancel_generation"
    bl_label = "Cancel"
    bl_options = {"REGISTER"}

    def execute(self, context):
        request_cancel()
        # Reset UI immediately — don't wait for the background thread
        props = context.scene.nano_banana
        props.is_generating       = False
        props.generation_status   = "Ready"
        props.generation_progress = 0.0
        return {"FINISHED"}


class NANOBANANA_OT_apply_cached_material(Operator):
    """Re-apply the latest cached textures as a Blender material"""
    bl_idname = "nanobanana.apply_cached_material"
    bl_label = "Apply Cached Material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object.")
            return {"CANCELLED"}

        uv_region_id = f"uv_{obj.name}"
        version_dir = get_latest_texture_version(context, uv_region_id)
        if not version_dir:
            self.report({"WARNING"}, "No cached textures found. Generate first.")
            return {"CANCELLED"}

        texture_paths = get_texture_maps_from_version(version_dir)
        if not texture_paths:
            self.report({"ERROR"}, "Cached version is empty.")
            return {"CANCELLED"}

        mat = create_pbr_material(f"NB_{uv_region_id}", texture_paths)
        apply_material_to_object(context, obj, mat)
        self.report({"INFO"}, f"Material applied ({len(texture_paths)} maps).")
        return {"FINISHED"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auto_load_to_image_editor(context, result: dict):
    priority = ["albedo", "normal", "roughness", "metallic",
                "ao", "emission", "height", "displacement"]
    path = None
    for name in priority:
        p = result.get(name)
        if p and os.path.exists(p):
            path = p
            break
    if not path:
        path = next((p for p in result.values() if p and os.path.exists(p)), None)
    if not path:
        return
    try:
        img = bpy.data.images.load(path, check_existing=True)
        for area in context.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.spaces.active.image = img
                area.tag_redraw()
                break
    except Exception:
        pass


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_generate_textures,
    NANOBANANA_OT_cancel_generation,
    NANOBANANA_OT_apply_cached_material,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
