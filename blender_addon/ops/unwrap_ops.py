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
from bpy.props import BoolProperty, EnumProperty, FloatProperty

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


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_mark_seam,
    NANOBANANA_OT_clear_seam,
    NANOBANANA_OT_unwrap_uv,
    NANOBANANA_OT_pack_islands,
    NANOBANANA_OT_analyze_uv_islands,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
