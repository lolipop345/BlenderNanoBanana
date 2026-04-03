"""
BlenderNanoBanana - Texture Generation Operators

GenerateTextures: Full pipeline → Gemini spec → Nano Banana → Rust → Material.
ApplyMaterial: Re-apply the latest cached textures as a Blender material.
"""

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, StringProperty

from ..core.texture_generator import run_generation_pipeline
from ..core.cache_manager import (
    get_project_name,
    get_latest_texture_version,
    get_texture_maps_from_version,
)
from ..utils.mesh_utils import create_pbr_material, apply_material_to_object
from ..preferences import get_preferences


class NANOBANANA_OT_generate_textures(Operator):
    """Generate PBR textures for the active UV region (full pipeline)"""
    bl_idname = "nanobanana.generate_textures"
    bl_label = "Generate Textures"
    bl_options = {"REGISTER"}

    force_new_spec: BoolProperty(
        name="Force New Spec",
        description="Regenerate Gemini JSON spec (ignore cache)",
        default=False,
    )

    def execute(self, context):
        prefs = get_preferences(context)
        props = context.scene.nano_banana

        # ── Validate prerequisites ─────────────────────────────────────────────
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

        # ── Collect enabled maps ───────────────────────────────────────────────
        enabled_maps = []
        for map_name in ["albedo", "normal", "roughness", "metallic",
                         "ao", "emission", "height", "displacement"]:
            if getattr(props, f"map_{map_name}", False):
                enabled_maps.append(map_name)

        if not enabled_maps:
            self.report({"WARNING"}, "No texture maps selected. Enable at least one map.")
            return {"CANCELLED"}

        engine_id = props.engine_preset

        # ── Set in-progress state ──────────────────────────────────────────────
        props.is_generating = True
        props.generation_progress = 0.0
        props.generation_status = "Starting..."

        def progress_cb(frac: float, msg: str):
            props.generation_progress = frac
            props.generation_status = msg

        # ── Run pipeline ───────────────────────────────────────────────────────
        try:
            result = run_generation_pipeline(
                context=context,
                api_key=prefs.google_api_key,
                uv_region_id=uv_region_id,
                tag_id=tag_id,
                engine_id=engine_id,
                enabled_maps=enabled_maps,
                progress_cb=progress_cb,
                auto_generate_refs=prefs.auto_generate_references,
                force_new_spec=self.force_new_spec,
            )
        except Exception as e:
            self.report({"ERROR"}, f"Generation failed: {e}")
            props.is_generating = False
            props.generation_status = "Error"
            return {"CANCELLED"}
        finally:
            props.is_generating = False

        if result:
            maps_str = ", ".join(result.keys())
            props.generation_status = f"Done: {maps_str}"
            self.report({"INFO"}, f"Textures generated: {maps_str}")
            return {"FINISHED"}
        else:
            props.generation_status = "Failed"
            self.report({"ERROR"}, "Texture generation failed. Check console for details.")
            return {"CANCELLED"}


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
            self.report({"WARNING"}, "No cached textures found for this region. Generate textures first.")
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
