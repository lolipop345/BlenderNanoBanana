"""
BlenderNanoBanana - Main Generate Panel

One panel. Prompt → Maps → Generate. That's it.
"""

import bpy
from bpy.types import Panel


class NANOBANANA_PT_generate(Panel):
    bl_label = "Nano Banana"
    bl_idname = "NANOBANANA_PT_generate"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        props  = context.scene.nano_banana
        obj    = context.active_object

        if not obj or obj.type != "MESH":
            layout.label(text="Select a mesh object", icon="MESH_DATA")
            return

        layout.label(text=f"Object: {obj.name}", icon="OBJECT_DATA")
        layout.separator()

        # ── Prompt ────────────────────────────────────────────────────────────
        col = layout.column(align=True)
        row = col.row(align=True)
        row.label(text="Texture description:", icon="TEXT")
        row.operator("nanobanana.auto_describe", text="", icon="EYEDROPPER",
                     emboss=True)
        col.prop(props, "generation_prompt", text="")

        layout.separator()

        # ── Map toggles ───────────────────────────────────────────────────────
        col = layout.column(align=True)
        col.label(text="Maps to generate:", icon="IMAGE_DATA")

        row = col.row(align=True)
        row.prop(props, "map_albedo",    toggle=True, text="Albedo")
        row.prop(props, "map_normal",    toggle=True, text="Normal")
        row.prop(props, "map_roughness", toggle=True, text="Roughness")

        row = col.row(align=True)
        row.prop(props, "map_metallic",  toggle=True, text="Metallic")
        row.prop(props, "map_ao",        toggle=True, text="AO")
        row.prop(props, "map_emission",  toggle=True, text="Emission")

        # ── Active island tag context ─────────────────────────────────────────
        import json as _json
        try:
            island_tags = _json.loads(props.island_tags_json or "{}")
        except Exception:
            island_tags = {}

        active_island = props.active_uv_region_id
        if active_island and island_tags.get(active_island):
            row = layout.row()
            row.alert = False
            row.label(
                text=f"Island: {active_island}  ·  {island_tags[active_island]}",
                icon="BOOKMARKS",
            )
        elif island_tags:
            # Show summary of all tagged islands
            box = layout.box()
            box.label(text="Tagged zones (all used as context):", icon="LINENUMBERS_ON")
            for iid, tag in list(island_tags.items())[:4]:
                box.label(text=f"  {iid}: {tag}", icon="UV")
            if len(island_tags) > 4:
                box.label(text=f"  ...and {len(island_tags)-4} more")

        layout.separator()

        # ── Engine ────────────────────────────────────────────────────────────
        row = layout.row(align=True)
        row.label(text="Engine:", icon="WORLD_DATA")
        row.prop(props, "engine_preset", text="")

        layout.separator()

        # ── Generate / Cancel ─────────────────────────────────────────────────
        from ..preferences import get_preferences
        prefs = get_preferences(context)

        can_generate = (
            bool(prefs.google_api_key) and
            bool(props.generation_prompt.strip()) and
            any(getattr(props, f"map_{m}", False)
                for m in ["albedo", "normal", "roughness", "metallic",
                          "ao", "emission", "height", "displacement"])
        )

        if props.is_generating:
            # Progress
            try:
                layout.progress(factor=props.generation_progress,
                                text=props.generation_status)
            except Exception:
                pct = int(props.generation_progress * 100)
                layout.label(text=f"{pct}%  {props.generation_status}")

            cancel_row = layout.row()
            cancel_row.alert = True
            cancel_row.scale_y = 1.4
            cancel_row.operator("nanobanana.cancel_generation",
                                text="Cancel", icon="X")
        else:
            btn_row = layout.row()
            btn_row.scale_y = 2.0
            btn_row.enabled = can_generate
            btn_row.operator("nanobanana.generate_textures",
                             text="Generate" if can_generate else "Generate  (fill prompt & maps)",
                             icon="RENDER_STILL")

            if not prefs.google_api_key:
                row = layout.row()
                row.alert = True
                row.label(text="API Key missing — check Preferences", icon="ERROR")

        # ── Generated previews ────────────────────────────────────────────────
        import json as _json, os as _os
        try:
            last_maps = _json.loads(props.last_generated_maps_json or "{}")
        except Exception:
            last_maps = {}

        last_maps = {k: v for k, v in last_maps.items() if v and _os.path.isfile(v)}

        if last_maps:
            layout.separator()
            box = layout.box()
            row = box.row()
            row.label(text="Generated Maps", icon="IMAGE_DATA")
            row.operator("nanobanana.apply_cached_material",
                         text="Apply Material", icon="MATERIAL")

            from ..utils.preview_manager import get_icon_id
            grid = box.grid_flow(row_major=True, columns=3,
                                 even_columns=True, even_rows=True, align=True)
            for map_name in last_maps:
                icon_id = get_icon_id(map_name)
                col = grid.column(align=True)
                if icon_id:
                    col.template_icon(icon_value=icon_id, scale=3.5)
                col.label(text=map_name.capitalize())


def register():
    bpy.utils.register_class(NANOBANANA_PT_generate)


def unregister():
    bpy.utils.unregister_class(NANOBANANA_PT_generate)
