"""
BlenderNanoBanana - UV Tools Panel

Seam controls, unwrap, pack, island browser with material tag assignment.
Tags assigned here are persistent and used during texture generation.
"""

import json
import bpy
from bpy.types import Panel

_ISLAND_PAGE_SIZE = 8


class NANOBANANA_PT_uv(Panel):
    bl_label = "UV Tools"
    bl_idname = "NANOBANANA_PT_uv"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        obj    = context.active_object
        props  = context.scene.nano_banana

        if obj is None or obj.type != "MESH":
            layout.label(text="Select a mesh object", icon="INFO")
            return

        # ── Seam Controls ─────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Seams", icon="MOD_EDGESPLIT")
        row = box.row(align=True)
        row.operator("nanobanana.mark_seam",  text="Mark Seam",  icon="EDGESEL")
        row.operator("nanobanana.clear_seam", text="Clear Seam", icon="X")

        # ── Unwrap / Pack ─────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Unwrap", icon="UV")
        col = box.column(align=True)
        col.operator("nanobanana.unwrap_uv",   text="Unwrap UV",    icon="MOD_UVPROJECT")
        col.operator("nanobanana.pack_islands", text="Pack Islands", icon="FULLSCREEN_ENTER")

        # ── Island Browser ────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="UV Islands", icon="UV_ISLANDSEL")
        box.operator("nanobanana.analyze_uv_islands",
                     text="Detect Islands", icon="VIEWZOOM")

        uv_data = context.scene.get("nb_uv_analysis")
        if not uv_data:
            box.label(text="Click 'Detect Islands' to scan", icon="DOT")
        else:
            islands = uv_data.get("islands", [])
            total   = len(islands)
            box.label(text=f"{total} island(s) detected", icon="INFO")

            try:
                island_tags = json.loads(props.island_tags_json or "{}")
            except Exception:
                island_tags = {}

            page    = context.scene.get("_nb_island_page", 0)
            page    = max(0, min(page, max(0, (total - 1)) // _ISLAND_PAGE_SIZE))
            start   = page * _ISLAND_PAGE_SIZE
            end     = min(start + _ISLAND_PAGE_SIZE, total)

            for island in islands[start:end]:
                iid        = island.get("id", "?")
                face_count = island.get("face_count", 0)
                is_active  = (iid == props.active_uv_region_id)
                tag_label  = island_tags.get(iid, "")

                row = box.row(align=True)
                icon = "RADIOBUT_ON" if is_active else "RADIOBUT_OFF"
                label = f"{iid}  ({face_count}f)"
                if tag_label:
                    label += f"  ·  {tag_label}"

                op = row.operator("nanobanana.select_uv_island",
                                  text=label, icon=icon, depress=is_active)
                op.island_id = iid

                # Tag indicator dot (colored via alert if tagged)
                if tag_label:
                    row.label(text="", icon="FUND")

            # Pagination
            if total > _ISLAND_PAGE_SIZE:
                max_page = (total - 1) // _ISLAND_PAGE_SIZE
                nav = box.row(align=True)
                op_prev = nav.operator("nanobanana.island_page",
                                       text="", icon="TRIA_LEFT")
                op_prev.delta = -1
                nav.label(text=f"{page + 1} / {max_page + 1}")
                op_next = nav.operator("nanobanana.island_page",
                                       text="", icon="TRIA_RIGHT")
                op_next.delta = 1

        # ── Island Tag Assignment ─────────────────────────────────────────────
        if props.active_uv_region_id:
            box = layout.box()
            active_id = props.active_uv_region_id

            try:
                island_tags = json.loads(props.island_tags_json or "{}")
            except Exception:
                island_tags = {}

            existing_tag = island_tags.get(active_id, "")
            box.label(text=f"Tag: {active_id}", icon="BOOKMARKS")

            if existing_tag:
                row = box.row()
                row.label(text=f"Current:  {existing_tag}", icon="CHECKMARK")
                box.operator("nanobanana.clear_island_tag",
                             text="Remove Tag", icon="X")
                box.separator()
                box.label(text="Change tag:", icon="GREASEPENCIL")

            col = box.column(align=True)
            col.prop(props, "island_tag_input", text="", placeholder="e.g. Skin, Metal Armor, Cloth...")
            row = col.row(align=True)
            row.scale_y = 1.3
            row.enabled = bool(props.island_tag_input.strip())
            row.operator("nanobanana.set_island_tag",
                         text="Save Tag", icon="CHECKMARK")

            # Quick-pick common materials
            box.separator()
            box.label(text="Quick pick:", icon="PRESET")
            grid = box.grid_flow(columns=3, align=True)
            for quick_label in ["Skin", "Metal", "Fabric", "Wood",
                                 "Stone", "Glass", "Leather", "Plastic", "Emission"]:
                op = grid.operator("nanobanana.quick_island_tag", text=quick_label)
                op.tag = quick_label

        # ── Tagged Island Summary ─────────────────────────────────────────────
        try:
            all_tags = json.loads(props.island_tags_json or "{}")
        except Exception:
            all_tags = {}

        if all_tags:
            box = layout.box()
            box.label(text="All Tags:", icon="LINENUMBERS_ON")
            for iid, tag in list(all_tags.items())[:6]:
                row = box.row()
                row.label(text=f"{iid}", icon="UV")
                row.label(text=tag)
            if len(all_tags) > 6:
                box.label(text=f"...and {len(all_tags)-6} more")


def register():
    bpy.utils.register_class(NANOBANANA_PT_uv)


def unregister():
    bpy.utils.unregister_class(NANOBANANA_PT_uv)
