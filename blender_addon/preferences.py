"""
BlenderNanoBanana - Addon Preferences Panel
API keys, cache settings, debug options.
"""

import bpy
import os
from bpy.types import AddonPreferences
from bpy.props import StringProperty, IntProperty, BoolProperty

from .config.defaults import DEFAULT_CACHE_MAX_VERSIONS, DEFAULT_CACHE_AUTO_CLEANUP


class NanoBananaPreferences(AddonPreferences):
    bl_idname = __package__

    # ── API Keys ──────────────────────────────────────────────────────────────

    google_api_key: StringProperty(
        name="Google API Key",
        description=(
            "Your Google Generative AI API Key.\n"
            "Used for Gemini 3 Flash (spec) and Gemini Image (texture generation)."
        ),
        subtype="PASSWORD",
        default="",
    )

    # ── Cache Settings ────────────────────────────────────────────────────────

    cache_base_path: StringProperty(
        name="Cache Directory",
        description=(
            "Where to store generated textures.\n"
            "Leave empty to use the addon directory."
        ),
        subtype="DIR_PATH",
        default="",
    )

    cache_max_versions: IntProperty(
        name="Max Versions per Region",
        description="How many generated versions to keep per UV region before auto-cleanup",
        default=DEFAULT_CACHE_MAX_VERSIONS,
        min=1,
        max=50,
    )

    cache_auto_cleanup: BoolProperty(
        name="Auto-Cleanup Old Versions",
        description="Automatically delete old versions when limit is reached",
        default=DEFAULT_CACHE_AUTO_CLEANUP,
    )

    # ── Debug Settings ────────────────────────────────────────────────────────

    enable_debug_logging: BoolProperty(
        name="Enable Debug Logging",
        description="Show detailed logs in the system console",
        default=False,
    )

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, context):
        layout = self.layout

        # ─ Dependencies ───────────────────────────────────────────────────────
        from .install_dependencies import check_all
        dep_status = check_all()

        box = layout.box()
        if dep_status.get("installing"):
            row = box.row()
            row.label(text="Installing dependencies... (see System Console)", icon="TIME")
        elif dep_status["all_ok"]:
            box.row().label(text="Dependencies: All installed", icon="CHECKMARK")
        else:
            box.label(text="Missing dependencies:", icon="ERROR")
            for pkg in dep_status["packages"]:
                icon = "CHECKMARK" if pkg["installed"] else "X"
                box.row().label(text=f"  {pkg['name']}", icon=icon)
            row = box.row()
            row.scale_y = 1.4
            row.operator("nanobanana.install_dependencies",
                         text="Install Missing Dependencies", icon="IMPORT")
            box.label(text="Auto-install runs on addon enable — check System Console",
                      icon="INFO")

        # ─ API Configuration ──────────────────────────────────────────────────
        box = layout.box()
        box.label(text="API Configuration", icon="WORLD_DATA")
        box.prop(self, "google_api_key", icon="KEY_HLT")
        if not self.google_api_key:
            row = box.row()
            row.alert = True
            row.label(text="Google API Key required!", icon="ERROR")

        # ─ Cache Settings ─────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Cache Settings", icon="FILE_FOLDER")
        col = box.column(align=True)
        col.prop(self, "cache_base_path")
        col.prop(self, "cache_max_versions")
        col.prop(self, "cache_auto_cleanup")

        # ─ Debug ──────────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Debug", icon="PREFERENCES")
        box.prop(self, "enable_debug_logging")


def get_preferences(context=None) -> NanoBananaPreferences:
    ctx = context or bpy.context
    return ctx.preferences.addons[__package__].preferences


def register():
    bpy.utils.register_class(NanoBananaPreferences)


def unregister():
    bpy.utils.unregister_class(NanoBananaPreferences)
