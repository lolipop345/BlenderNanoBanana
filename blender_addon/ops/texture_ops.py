"""
BlenderNanoBanana - Texture Generation Operators

GenerateTextures: Full pipeline in background thread — UI stays responsive.
  1. Validate prerequisites
  2. Start modal operator (RUNNING_MODAL) with timer
  3. Background thread: Gemini spec → Image API → Rust → cache save
  4. Main thread (modal finish): create Blender material + apply to object

ApplyMaterial: Re-apply the latest cached textures as a Blender material.
"""

import threading
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty

import json
import os

from ..core.texture_generator import run_generation_pipeline, request_cancel
from ..core.cache_manager import (
    get_project_name,
    get_cache_base_path,
    set_thread_overrides,
    get_latest_texture_version,
    get_texture_maps_from_version,
)
from ..core.viewport_handler import capture_and_store, get_latest_capture
from ..core.uv_layout_capture import capture_uv_layout
from ..utils.mesh_utils import create_pbr_material, apply_material_to_object
from ..utils.preview_manager import load_map_previews
from ..preferences import get_preferences


class NANOBANANA_OT_generate_textures(Operator):
    """Generate PBR textures for the active UV region (runs in background)"""
    bl_idname = "nanobanana.generate_textures"
    bl_label = "Generate Textures"
    bl_options = {"REGISTER"}

    force_new_spec: BoolProperty(
        name="Force New Spec",
        description="Regenerate Gemini JSON spec (ignore cache)",
        default=False,
    )

    # ── Per-instance thread state ──────────────────────────────────────────────
    _timer = None
    _thread: threading.Thread = None
    _done: bool = False
    _result = None      # dict of map_name → file_path, or None
    _error: str = None
    _progress: dict = None  # {"frac": float, "msg": str}
    # Capture state needed for material creation on main thread
    _mat_name: str = None
    _uv_region_id: str = None

    def execute(self, context):
        prefs = get_preferences(context)
        props = context.scene.nano_banana

        # ── Validate ───────────────────────────────────────────────────────────
        if not prefs.google_api_key:
            self.report({"ERROR"}, "Google API Key not set in Addon Preferences.")
            return {"CANCELLED"}

        uv_region_id = props.active_uv_region_id
        if not uv_region_id:
            self.report({"WARNING"}, "No UV region selected. Analyze UV Islands first.")
            return {"CANCELLED"}

        tag_id = props.active_semantic_tag
        if not tag_id or tag_id == "none":
            self.report({"WARNING"}, "No semantic tag selected.")
            return {"CANCELLED"}

        enabled_maps = [
            m for m in ["albedo", "normal", "roughness", "metallic",
                        "ao", "emission", "height", "displacement"]
            if getattr(props, f"map_{m}", False)
        ]
        if not enabled_maps:
            self.report({"WARNING"}, "No texture maps selected.")
            return {"CANCELLED"}

        engine_id = props.engine_preset

        # ── Pre-compute all bpy-dependent values on main thread ───────────────
        # Background threads must NOT call bpy.context — pre-extract everything here.
        api_key = prefs.google_api_key
        force_new_spec = self.force_new_spec
        project_name = get_project_name(context)
        cache_base = get_cache_base_path(context)

        # Auto-capture viewport if no capture exists yet
        viewport_path = get_latest_capture(context, project_name)
        if not viewport_path:
            viewport_path = capture_and_store(context, project_name)

        # Capture UV layout for AI context (main thread only)
        uv_layout_out = os.path.join(
            cache_base, project_name, uv_region_id, "uv_layout.png"
        )
        uv_layout_path = capture_uv_layout(context, uv_layout_out)

        # Set thread-safe overrides so cache_manager doesn't touch bpy.context
        set_thread_overrides(cache_base, project_name)

        self._mat_name = f"NB_{uv_region_id}_{tag_id}_{engine_id}"
        self._uv_region_id = uv_region_id
        self._done = False
        self._result = None
        self._error = None
        self._progress = {"frac": 0.0, "msg": "Starting..."}

        # Mark generating
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
                    uv_region_id=uv_region_id,
                    tag_id=tag_id,
                    engine_id=engine_id,
                    enabled_maps=enabled_maps,
                    progress_cb=progress_cb,
                    auto_generate_refs=auto_gen_refs,
                    force_new_spec=force_new_spec,
                    viewport_path=viewport_path,
                    uv_layout_path=uv_layout_path,
                )
            except Exception as e:
                self._error = str(e)
            finally:
                self._done = True
                # Clear thread overrides so main thread bpy access works normally
                set_thread_overrides(None, None)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

        # Start polling timer (every 0.25s)
        self._timer = context.window_manager.event_timer_add(0.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        props = context.scene.nano_banana

        # Push latest progress from thread → scene props → UI
        if self._progress:
            props.generation_progress = self._progress["frac"]
            props.generation_status = self._progress["msg"]

        # Redraw panels
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        if not self._done:
            return {"RUNNING_MODAL"}

        # ── Thread finished — back on main thread ──────────────────────────────
        context.window_manager.event_timer_remove(self._timer)
        props.is_generating = False

        if self._error:
            props.generation_status = "Error"
            self.report({"ERROR"}, f"Generation failed: {self._error}")
            return {"CANCELLED"}

        if not self._result:
            props.generation_status = "Failed"
            self.report({"ERROR"}, "Texture generation failed. Check console.")
            return {"CANCELLED"}

        # Create + apply Blender material on main thread
        try:
            mat = create_pbr_material(self._mat_name, self._result)
            obj = context.active_object
            if obj:
                apply_material_to_object(context, obj, mat)
        except Exception as e:
            self.report({"WARNING"}, f"Textures saved but material apply failed: {e}")

        # Store generated map paths in scene props for preview panel
        props.last_generated_maps_json = json.dumps(self._result)

        # Load thumbnails into preview collection
        try:
            load_map_previews(self._result)
        except Exception:
            pass

        # Auto-load albedo (or first available map) into Image Editor
        _auto_load_to_image_editor(context, self._result)

        maps_str = ", ".join(self._result.keys())
        props.generation_status = f"Done: {maps_str}"
        self.report({"INFO"}, f"Textures generated: {maps_str}")
        return {"FINISHED"}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        context.scene.nano_banana.is_generating = False
        context.scene.nano_banana.generation_status = "Cancelled"


def _auto_load_to_image_editor(context, result: dict):
    """Load the best available generated map into any open Image Editor area."""
    import bpy as _bpy
    # Prefer albedo, fall back to the first available map
    priority = ["albedo", "normal", "roughness", "metallic", "ao",
                "emission", "height", "displacement"]
    chosen_path = None
    for map_name in priority:
        p = result.get(map_name)
        if p and os.path.exists(p):
            chosen_path = p
            break
    if not chosen_path:
        for p in result.values():
            if p and os.path.exists(p):
                chosen_path = p
                break

    if not chosen_path:
        return

    try:
        img = _bpy.data.images.load(chosen_path, check_existing=True)
        for area in context.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.spaces.active.image = img
                area.tag_redraw()
                break
    except Exception:
        pass


class NANOBANANA_OT_apply_cached_material(Operator):
    """Apply the latest cached textures as a Blender material to the active object"""
    bl_idname = "nanobanana.apply_cached_material"
    bl_label = "Apply Cached Material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.nano_banana
        uv_region_id = props.active_uv_region_id

        if not uv_region_id:
            self.report({"WARNING"}, "No UV region selected.")
            return {"CANCELLED"}

        version_dir = get_latest_texture_version(context, uv_region_id)
        if not version_dir:
            self.report({"WARNING"}, "No cached textures found. Generate textures first.")
            return {"CANCELLED"}

        texture_paths = get_texture_maps_from_version(version_dir)
        if not texture_paths:
            self.report({"ERROR"}, "Cached version directory is empty.")
            return {"CANCELLED"}

        tag_id = props.active_semantic_tag or "unknown"
        engine_id = props.engine_preset or "custom"
        mat_name = f"NB_{uv_region_id}_{tag_id}_{engine_id}"

        mat = create_pbr_material(mat_name, texture_paths)
        obj = context.active_object
        if obj:
            apply_material_to_object(context, obj, mat)
            self.report({"INFO"}, f"Material '{mat_name}' applied.")
            return {"FINISHED"}

        self.report({"WARNING"}, "No active object to assign material to.")
        return {"CANCELLED"}


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_generate_textures,
    NANOBANANA_OT_apply_cached_material,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
