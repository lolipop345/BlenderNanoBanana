"""
BlenderNanoBanana - UV Management Panel

Seam marking controls, unwrap, pack, UV island browser.
"""

import bpy
from bpy.types import Panel


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
        op = col.operator("nanobanana.unwrap_uv", icon="MOD_UVPROJECT")
        col.operator("nanobanana.pack_islands", icon="FULLSCREEN_ENTER")

        # ── UV Islands ────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="UV Islands", icon="UV_ISLANDSEL")
        box.operator("nanobanana.analyze_uv_islands", text="Detect Islands", icon="VIEWZOOM")

        uv_data = context.scene.get("nb_uv_analysis")
        if uv_data:
            islands = uv_data.get("islands", [])
            count = uv_data.get("island_count", len(islands))
            box.label(text=f"{count} island(s) detected", icon="INFO")

            props = context.scene.nano_banana

            for island in islands[:8]:  # Show max 8 in panel
                iid = island.get("id", "?")
                area = island.get("area", 0.0)
                is_active = (iid == props.active_uv_region_id)

                row = box.row(align=True)
                icon = "RADIOBUT_ON" if is_active else "RADIOBUT_OFF"
                op = row.operator("wm.context_set_string",
                                  text=f"{iid}  ({area:.3f})",
                                  icon=icon,
                                  depress=is_active)
                op.data_path = "scene.nano_banana.active_uv_region_id"
                op.value = iid

            if len(islands) > 8:
                box.label(text=f"...and {len(islands) - 8} more", icon="DOT")
        else:
            box.label(text="Click 'Detect Islands' to scan", icon="DOT")


def register():
    bpy.utils.register_class(NANOBANANA_PT_uv)


def unregister():
    bpy.utils.unregister_class(NANOBANANA_PT_uv)
