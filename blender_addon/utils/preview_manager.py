"""
BlenderNanoBanana - Preview / Thumbnail Manager

Manages a bpy.utils.previews ImagePreviewCollection for displaying
generated texture map thumbnails in the N-tab panels and Image Editor.

Blender 4.x compatibility: bpy.utils.previews must be explicitly imported.
"""

import os
from typing import Dict, Optional

import bpy
# Blender 4.x requires explicit import of the previews sub-module
import bpy.utils.previews as _bpy_previews

_pcoll = None


def get_preview_collection():
    """Return the active preview collection, creating it if needed."""
    global _pcoll
    if _pcoll is None:
        _pcoll = _bpy_previews.new()
    return _pcoll


def load_map_previews(map_paths: Dict[str, str]):
    """
    Load generated map images into the preview collection.

    Args:
        map_paths: {"albedo": "/path/albedo.png", "normal": "/path/normal.png", ...}
    """
    pcoll = get_preview_collection()

    for map_name, filepath in map_paths.items():
        if not filepath or not os.path.exists(filepath):
            continue
        key = f"nb_{map_name}"
        # Remove stale entry before reloading
        if key in pcoll:
            del pcoll[key]
        try:
            pcoll.load(key, filepath, "IMAGE")
        except Exception:
            pass


def get_icon_id(map_name: str) -> Optional[int]:
    """Return the icon_value for a map name, or None if not loaded."""
    try:
        pcoll = get_preview_collection()
        key = f"nb_{map_name}"
        if key in pcoll:
            return pcoll[key].icon_id
    except Exception:
        pass
    return None


def get_all_icon_ids() -> Dict[str, int]:
    """Return {map_name: icon_id} for all loaded previews."""
    try:
        pcoll = get_preview_collection()
        result = {}
        for key, preview in pcoll.items():
            if key.startswith("nb_"):
                map_name = key[3:]  # strip "nb_" prefix
                result[map_name] = preview.icon_id
        return result
    except Exception:
        return {}


def clear():
    """Remove all loaded previews."""
    global _pcoll
    if _pcoll is not None:
        _pcoll.clear()


def register():
    global _pcoll
    _pcoll = _bpy_previews.new()


def unregister():
    global _pcoll
    if _pcoll is not None:
        _bpy_previews.remove(_pcoll)
        _pcoll = None
