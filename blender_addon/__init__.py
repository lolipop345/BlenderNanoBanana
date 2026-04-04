"""
BlenderNanoBanana - Blender Addon Entry Point

UV mapping and PBR texture generation using Google's Gemini models.
Gemini 3 Flash generates structured JSON specs → Gemini Image API generates textures.
"""

bl_info = {
    "name": "Nano Banana",
    "author": "lolipop345",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Nano Banana",
    "description": (
        "AI-powered UV mapping and PBR texture generation. "
        "Semantically tags UV islands, generates engine-optimized textures "
        "via Gemini 3 Flash + Nano Banana vision model."
    ),
    "category": "UV",
    "support": "COMMUNITY",
    "doc_url": "",
    "tracker_url": "",
}

import bpy
from bpy.props import (
    StringProperty, BoolProperty, EnumProperty,
    IntProperty, FloatProperty,
)


# ── Dependency check (runs before any addon module imports) ───────────────────

def _auto_install_dependencies():
    """
    Kick off a background daemon thread to install any missing packages.
    Returns immediately — Blender's UI is never blocked.
    Progress is printed to the System Console.
    """
    try:
        from .install_dependencies import auto_install_in_background
        auto_install_in_background()
    except Exception as e:
        print(f"[NanoBanana] Dependency check error: {e}")


# ── Lazy import helpers ────────────────────────────────────────────────────────

def _register_modules():
    """Import and register all addon modules in dependency order."""
    from . import preferences
    from .ops import install_ops, model_ops, unwrap_ops, texture_ops, cache_ops, seam_tag_ops
    from .ui import uv_panel, texture_panel, image_editor_panel, viewport_overlay
    from .core import uv_seam_overlay
    from .utils import preview_manager

    return [
        preferences,
        install_ops,
        model_ops,
        unwrap_ops,
        texture_ops,
        cache_ops,
        seam_tag_ops,
        uv_panel,
        texture_panel,
        image_editor_panel,
        viewport_overlay,
        uv_seam_overlay,
        preview_manager,
    ]


def _unregister_modules():
    """Import modules for unregistration (reverse order)."""
    from . import preferences
    from .ops import install_ops, model_ops, unwrap_ops, texture_ops, cache_ops, seam_tag_ops
    from .ui import uv_panel, texture_panel, image_editor_panel, viewport_overlay
    from .core import uv_seam_overlay
    from .utils import preview_manager

    return [
        preview_manager,
        uv_seam_overlay,
        viewport_overlay,
        image_editor_panel,
        texture_panel,
        uv_panel,
        seam_tag_ops,
        cache_ops,
        texture_ops,
        unwrap_ops,
        model_ops,
        install_ops,
        preferences,
    ]


# ── Scene Properties ───────────────────────────────────────────────────────────

class NanoBananaSceneProps(bpy.types.PropertyGroup):
    """Per-scene properties stored on bpy.context.scene."""

    # ── Generation ────────────────────────────────────────────────────────────
    generation_prompt: StringProperty(
        name="Texture Description",
        description="Describe the material/texture you want to generate",
        default="",
    )

    # UV seam tagging (still used in UV editor)
    active_uv_region_id: StringProperty(
        name="Active UV Region",
        description="ID of the currently selected UV island region",
        default="",
    )

    active_semantic_tag: EnumProperty(
        name="Semantic Tag",
        description="Material type tag for the selected UV region",
        items=lambda self, context: _get_semantic_tag_items(),
    )

    # Engine preset
    engine_preset: EnumProperty(
        name="Engine Preset",
        description="Target game engine or renderer",
        items=lambda self, context: _get_engine_items(),
    )

    # Per-map toggles (Unity set, most common maps)
    map_albedo: BoolProperty(name="Albedo", default=False)
    map_normal: BoolProperty(name="Normal", default=False)
    map_roughness: BoolProperty(name="Roughness", default=False)
    map_metallic: BoolProperty(name="Metallic", default=False)
    map_ao: BoolProperty(name="AO", default=False)
    map_emission: BoolProperty(name="Emission", default=False)
    map_height: BoolProperty(name="Height", default=False)
    map_displacement: BoolProperty(name="Displacement", default=False)

    # Texture size override
    texture_size_override: EnumProperty(
        name="Texture Size",
        description="Override default texture size for this generation",
        items=lambda self, context: _get_texture_size_items(),
    )

    # Status / progress
    is_generating: BoolProperty(
        name="Generating",
        description="True while texture generation is in progress",
        default=False,
    )

    generation_progress: FloatProperty(
        name="Progress",
        description="Generation progress (0.0-1.0)",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )

    generation_status: StringProperty(
        name="Status",
        description="Current generation status message",
        default="Ready",
    )

    # Viewport overlay toggle
    show_uv_overlay: BoolProperty(
        name="Show UV Overlay",
        description="Show UV island highlights in viewport and UV editor tag overlay",
        default=True,
    )

    show_semantic_labels: BoolProperty(
        name="Show Tag Labels",
        description="Show semantic tag labels on UV islands",
        default=True,
    )

    # Seam edge tag data — JSON: {"MeshName": {"42": "tag_id", ...}}
    seam_tags_json: StringProperty(
        name="Seam Tags",
        description="Edge-level semantic tag assignments (JSON)",
        default="{}",
    )

    # Island-level material tags — JSON: {"uv_001": "Skin", "uv_002": "Metal Armor", ...}
    island_tags_json: StringProperty(
        name="Island Tags",
        description="Per-island material label (JSON) — persists across prompt changes",
        default="{}",
    )

    # Text field for typing an island tag in the UV panel
    island_tag_input: StringProperty(
        name="Material Tag",
        description="Material label for the selected UV island (e.g. Skin, Metal Armor, Cloth)",
        default="",
    )

    # Last generated maps — JSON: {"albedo": "/path/...", "normal": "/path/..."}
    last_generated_maps_json: StringProperty(
        name="Last Generated Maps",
        description="File paths of the most recently generated texture maps (JSON)",
        default="{}",
    )


def _get_semantic_tag_items():
    try:
        from .config.semantic_tags import SEMANTIC_TAGS
        items = []
        for tag_id, tag in SEMANTIC_TAGS.items():
            items.append((
                tag_id,
                tag["name"],
                tag.get("description", ""),
            ))
        return items if items else [("none", "None", "")]
    except Exception:
        return [("none", "None", "")]


def _get_engine_items():
    try:
        from .config.engine_presets import ENGINE_ITEMS
        return ENGINE_ITEMS
    except Exception:
        return [("unity", "Unity", "Unity Engine")]


def _get_texture_size_items():
    try:
        from .config.engine_presets import TEXTURE_SIZE_ITEMS
        return TEXTURE_SIZE_ITEMS
    except Exception:
        return [("2048", "2048 px", "")]


# ── Registration ───────────────────────────────────────────────────────────────

_registered_modules = []


def register():
    global _registered_modules

    # Auto-install missing Python dependencies first
    _auto_install_dependencies()

    # Register scene property group first
    bpy.utils.register_class(NanoBananaSceneProps)
    bpy.types.Scene.nano_banana = bpy.props.PointerProperty(
        type=NanoBananaSceneProps
    )

    # Register all addon modules
    try:
        _registered_modules = _register_modules()
        for mod in _registered_modules:
            if hasattr(mod, "register"):
                mod.register()
    except Exception as e:
        print(f"[NanoBanana] Error during module registration: {e}")
        import traceback
        traceback.print_exc()

    # Reset all session-only state that shouldn't persist across addon reloads
    try:
        import bpy as _bpy
        for scene in _bpy.data.scenes:
            props = getattr(scene, "nano_banana", None)
            if props is not None:
                props.last_generated_maps_json = "{}"
                props.is_generating       = False
                props.generation_progress = 0.0
                props.generation_status   = "Ready"
    except Exception:
        pass

    print("[NanoBanana] Addon registered successfully.")


def unregister():
    global _registered_modules

    # Unregister modules in reverse
    try:
        mods = _unregister_modules()
        for mod in mods:
            if hasattr(mod, "unregister"):
                mod.unregister()
    except Exception as e:
        print(f"[NanoBanana] Error during module unregistration: {e}")

    # Clean up scene property
    if hasattr(bpy.types.Scene, "nano_banana"):
        del bpy.types.Scene.nano_banana

    bpy.utils.unregister_class(NanoBananaSceneProps)

    _registered_modules = []
    print("[NanoBanana] Addon unregistered.")


