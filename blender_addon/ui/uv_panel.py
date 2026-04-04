"""
BlenderNanoBanana - UV Management Panel

Seam marking controls, unwrap, pack, UV island browser.
"""

import bpy
from bpy.types import Panel

_ISLAND_PAGE_SIZE = 8


class NANOBANANA_PT_uv(Panel):
    bl_label = "UV Mapping"
    bl_idname = "NANOBANANA_PT_uv"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        if obj is None or obj.type != "MESH":
            layout.label(text="Select a mesh object", icon="INFO")
            return

        # ── Seam Controls ─────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Seams", icon="MOD_EDGESPLIT")
        row = box.row(align=True)
        row.operator("nanobanana.mark_seam", text="Mark Seam", icon="EDGESEL")
        row.operator("nanobanana.clear_seam", text="Clear Seam", icon="X")

        # ── Unwrap ─────────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Unwrap", icon="UV")

        col = box.column(align=True)
        col.operator("nanobanana.unwrap_uv", icon="MOD_UVPROJECT")
        col.operator("nanobanana.pack_islands", icon="FULLSCREEN_ENTER")

        # ── UV Islands ────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="UV Islands", icon="UV_ISLANDSEL")
        box.operator("nanobanana.analyze_uv_islands", text="Detect Islands", icon="VIEWZOOM")

        uv_data = context.scene.get("nb_uv_analysis")
        if not uv_data:
            box.label(text="Click 'Detect Islands' to scan", icon="DOT")
            return

        islands = uv_data.get("islands", [])
        total = len(islands)
        box.label(text=f"{total} island(s) detected", icon="INFO")

        props = context.scene.nano_banana

        # Current page (stored as a custom scene dict prop — no registration needed)
        page = context.scene.get("_nb_island_page", 0)
        page = max(0, min(page, (total - 1) // _ISLAND_PAGE_SIZE))

        start = page * _ISLAND_PAGE_SIZE
        end = min(start + _ISLAND_PAGE_SIZE, total)

        for island in islands[start:end]:
            iid = island.get("id", "?")
            face_count = island.get("face_count", 0)
            is_active = (iid == props.active_uv_region_id)

            row = box.row(align=True)
            icon = "RADIOBUT_ON" if is_active else "RADIOBUT_OFF"
            op = row.operator("nanobanana.select_uv_island",
                              text=f"{iid}  ({face_count}f)",
                              icon=icon,
                              depress=is_active)
            op.island_id = iid

        # Pagination controls
        if total > _ISLAND_PAGE_SIZE:
            max_page = (total - 1) // _ISLAND_PAGE_SIZE
            nav = box.row(align=True)
            op_prev = nav.operator("nanobanana.island_page", text="", icon="TRIA_LEFT")
            op_prev.delta = -1
            nav.label(text=f"{page + 1} / {max_page + 1}")
            op_next = nav.operator("nanobanana.island_page", text="", icon="TRIA_RIGHT")
            op_next.delta = 1


def register():
    bpy.utils.register_class(NANOBANANA_PT_uv)


def unregister():
    bpy.utils.unregister_class(NANOBANANA_PT_uv)
