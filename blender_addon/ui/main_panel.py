"""
BlenderNanoBanana - Main Control Panel

Top-level panel in View3D sidebar.
Shows project status, quick actions, and generation progress.
"""

import bpy
from bpy.types import Panel


class NANOBANANA_PT_main(Panel):
    bl_label = "Nano Banana"
    bl_idname = "NANOBANANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        props = context.scene.nano_banana

        # ── Project Info ───────────────────────────────────────────────────────
        from ..core.cache_manager import get_project_name
        project_name = get_project_name(context)

        box = layout.box()
        row = box.row()
        row.label(text="Project", icon="FILE_BLEND")
        box.label(text=project_name, icon="DOT")

        # ── Quick Actions ──────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Quick Actions", icon="TOOL_SETTINGS")

        col = box.column(align=True)
        col.operator("nanobanana.read_model", icon="MESH_DATA")
        col.operator("nanobanana.capture_viewport", icon="CAMERA_DATA")
        col.operator("nanobanana.analyze_uv_islands", icon="UV")

        # ── Active Region Info ─────────────────────────────────────────────────
        if props.active_uv_region_id:
            box = layout.box()
            box.label(text="Active Region", icon="UV_ISLANDSEL")
            row = box.row()
            row.label(text=props.active_uv_region_id, icon="DOT")

            # Show applied tag
            from ..core.semantic_manager import get_tag
            tag = get_tag(props.active_semantic_tag) if props.active_semantic_tag else None
            if tag:
                row = box.row()
                row.label(text=f"Tag: {tag['name']}", icon="BOOKMARKS")

        # ── Generation Progress ────────────────────────────────────────────────
        if props.is_generating:
            box = layout.box()
            box.label(text="Generating...", icon="TIME")
            try:
                box.progress(factor=props.generation_progress, text=props.generation_status)
            except Exception:
                pct = int(props.generation_progress * 100)
                box.label(text=f"{pct}%  {props.generation_status}")
        elif props.generation_status and props.generation_status != "Ready":
            box = layout.box()
            row = box.row()
            icon = "CHECKMARK" if "Done" in props.generation_status else "INFO"
            row.label(text=props.generation_status, icon=icon)

        # ── Overlay Toggles ────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Overlay", icon="OVERLAY")
        row = box.row()
        row.prop(props, "show_uv_overlay", text="UV Overlay", toggle=True)
        row.prop(props, "show_semantic_labels", text="Labels", toggle=True)


def register():
    bpy.utils.register_class(NANOBANANA_PT_main)


def unregister():
    bpy.utils.unregister_class(NANOBANANA_PT_main)
