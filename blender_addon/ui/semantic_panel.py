"""
BlenderNanoBanana - Semantic Tagging Panel

Tag selector, tag definition viewer, apply button, custom tag management.
"""

import bpy
from bpy.types import Panel


class NANOBANANA_PT_semantic(Panel):
    bl_label = "Semantic Tags"
    bl_idname = "NANOBANANA_PT_semantic"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        props = context.scene.nano_banana

        # ── Active Region ──────────────────────────────────────────────────────
        if not props.active_uv_region_id:
            box = layout.box()
            box.label(text="Select a UV region first", icon="INFO")
            box.label(text="UV Mapping → Detect Islands", icon="ARROW_LEFTRIGHT")
            return

        box = layout.box()
        row = box.row()
        row.label(text=f"Region: {props.active_uv_region_id}", icon="UV_ISLANDSEL")

        # ── Tag Selector ───────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Select Tag", icon="BOOKMARKS")
        box.prop(props, "active_semantic_tag", text="")

        # Show tag info
        from ..core.semantic_manager import get_tag
        tag = get_tag(props.active_semantic_tag) if props.active_semantic_tag else None

        if tag:
            info_box = layout.box()
            info_box.label(text=tag.get("name", ""), icon="INFO")

            col = info_box.column(align=True)
            col.label(text=tag.get("description", ""), icon="DOT")

            row = info_box.row(align=True)
            row.label(text=f"Detail: {tag.get('detail_level', '—')}")
            row.label(text=f"Realism: {tag.get('realism', '—')}")

            notes = tag.get("special_notes", "")
            if notes:
                note_box = info_box.box()
                note_box.label(text="Notes:", icon="TEXT")
                # Word-wrap long notes
                for line in _wrap_text(notes, 36):
                    note_box.label(text=line)

            hints = tag.get("gemini_hints", {})
            if hints:
                hint_box = info_box.box()
                hint_box.label(text="Gemini Hints:", icon="RNA")
                for k, v in hints.items():
                    hint_box.label(text=f"{k}: {v}", icon="DOT")

        # ── Apply Button ───────────────────────────────────────────────────────
        col = layout.column()
        col.scale_y = 1.4
        col.operator("nanobanana.apply_semantic_tag", icon="CHECKMARK")

        # ── Custom Tags ────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Custom Tags", icon="ADD")
        row = box.row(align=True)
        row.operator("nanobanana.add_custom_tag", text="Add", icon="ADD")


def _wrap_text(text: str, max_chars: int):
    """Simple word-wrap for panel labels."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def register():
    bpy.utils.register_class(NANOBANANA_PT_semantic)


def unregister():
    bpy.utils.unregister_class(NANOBANANA_PT_semantic)
