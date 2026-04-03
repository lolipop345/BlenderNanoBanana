"""
BlenderNanoBanana - Reference Image Operators

GenerateReferences: Generate reference images for the active UV region.
BrowseReferences: Open the cache folder in the OS file manager.
ClearReferences: Delete cached references for the active region.
"""

import bpy
import os
from bpy.types import Operator
from bpy.props import BoolProperty, IntProperty

from ..core.reference_generator import generate_references
from ..core.semantic_manager import get_tag_for_region
from ..core.cache_manager import get_project_name, get_region_dir, get_reference_images
from ..preferences import get_preferences


class NANOBANANA_OT_generate_references(Operator):
    """Generate reference images for the active UV region via Nano Banana"""
    bl_idname = "nanobanana.generate_references"
    bl_label = "Generate References"
    bl_options = {"REGISTER"}

    count: IntProperty(
        name="Count",
        description="Number of reference images to generate",
        default=3,
        min=1,
        max=10,
    )
    force: BoolProperty(
        name="Force Regenerate",
        description="Generate new references even if cached ones exist",
        default=False,
    )

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
            self.report({"WARNING"}, "No semantic tag applied to this region. Apply a tag first.")
            return {"CANCELLED"}

        tag_def = tag_data.get("tag_definition", {})

        self.report({"INFO"}, f"Generating {self.count} reference images...")

        saved = generate_references(
            context=context,
            api_key=prefs.google_api_key,
            uv_region_id=uv_region_id,
            tag_definition=tag_def,
            project_name=project_name,
            count=self.count,
        )

        self.report({"INFO"}, f"Generated {len(saved)} reference images.")
        return {"FINISHED"}


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
