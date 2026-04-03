"""
BlenderNanoBanana - Model Information Panel

Shows mesh stats, symmetry info, material list.
"""

import bpy
from bpy.types import Panel


class NANOBANANA_PT_model(Panel):
    bl_label = "Model Info"
    bl_idname = "NANOBANANA_PT_model"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 1
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        if obj is None or obj.type != "MESH":
            layout.label(text="Select a mesh object", icon="INFO")
            layout.operator("nanobanana.read_model", icon="MESH_DATA")
            return

        # ── Mesh Stats ─────────────────────────────────────────────────────────
        model_data = context.scene.get("nb_model_data")

        col = layout.column(align=True)
        col.operator("nanobanana.read_model", icon="FILE_REFRESH", text="Refresh Analysis")

        if model_data:
            box = layout.box()
            box.label(text="Mesh Statistics", icon="MESH_DATA")

            grid = box.grid_flow(columns=2, align=True)
            grid.label(text="Vertices:")
            grid.label(text=str(model_data.get("vertex_count", "—")))
            grid.label(text="Faces:")
            grid.label(text=str(model_data.get("face_count", "—")))
            grid.label(text="Seams:")
            grid.label(text=str(model_data.get("seam_count", "—")))
            grid.label(text="Manifold:")
            grid.label(text="Yes" if model_data.get("is_manifold") else "No")

            # Symmetry
            box2 = layout.box()
            box2.label(text="Symmetry", icon="MOD_MIRROR")
            if model_data.get("has_symmetry"):
                row = box2.row()
                row.label(text=f"✓ {model_data.get('symmetry_axis', 'X')}-axis symmetry",
                          icon="CHECKMARK")
            else:
                box2.label(text="No symmetry detected", icon="X")

            # Bounds
            bounds = model_data.get("bounds")
            if bounds:
                box3 = layout.box()
                box3.label(text="Bounding Box", icon="CUBE")
                mn = bounds.get("min", [0, 0, 0])
                mx = bounds.get("max", [0, 0, 0])
                box3.label(text=f"Min: ({mn[0]:.2f}, {mn[1]:.2f}, {mn[2]:.2f})")
                box3.label(text=f"Max: ({mx[0]:.2f}, {mx[1]:.2f}, {mx[2]:.2f})")

        else:
            box = layout.box()
            box.label(text="Click 'Refresh Analysis' to scan mesh", icon="INFO")

        # ── Viewport Capture ───────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Viewport Context", icon="CAMERA_DATA")
        box.operator("nanobanana.capture_viewport", icon="RENDER_STILL")


def register():
    bpy.utils.register_class(NANOBANANA_PT_model)


def unregister():
    bpy.utils.unregister_class(NANOBANANA_PT_model)
