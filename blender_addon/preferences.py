"""
BlenderNanoBanana - Addon Preferences Panel
API keys, cache settings, performance options.
"""

import bpy
import os
from bpy.types import AddonPreferences
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty

from .config.defaults import (
    DEFAULT_CACHE_MAX_VERSIONS,
    DEFAULT_CACHE_AUTO_CLEANUP,
    DEFAULT_GENERATE_REFERENCES,
    DEFAULT_REFERENCES_COUNT,
)


class NanoBananaPreferences(AddonPreferences):
    bl_idname = __package__

    # ── API Keys ──────────────────────────────────────────────────────────────

    google_api_key: StringProperty(
        name="Google API Key",
        description=(
            "Your Google Generative AI API Key.\n"
            "Used for both Gemini 3 Flash (JSON spec generation) "
            "and Nano Banana (texture generation)."
        ),
        subtype="PASSWORD",
        default="",
    )

    # ── Cache Settings ────────────────────────────────────────────────────────

    cache_base_path: StringProperty(
        name="Cache Directory",
        description=(
            "Where to store generated textures and references.\n"
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

    # ── Generation Settings ───────────────────────────────────────────────────

    auto_generate_references: BoolProperty(
        name="Auto-Generate References",
        description="Automatically generate reference images before texture generation",
        default=DEFAULT_GENERATE_REFERENCES,
    )

    references_count: IntProperty(
        name="References to Generate",
        description="How many reference images to generate per UV region",
        default=DEFAULT_REFERENCES_COUNT,
        min=1,
        max=10,
    )

    # ── Rust Backend ──────────────────────────────────────────────────────────

    rust_binary_path: StringProperty(
        name="Rust Backend Path",
        description=(
            "Path to the Rust backend binary.\n"
            "Leave empty to use the bundled binary."
        ),
        subtype="FILE_PATH",
        default="",
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
        if dep_status["all_ok"]:
            row = box.row()
            row.label(text="Dependencies: All installed", icon="CHECKMARK")
        else:
            box.label(text="Dependencies", icon="ERROR")
            for pkg in dep_status["packages"]:
                row = box.row()
                icon = "CHECKMARK" if pkg["installed"] else "X"
                row.label(text=f"  {pkg['name']}", icon=icon)
            row = box.row()
            row.scale_y = 1.4
            row.operator("nanobanana.install_dependencies",
                         text="Install Missing Dependencies", icon="IMPORT")

        # ─ API Configuration ──────────────────────────────────────────────────
        box = layout.box()
        row = box.row()
        row.label(text="API Configuration", icon="WORLD_DATA")

        col = box.column(align=True)
        col.prop(self, "google_api_key", icon="KEY_HLT")

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

        # ─ Generation Settings ────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Generation Settings", icon="IMAGE_DATA")

        col = box.column(align=True)
        col.prop(self, "auto_generate_references")
        if self.auto_generate_references:
            col.prop(self, "references_count")

        # ─ Advanced ───────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Advanced", icon="PREFERENCES")

        col = box.column(align=True)
        col.prop(self, "rust_binary_path")
        col.prop(self, "enable_debug_logging")

        # ─ Status ─────────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Status", icon="INFO")

        # Rust backend status
        from .core.rust_bridge import get_rust_bridge
        bridge = get_rust_bridge()
        if bridge and bridge.is_running():
            row = box.row()
            row.label(text="Rust Backend: Running", icon="CHECKMARK")
        else:
            row = box.row()
            row.label(text="Rust Backend: Not started", icon="X")
            row.operator("nanobanana.start_rust_backend", text="Start Backend")


def get_preferences(context=None) -> NanoBananaPreferences:
    """Helper to get addon preferences from any context."""
    ctx = context or bpy.context
    return ctx.preferences.addons[__package__].preferences


def register():
    bpy.utils.register_class(NanoBananaPreferences)


def unregister():
    bpy.utils.unregister_class(NanoBananaPreferences)
