"""
BlenderNanoBanana - Seam Tag Operators

Tag selected mesh edges with a semantic label.
Tags are stored in scene.nano_banana.seam_tags_json as:
    {"MeshName": {"42": "metallic", "17": "fabric"}, ...}

Works in both EDIT and OBJECT mode — in OBJECT mode it reads the selection
stored in the mesh's edge data.
"""

import json
import bpy
from bpy.types import Operator
from bpy.props import StringProperty


def _load_tags(props) -> dict:
    """Parse seam_tags_json into a dict. Returns {} on any error."""
    try:
        return json.loads(props.seam_tags_json or "{}")
    except Exception:
        return {}


def _save_tags(props, tags: dict):
    """Serialize tags dict back to seam_tags_json."""
    props.seam_tags_json = json.dumps(tags)


def _get_selected_edge_indices(obj) -> list:
    """
    Return indices of currently selected edges.
    Works in EDIT and OBJECT mode by temporarily switching if needed.
    """
    import bmesh
    me = obj.data

    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(me)
        return [e.index for e in bm.edges if e.select]
    else:
        # In object mode mesh data reflects last edit selection
        return [e.index for e in me.edges if e.select]


# ── Tag Selected Edges ─────────────────────────────────────────────────────────

class NANOBANANA_OT_tag_selected_seams(Operator):
    """Assign the active semantic tag to all selected edges"""
    bl_idname = "nanobanana.tag_selected_seams"
    bl_label = "Tag Selected Edges"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.nano_banana
        obj = context.active_object

        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object first.")
            return {"CANCELLED"}

        tag_id = props.active_semantic_tag
        if not tag_id or tag_id == "none":
            self.report({"WARNING"}, "No semantic tag selected.")
            return {"CANCELLED"}

        indices = _get_selected_edge_indices(obj)
        if not indices:
            self.report({"WARNING"}, "No edges selected.")
            return {"CANCELLED"}

        tags = _load_tags(props)
        mesh_key = obj.data.name
        region = tags.setdefault(mesh_key, {})

        for idx in indices:
            region[str(idx)] = tag_id

        _save_tags(props, tags)

        # Redraw all Image Editor areas to show updated overlay
        for area in context.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.tag_redraw()

        self.report({"INFO"}, f"Tagged {len(indices)} edge(s) as '{tag_id}'.")
        return {"FINISHED"}


# ── Clear Tags from Selected Edges ────────────────────────────────────────────

class NANOBANANA_OT_clear_seam_tags(Operator):
    """Remove semantic tag from all selected edges"""
    bl_idname = "nanobanana.clear_seam_tags"
    bl_label = "Clear Edge Tags"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.nano_banana
        obj = context.active_object

        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object first.")
            return {"CANCELLED"}

        indices = _get_selected_edge_indices(obj)
        if not indices:
            self.report({"WARNING"}, "No edges selected.")
            return {"CANCELLED"}

        tags = _load_tags(props)
        mesh_key = obj.data.name
        region = tags.get(mesh_key, {})

        removed = 0
        for idx in indices:
            if str(idx) in region:
                del region[str(idx)]
                removed += 1

        if not region:
            tags.pop(mesh_key, None)

        _save_tags(props, tags)

        for area in context.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.tag_redraw()

        self.report({"INFO"}, f"Cleared tags from {removed} edge(s).")
        return {"FINISHED"}


# ── Clear All Tags for Active Mesh ────────────────────────────────────────────

class NANOBANANA_OT_clear_all_seam_tags(Operator):
    """Remove all semantic edge tags from the active mesh"""
    bl_idname = "nanobanana.clear_all_seam_tags"
    bl_label = "Clear All Edge Tags"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.nano_banana
        obj = context.active_object

        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object first.")
            return {"CANCELLED"}

        tags = _load_tags(props)
        mesh_key = obj.data.name
        count = len(tags.pop(mesh_key, {}))
        _save_tags(props, tags)

        for area in context.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.tag_redraw()

        self.report({"INFO"}, f"Cleared all {count} edge tag(s).")
        return {"FINISHED"}


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_tag_selected_seams,
    NANOBANANA_OT_clear_seam_tags,
    NANOBANANA_OT_clear_all_seam_tags,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
