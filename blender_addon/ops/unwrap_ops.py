"""
BlenderNanoBanana - UV Unwrap Operators

MarkSeam: Mark selected edges as UV seams.
ClearSeam: Remove seams from selected edges.
UnwrapUV: Execute UV unwrap.
PackIslands: Pack UV islands.
AnalyzeUVIslands: Detect islands and update overlay.
"""

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty, IntProperty

from ..core.unwrap_engine import mark_seam, clear_seam, unwrap_uv, pack_islands
from ..core.uv_analyzer import analyze_uv_islands


class NANOBANANA_OT_mark_seam(Operator):
    """Mark selected edges as UV seams"""
    bl_idname = "nanobanana.mark_seam"
    bl_label = "Mark Seam"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        success = mark_seam(context)
        if success:
            self.report({"INFO"}, "Seams marked.")
            return {"FINISHED"}
        self.report({"WARNING"}, "No edges selected.")
        return {"CANCELLED"}


class NANOBANANA_OT_clear_seam(Operator):
    """Clear UV seams from selected edges"""
    bl_idname = "nanobanana.clear_seam"
    bl_label = "Clear Seam"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        success = clear_seam(context)
        if success:
            self.report({"INFO"}, "Seams cleared.")
            return {"FINISHED"}
        return {"CANCELLED"}


class NANOBANANA_OT_unwrap_uv(Operator):
    """Unwrap UV for the active mesh using marked seams"""
    bl_idname = "nanobanana.unwrap_uv"
    bl_label = "Unwrap UV"
    bl_options = {"REGISTER", "UNDO"}

    method: EnumProperty(
        name="Method",
        items=[
            ("ANGLE_BASED", "Angle Based", "Angle-based unwrap (recommended)"),
            ("CONFORMAL", "Conformal", "Conformal (LSCM) unwrap"),
        ],
        default="ANGLE_BASED",
    )
    fill_holes: BoolProperty(name="Fill Holes", default=True)
    correct_aspect: BoolProperty(name="Correct Aspect", default=True)
    pack_after: BoolProperty(name="Pack After Unwrap", default=True)

    def execute(self, context):
        success = unwrap_uv(context,
                            method=self.method,
                            fill_holes=self.fill_holes,
                            correct_aspect=self.correct_aspect)
        if not success:
            self.report({"ERROR"}, "UV unwrap failed. Ensure you have a mesh selected.")
            return {"CANCELLED"}

        if self.pack_after:
            pack_islands(context)

        # Refresh UV island analysis
        bpy.ops.nanobanana.analyze_uv_islands()

        self.report({"INFO"}, "UV unwrap complete.")
        return {"FINISHED"}


class NANOBANANA_OT_pack_islands(Operator):
    """Pack UV islands to maximize UV space usage"""
    bl_idname = "nanobanana.pack_islands"
    bl_label = "Pack Islands"
    bl_options = {"REGISTER", "UNDO"}

    margin: FloatProperty(
        name="Margin",
        description="Space between packed islands",
        default=0.005,
        min=0.0,
        max=0.1,
    )

    def execute(self, context):
        success = pack_islands(context, margin=self.margin)
        if success:
            self.report({"INFO"}, "UV islands packed.")
            return {"FINISHED"}
        self.report({"ERROR"}, "Pack islands failed.")
        return {"CANCELLED"}


class NANOBANANA_OT_analyze_uv_islands(Operator):
    """Detect UV islands and update the viewport overlay"""
    bl_idname = "nanobanana.analyze_uv_islands"
    bl_label = "Analyze UV Islands"
    bl_options = {"REGISTER"}

    def execute(self, context):
        result = analyze_uv_islands(context)
        if result is None:
            self.report({"WARNING"}, "No UV data found. Unwrap first.")
            return {"CANCELLED"}

        context.scene["nb_uv_analysis"] = result
        island_count = result.get("island_count", 0)
        self.report({"INFO"}, f"Found {island_count} UV island(s).")
        return {"FINISHED"}


class NANOBANANA_OT_select_uv_island(Operator):
    """Select this UV island in the UV editor and set it as active region"""
    bl_idname = "nanobanana.select_uv_island"
    bl_label = "Select UV Island"
    bl_options = {"REGISTER", "UNDO"}

    island_id: StringProperty(name="Island ID", default="")

    def execute(self, context):
        if not self.island_id:
            return {"CANCELLED"}

        uv_data = context.scene.get("nb_uv_analysis")
        if not uv_data:
            self.report({"WARNING"}, "No UV analysis data. Run 'Detect Islands' first.")
            return {"CANCELLED"}

        # Find the island
        target = None
        for island in uv_data.get("islands", []):
            if island.get("id") == self.island_id:
                target = island
                break

        if target is None:
            self.report({"WARNING"}, f"Island '{self.island_id}' not found.")
            return {"CANCELLED"}

        obj = context.active_object
        if obj is None or obj.type != "MESH":
            return {"CANCELLED"}

        face_indices = set(target.get("face_indices", []))

        # Enter Edit Mode
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        # Switch to face select mode and select the island faces
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')

        import bmesh
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
            if face.index in face_indices:
                face.select = True
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        # Tag redraw so UV editor updates immediately
        for area in context.screen.areas:
            if area.type in ("VIEW_3D", "IMAGE_EDITOR"):
                area.tag_redraw()

        # Set as active region
        context.scene.nano_banana.active_uv_region_id = self.island_id

        self.report({"INFO"}, f"Selected island: {self.island_id} ({len(face_indices)} faces)")
        return {"FINISHED"}


class NANOBANANA_OT_island_page(Operator):
    """Navigate UV island list pages"""
    bl_idname = "nanobanana.island_page"
    bl_label = "Island Page"
    bl_options = {"REGISTER", "INTERNAL"}

    delta: IntProperty(default=1)

    def execute(self, context):
        uv_data = context.scene.get("nb_uv_analysis")
        if not uv_data:
            return {"CANCELLED"}
        total = len(uv_data.get("islands", []))
        if total == 0:
            return {"CANCELLED"}
        from ..ui.uv_panel import _ISLAND_PAGE_SIZE
        max_page = (total - 1) // _ISLAND_PAGE_SIZE
        current = context.scene.get("_nb_island_page", 0)
        context.scene["_nb_island_page"] = max(0, min(current + self.delta, max_page))
        return {"FINISHED"}


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_mark_seam,
    NANOBANANA_OT_clear_seam,
    NANOBANANA_OT_unwrap_uv,
    NANOBANANA_OT_pack_islands,
    NANOBANANA_OT_analyze_uv_islands,
    NANOBANANA_OT_select_uv_island,
    NANOBANANA_OT_island_page,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
