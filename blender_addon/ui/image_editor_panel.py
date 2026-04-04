"""
BlenderNanoBanana - Image Editor (UV Editor) Panels

Three panels added to the IMAGE_EDITOR N-tab sidebar:
  1. Seam Tags    — tag selected edges, view legend
  2. Generate     — engine + map toggles + generate button
  3. Preview      — thumbnail grid of last generated maps
"""

import bpy
from bpy.types import Panel

from ..config.constants import SEAM_TAG_COLORS


# ── Helper ────────────────────────────────────────────────────────────────────

def _icon_for_tag(tag_id: str) -> str:
    """Return a suitable Blender icon name for a tag category."""
    t = tag_id.lower()
    if any(k in t for k in ("metal", "steel", "iron")):
        return "MATMETAL"
    if any(k in t for k in ("fabric", "cloth", "leather")):
        return "MATCLOTH"
    if any(k in t for k in ("skin", "face", "body", "hair")):
        return "COMMUNITY"
    if any(k in t for k in ("wood", "tree")):
        return "OUTLINER_OB_FORCE_FIELD"
    if any(k in t for k in ("stone", "rock", "brick")):
        return "MESH_ICOSPHERE"
    if any(k in t for k in ("glass", "crystal")):
        return "MATFLUID"
    if any(k in t for k in ("emissive", "emission", "glow")):
        return "LIGHT_SUN"
    return "MATERIAL"


# ── Panel 1: Seam Tags ────────────────────────────────────────────────────────

class NANOBANANA_PT_ie_seam_tags(Panel):
    bl_label = "Seam Tags"
    bl_idname = "NANOBANANA_PT_ie_seam_tags"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        props = context.scene.nano_banana
        obj = context.active_object

        if obj is None or obj.type != "MESH":
            layout.label(text="Select a mesh object", icon="INFO")
            return

        # ── Active region / tag ───────────────────────────────────────────────
        box = layout.box()
        row = box.row()
        row.label(text=f"Mesh: {obj.data.name}", icon="MESH_DATA")

        if props.active_uv_region_id:
            row = box.row()
            row.label(text=f"Region: {props.active_uv_region_id}", icon="UV_ISLANDSEL")

        # ── Tag selector ──────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Select Tag", icon="BOOKMARKS")
        box.prop(props, "active_semantic_tag", text="")

        # Show current tag info
        from ..core.semantic_manager import get_tag
        tag = get_tag(props.active_semantic_tag) if props.active_semantic_tag else None
        if tag:
            row = box.row()
            row.label(text=tag.get("name", ""), icon=_icon_for_tag(props.active_semantic_tag))

        # ── Action buttons ────────────────────────────────────────────────────
        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator("nanobanana.tag_selected_seams",
                     text="Tag Selected Edges", icon="EDGESEL")
        col.operator("nanobanana.clear_seam_tags",
                     text="Clear Selected Tags", icon="X")
        col.operator("nanobanana.clear_all_seam_tags",
                     text="Clear All Tags", icon="TRASH")

        # ── Overlay toggle ────────────────────────────────────────────────────
        layout.separator()
        row = layout.row()
        row.prop(props, "show_uv_overlay", text="Show Tag Overlay", toggle=True, icon="OVERLAY")

        # ── Color legend ──────────────────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="Color Legend", icon="COLOR")

        for key, rgba in SEAM_TAG_COLORS.items():
            row = box.row(align=True)
            row.label(text=key.capitalize(), icon="DOT")

        box.label(text="Unknown tags → auto-color", icon="QUESTION")


# ── Panel 2: Generate ─────────────────────────────────────────────────────────

class NANOBANANA_PT_ie_generate(Panel):
    bl_label = "Generate Textures"
    bl_idname = "NANOBANANA_PT_ie_generate"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        props = context.scene.nano_banana

        if not props.active_uv_region_id:
            layout.label(text="No UV region selected", icon="INFO")
            layout.label(text="Go to 3D View → UV Mapping → Detect Islands", icon="ARROW_LEFTRIGHT")
            return

        # ── Engine Preset ─────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Engine Preset", icon="WORLD_DATA")
        box.prop(props, "engine_preset", text="")

        from ..config.engine_presets import ENGINE_PRESETS
        engine = ENGINE_PRESETS.get(props.engine_preset)
        if engine:
            box.label(text=engine.get("description", ""), icon="INFO")

        # ── Map Toggles ───────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Texture Maps", icon="IMAGE_DATA")

        col = box.column(align=True)
        MAP_PROPS = {
            "albedo": "map_albedo", "normal": "map_normal",
            "roughness": "map_roughness", "metallic": "map_metallic",
            "ao": "map_ao", "emission": "map_emission",
            "height": "map_height", "displacement": "map_displacement",
        }

        if engine:
            for map_name, prop_name in MAP_PROPS.items():
                if map_name not in engine.get("supported_maps", {}):
                    continue
                row = col.row(align=True)
                row.prop(props, prop_name, toggle=True)
        else:
            for prop_name, label in [
                ("map_albedo", "Albedo"), ("map_normal", "Normal"),
                ("map_roughness", "Roughness"), ("map_metallic", "Metallic"),
                ("map_ao", "AO"), ("map_emission", "Emission"),
            ]:
                col.prop(props, prop_name, toggle=True, text=label)

        # ── Prerequisites check ───────────────────────────────────────────────
        from ..preferences import get_preferences
        prefs = get_preferences(context)
        missing = []
        if not prefs.google_api_key:
            missing.append("Google API Key (Preferences)")
        if not props.active_semantic_tag or props.active_semantic_tag == "none":
            missing.append("Semantic Tag")
        any_map = any(
            getattr(props, f"map_{m}", False)
            for m in MAP_PROPS
        )
        if not any_map:
            missing.append("At least one map")

        if missing:
            box = layout.box()
            box.label(text="Missing:", icon="ERROR")
            for item in missing:
                box.label(text=f"  • {item}", icon="DOT")

        # ── Generate button ───────────────────────────────────────────────────
        layout.separator()
        row = layout.row()
        row.scale_y = 2.0
        row.enabled = not props.is_generating and not missing
        row.operator(
            "nanobanana.generate_textures",
            text="Generate Textures" if not props.is_generating else "Generating...",
            icon="RENDER_STILL",
        )

        if props.is_generating:
            try:
                layout.progress(factor=props.generation_progress,
                                text=props.generation_status)
            except Exception:
                pct = int(props.generation_progress * 100)
                layout.label(text=f"{pct}%  {props.generation_status}")

        # ── Apply cached ──────────────────────────────────────────────────────
        layout.separator()
        layout.operator("nanobanana.apply_cached_material",
                        text="Apply Cached Material", icon="MATERIAL")


# ── Panel 3: Preview ──────────────────────────────────────────────────────────

class NANOBANANA_PT_ie_preview(Panel):
    bl_label = "Generated Maps"
    bl_idname = "NANOBANANA_PT_ie_preview"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        props = context.scene.nano_banana

        import json as _json
        import os as _os
        try:
            last_maps = _json.loads(getattr(props, "last_generated_maps_json", "{}") or "{}")
        except Exception:
            last_maps = {}

        # Only show maps whose files still exist on disk
        last_maps = {k: v for k, v in last_maps.items() if v and _os.path.isfile(v)}

        if not last_maps:
            layout.label(text="No generated maps yet", icon="INFO")
            layout.label(text="Use Generate Textures above", icon="DOT")
            return

        from ..utils.preview_manager import get_icon_id

        # 2-column grid
        grid = layout.grid_flow(row_major=True, columns=2,
                                even_columns=True, even_rows=True)
        for map_name in last_maps:
            icon_id = get_icon_id(map_name)
            col = grid.column(align=True)
            if icon_id:
                col.template_icon(icon_value=icon_id, scale=5.0)
            else:
                col.label(text=map_name, icon="IMAGE_DATA")
            col.label(text=map_name.capitalize())

        layout.separator()
        layout.label(text="Image Editor shows albedo automatically", icon="INFO")


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_PT_ie_seam_tags,
    NANOBANANA_PT_ie_generate,
    NANOBANANA_PT_ie_preview,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
