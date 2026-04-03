"""
BlenderNanoBanana - Cache Browser Panel

Browse cached textures and references. Version history. Cache management.
"""

import bpy
import os
from bpy.types import Panel

from ..core.cache_manager import (
    get_reference_images,
    get_latest_texture_version,
    get_texture_maps_from_version,
    get_project_name,
)


class NANOBANANA_PT_cache(Panel):
    bl_label = "Cache"
    bl_idname = "NANOBANANA_PT_cache"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Nano Banana"
    bl_order = 5
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.nano_banana

        # ── Cache Location ─────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Cache", icon="FILE_FOLDER")
        box.operator("nanobanana.browse_cache", text="Open Cache Folder", icon="FILEBROWSER")

        # ── Active Region Cache ────────────────────────────────────────────────
        uv_region_id = props.active_uv_region_id
        if uv_region_id:
            # References
            ref_box = layout.box()
            ref_box.label(text="Reference Images", icon="IMAGE_REFERENCE")

            refs = get_reference_images(context, uv_region_id)
            if refs:
                ref_box.label(text=f"{len(refs)} cached", icon="CHECKMARK")
                for path in refs[-3:]:  # Show last 3
                    row = ref_box.row()
                    row.label(text=os.path.basename(path), icon="IMAGE_DATA")
                ref_box.operator("nanobanana.browse_references",
                                 text="Browse All", icon="FILEBROWSER")
            else:
                ref_box.label(text="No references cached", icon="X")
            ref_box.operator("nanobanana.generate_references",
                             text="Generate References", icon="RENDER_STILL")

            # Textures
            tex_box = layout.box()
            tex_box.label(text="Latest Texture Version", icon="TEXTURE")

            version_dir = get_latest_texture_version(context, uv_region_id)
            if version_dir:
                tex_box.label(text=os.path.basename(version_dir), icon="CHECKMARK")
                maps = get_texture_maps_from_version(version_dir)
                for map_name, path in maps.items():
                    row = tex_box.row()
                    row.label(text=f"  {map_name}: {os.path.basename(path)}", icon="DOT")
            else:
                tex_box.label(text="No textures cached", icon="X")

            # Clear region cache
            layout.separator()
            row = layout.row()
            row.alert = True
            row.operator("nanobanana.clear_region_cache",
                         text="Clear Region Cache", icon="TRASH")

        # ── Project Cache ──────────────────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="Project Cache", icon="PACKAGE")

        project_name = get_project_name(context)
        box.label(text=project_name, icon="FILE_BLEND")

        row = box.row()
        row.alert = True
        row.operator("nanobanana.clear_project_cache",
                     text="Clear ALL Project Cache", icon="TRASH")


def register():
    bpy.utils.register_class(NANOBANANA_PT_cache)


def unregister():
    bpy.utils.unregister_class(NANOBANANA_PT_cache)
