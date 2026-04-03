"""
BlenderNanoBanana - Semantic Tagging Operators

ApplySemanticTag: Associate a tag with the active UV region.
EditCustomTag: Create/edit a custom tag definition.
RemoveCustomTag: Remove a custom tag.
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty

from ..core.semantic_manager import (
    apply_tag_to_region,
    get_tag,
    add_custom_tag,
    remove_custom_tag,
)
from ..core.project_manager import record_tag_assignment
from ..core.cache_manager import get_project_name


class NANOBANANA_OT_apply_semantic_tag(Operator):
    """Apply the selected semantic tag to the active UV region"""
    bl_idname = "nanobanana.apply_semantic_tag"
    bl_label = "Apply Tag"
    bl_options = {"REGISTER", "UNDO"}

    tag_id: StringProperty(
        name="Tag ID",
        description="Semantic tag identifier to apply",
        default="",
    )

    def execute(self, context):
        props = context.scene.nano_banana
        tag_id = self.tag_id or props.active_semantic_tag
        uv_region_id = props.active_uv_region_id

        if not tag_id:
            self.report({"WARNING"}, "No semantic tag selected.")
            return {"CANCELLED"}

        if not uv_region_id:
            self.report({"WARNING"}, "No UV region selected. Use Analyze UV Islands first.")
            return {"CANCELLED"}

        tag = get_tag(tag_id)
        if tag is None:
            self.report({"ERROR"}, f"Unknown tag: '{tag_id}'")
            return {"CANCELLED"}

        project_name = get_project_name(context)
        apply_tag_to_region(context, uv_region_id, tag_id, project_name)
        record_tag_assignment(context, uv_region_id, tag_id)

        self.report({"INFO"}, f"Tag '{tag['name']}' applied to region '{uv_region_id}'.")
        return {"FINISHED"}


class NANOBANANA_OT_add_custom_tag(Operator):
    """Add a custom semantic tag"""
    bl_idname = "nanobanana.add_custom_tag"
    bl_label = "Add Custom Tag"
    bl_options = {"REGISTER"}

    tag_id: StringProperty(name="Tag ID", default="custom_tag")
    tag_name: StringProperty(name="Display Name", default="Custom Tag")
    tag_description: StringProperty(name="Description", default="")
    detail_level: EnumProperty(
        name="Detail Level",
        items=[
            ("low", "Low", ""),
            ("medium", "Medium", ""),
            ("high", "High", ""),
            ("ultra", "Ultra", ""),
        ],
        default="medium",
    )
    realism: EnumProperty(
        name="Realism",
        items=[
            ("photorealistic", "Photorealistic", ""),
            ("realistic", "Realistic", ""),
            ("stylized", "Stylized", ""),
            ("cartoon", "Cartoon", ""),
        ],
        default="realistic",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "tag_id")
        layout.prop(self, "tag_name")
        layout.prop(self, "tag_description")
        layout.prop(self, "detail_level")
        layout.prop(self, "realism")

    def execute(self, context):
        if not self.tag_id:
            self.report({"ERROR"}, "Tag ID cannot be empty.")
            return {"CANCELLED"}

        tag_def = {
            "id": self.tag_id,
            "name": self.tag_name,
            "category": "custom",
            "description": self.tag_description,
            "detail_level": self.detail_level,
            "realism": self.realism,
            "special_notes": "",
            "gemini_hints": {},
        }

        success = add_custom_tag(self.tag_id, tag_def)
        if success:
            self.report({"INFO"}, f"Custom tag '{self.tag_id}' added.")
            return {"FINISHED"}
        self.report({"ERROR"}, "Failed to add custom tag.")
        return {"CANCELLED"}


class NANOBANANA_OT_remove_custom_tag(Operator):
    """Remove a custom semantic tag"""
    bl_idname = "nanobanana.remove_custom_tag"
    bl_label = "Remove Custom Tag"
    bl_options = {"REGISTER"}

    tag_id: StringProperty(name="Tag ID", default="")

    def execute(self, context):
        if remove_custom_tag(self.tag_id):
            self.report({"INFO"}, f"Custom tag '{self.tag_id}' removed.")
            return {"FINISHED"}
        self.report({"WARNING"}, f"Tag '{self.tag_id}' not found or is a standard tag.")
        return {"CANCELLED"}


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_apply_semantic_tag,
    NANOBANANA_OT_add_custom_tag,
    NANOBANANA_OT_remove_custom_tag,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
