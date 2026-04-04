"""
BlenderNanoBanana - Texture Generation Panel

Engine preset selector, per-map toggles, generate button, progress display.
"""

import bpy
from bpy.types import Panel


class NANOBANANA_PT_texture(Panel):
    bl_label = "Texture Generation"
    bl_idname = "NANOBANANA_PT_texture"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 4

    def draw(self, context):
        layout = self.layout
        props = context.scene.nano_banana

        if not props.active_uv_region_id:
            layout.label(text="Select a UV region first", icon="INFO")
            return

        # ── Engine Preset ──────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Engine Preset", icon="WORLD_DATA")
        box.prop(props, "engine_preset", text="")

        # Show engine description
        from ..config.engine_presets import ENGINE_PRESETS
        engine_id = props.engine_preset
        engine = ENGINE_PRESETS.get(engine_id)
        if engine:
            box.label(text=engine.get("description", ""), icon="INFO")

        # ── Map Toggles ────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Texture Maps", icon="IMAGE_DATA")
        box.label(text="(All off by default — enable what you need)", icon="DOT")

        col = box.column(align=True)

        if engine:
            supported = engine.get("supported_maps", {})

            # Map name → prop name
            MAP_PROPS = {
                "albedo": "map_albedo",
                "normal": "map_normal",
                "roughness": "map_roughness",
                "metallic": "map_metallic",
                "ao": "map_ao",
                "emission": "map_emission",
                "height": "map_height",
                "displacement": "map_displacement",
            }

            for map_name, map_cfg in supported.items():
                prop_name = MAP_PROPS.get(map_name)
                if not prop_name:
                    continue

                row = col.row(align=True)
                row.prop(props, prop_name, toggle=True)

                # Show size + format info
                if getattr(props, prop_name, False):
                    size = map_cfg.get("size", 2048)
                    fmt = map_cfg.get("format", "")
                    ext = map_cfg.get("file_ext", "png")
                    row.label(text=f"{size}px  {ext}  [{fmt}]")
        else:
            # Fallback: show all common maps
            for prop_name, label in [
                ("map_albedo", "Albedo"),
                ("map_normal", "Normal"),
                ("map_roughness", "Roughness"),
                ("map_metallic", "Metallic"),
                ("map_ao", "AO"),
                ("map_emission", "Emission"),
                ("map_height", "Height"),
            ]:
                col.prop(props, prop_name, toggle=True, text=label)

        # ── Generate Button ────────────────────────────────────────────────────
        layout.separator()

        # Check prerequisites
        from ..preferences import get_preferences
        prefs = get_preferences(context)
        missing = []
        if not prefs.google_api_key:
            missing.append("Google API Key")
        if not props.active_semantic_tag or props.active_semantic_tag == "none":
            missing.append("Semantic Tag")

        any_map = any(
            getattr(props, f"map_{m}", False)
            for m in ["albedo", "normal", "roughness", "metallic",
                      "ao", "emission", "height", "displacement"]
        )
        if not any_map:
            missing.append("At least one map enabled")

        if missing:
            box = layout.box()
            box.label(text="Missing:", icon="ERROR")
            for item in missing:
                box.label(text=f"  • {item}", icon="DOT")

        row = layout.row()
        row.scale_y = 2.0
        row.enabled = not props.is_generating and not missing
        op = row.operator("nanobanana.generate_textures",
                          text="Generate Textures" if not props.is_generating else "Generating...",
                          icon="RENDER_STILL")

        if props.is_generating:
            try:
                layout.progress(factor=props.generation_progress, text=props.generation_status)
            except Exception:
                pct = int(props.generation_progress * 100)
                layout.label(text=f"{pct}%  {props.generation_status}")

        # ── Apply Cached ───────────────────────────────────────────────────────
        layout.separator()
        layout.operator("nanobanana.apply_cached_material",
                        text="Apply Cached Material", icon="MATERIAL")

        # ── Generated Map Previews ─────────────────────────────────────────────
        import json as _json
        import os as _os
        try:
            last_maps = _json.loads(getattr(props, "last_generated_maps_json", "{}") or "{}")
        except Exception:
            last_maps = {}

        # Only show maps whose files actually exist on disk
        last_maps = {k: v for k, v in last_maps.items() if v and _os.path.isfile(v)}

        if last_maps:
            layout.separator()
            box = layout.box()
            box.label(text="Generated Maps", icon="IMAGE_DATA")

            from ..utils.preview_manager import get_icon_id
            grid = box.grid_flow(row_major=True, columns=2,
                                 even_columns=True, even_rows=True)
            for map_name in last_maps:
                icon_id = get_icon_id(map_name)
                col = grid.column(align=True)
                if icon_id:
                    col.template_icon(icon_value=icon_id, scale=4.0)
                else:
                    col.label(text=map_name, icon="IMAGE_DATA")
                col.label(text=map_name.capitalize())


def register():
    bpy.utils.register_class(NANOBANANA_PT_texture)


def unregister():
    bpy.utils.unregister_class(NANOBANANA_PT_texture)
