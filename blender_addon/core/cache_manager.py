"""
BlenderNanoBanana - Cache Manager

File-based cache organized per-project, per-UV-region.
Stores: reference images, generated textures, metadata.
Auto-cleanup keeps last N versions per region.

Structure:
  <cache_base>/<project_name>/
    <uv_region_id>/
      semantic_tag.json
      references/
        reference_001.png
        reference_002.png
        metadata.json
      textures/
        v001/
          albedo.png
          normal.png
          ...
          metadata.json
        v002/
          ...
    gemini_specs/
      gemini_spec_<hash>.json
    viewport_captures/
      context_<timestamp>.png
    custom_tags.json
    project_index.json
"""

import os
import shutil
import time
from typing import Optional, List, Dict, Any

from ..utils.serialization import load_json, save_json
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "CacheManager"

_DEFAULT_CACHE_SUBDIR = "nano_banana_cache"

# Thread-safe override: set before spawning background thread so bpy.context
# is never accessed from a non-main thread.
_cache_base_override: Optional[str] = None
_project_name_override: Optional[str] = None


def set_thread_overrides(cache_base: Optional[str], project_name: Optional[str]):
    """Set pre-computed values so background threads avoid bpy.context access."""
    global _cache_base_override, _project_name_override
    _cache_base_override = cache_base
    _project_name_override = project_name


def get_cache_base_path(context=None) -> str:
    """
    Get the root cache directory.

    Uses addon preferences cache_base_path if set,
    otherwise uses a subfolder next to the .blend file,
    otherwise uses the addon directory.

    If set_thread_overrides() was called, returns the pre-computed value
    without touching bpy.context (safe from background threads).
    """
    if _cache_base_override is not None:
        return _cache_base_override

    # Try preferences
    try:
        import bpy
        prefs = bpy.context.preferences.addons[
            __package__.split(".")[0]
        ].preferences
        if prefs.cache_base_path:
            path = bpy.path.abspath(prefs.cache_base_path)
            if path:
                return path
    except Exception:
        pass

    # Try blend file directory
    try:
        import bpy
        blend_path = bpy.data.filepath
        if blend_path:
            blend_dir = os.path.dirname(blend_path)
            return os.path.join(blend_dir, _DEFAULT_CACHE_SUBDIR)
    except Exception:
        pass

    # Fallback: next to addon package
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(addon_dir, "assets", "cache")


def get_project_name(context=None) -> str:
    """Get the current project name (derived from .blend filename)."""
    if _project_name_override is not None:
        return _project_name_override
    try:
        import bpy
        blend_path = bpy.data.filepath
        if blend_path:
            return os.path.basename(blend_path)
    except Exception:
        pass
    return "unsaved_project"


def get_region_dir(context, uv_region_id: str) -> str:
    """Return the cache directory for a specific UV region."""
    base = get_cache_base_path(context)
    project = get_project_name(context)
    safe_proj = _safe_name(project)
    return os.path.join(base, safe_proj, uv_region_id)


# ── Reference Images ──────────────────────────────────────────────────────────

def save_reference_image(context, uv_region_id: str,
                          image_b64: str, metadata: dict) -> Optional[str]:
    """
    Save a reference image to cache.

    Returns the path of the saved file, or None on failure.
    """
    from ..utils.image_processing import base64_to_file

    region_dir = get_region_dir(context, uv_region_id)
    ref_dir = os.path.join(region_dir, "references")
    os.makedirs(ref_dir, exist_ok=True)

    # Next reference index
    existing = [f for f in os.listdir(ref_dir) if f.endswith(".png")]
    index = len(existing) + 1
    filename = f"reference_{index:03d}.png"
    filepath = os.path.join(ref_dir, filename)

    if base64_to_file(image_b64, filepath):
        # Update metadata
        meta_path = os.path.join(ref_dir, "metadata.json")
        meta = load_json(meta_path) or {"references": []}
        meta["references"].append({
            "file": filename,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **metadata,
        })
        save_json(meta_path, meta)
        log_debug(f"Reference saved: {filename}", _MODULE)
        return filepath

    return None


def get_reference_images(context, uv_region_id: str) -> List[str]:
    """Return list of reference image paths for a UV region."""
    region_dir = get_region_dir(context, uv_region_id)
    ref_dir = os.path.join(region_dir, "references")
    if not os.path.isdir(ref_dir):
        return []
    return sorted(
        [os.path.join(ref_dir, f) for f in os.listdir(ref_dir) if f.endswith(".png")],
        key=os.path.getmtime,
    )


# ── Texture Versions ──────────────────────────────────────────────────────────

def save_texture_version(context, uv_region_id: str,
                         texture_files: Dict[str, str],
                         metadata: dict) -> Optional[str]:
    """
    Save a new texture version set to cache.

    Args:
        texture_files: {"albedo": filepath, "normal": filepath, ...}
        metadata: Generation metadata to store

    Returns:
        Version directory path, or None on failure.
    """
    region_dir = get_region_dir(context, uv_region_id)
    tex_dir = os.path.join(region_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    # Auto-increment version number
    existing = [
        d for d in os.listdir(tex_dir)
        if os.path.isdir(os.path.join(tex_dir, d)) and d.startswith("v")
    ]
    version = len(existing) + 1
    version_dir = os.path.join(tex_dir, f"v{version:03d}")
    os.makedirs(version_dir, exist_ok=True)

    # Copy texture files into version dir
    for map_name, src_path in texture_files.items():
        if src_path and os.path.isfile(src_path):
            dst = os.path.join(version_dir, os.path.basename(src_path))
            shutil.copy2(src_path, dst)

    # Save metadata
    meta = {
        "version": version,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "maps": list(texture_files.keys()),
        **metadata,
    }
    save_json(os.path.join(version_dir, "metadata.json"), meta)

    log_info(f"Texture version v{version:03d} saved for region '{uv_region_id}'.", _MODULE)

    # Auto-cleanup old versions
    _auto_cleanup_versions(context, tex_dir)

    return version_dir


def get_latest_texture_version(context, uv_region_id: str) -> Optional[str]:
    """Return path to the latest texture version directory, or None."""
    region_dir = get_region_dir(context, uv_region_id)
    tex_dir = os.path.join(region_dir, "textures")
    if not os.path.isdir(tex_dir):
        return None

    versions = sorted(
        [os.path.join(tex_dir, d) for d in os.listdir(tex_dir)
         if os.path.isdir(os.path.join(tex_dir, d)) and d.startswith("v")],
        key=lambda p: os.path.getmtime(p),
    )
    return versions[-1] if versions else None


def get_texture_maps_from_version(version_dir: str) -> Dict[str, str]:
    """Return map_name → filepath for all textures in a version directory."""
    if not version_dir or not os.path.isdir(version_dir):
        return {}

    result = {}
    extensions = {".png", ".exr", ".jpg", ".tga", ".tif"}
    for fname in os.listdir(version_dir):
        _, ext = os.path.splitext(fname)
        if ext.lower() in extensions:
            name = fname.rsplit(".", 1)[0]  # "albedo" from "albedo.png"
            result[name] = os.path.join(version_dir, fname)
    return result


# ── Auto-Cleanup ──────────────────────────────────────────────────────────────

def _auto_cleanup_versions(context, textures_dir: str):
    """Keep only the last N versions per region (from preferences)."""
    try:
        import bpy
        prefs = bpy.context.preferences.addons[
            __package__.split(".")[0]
        ].preferences
        max_versions = prefs.cache_max_versions
        do_cleanup = prefs.cache_auto_cleanup
    except Exception:
        max_versions = 5
        do_cleanup = True

    if not do_cleanup:
        return

    versions = sorted(
        [os.path.join(textures_dir, d) for d in os.listdir(textures_dir)
         if os.path.isdir(os.path.join(textures_dir, d)) and d.startswith("v")],
        key=lambda p: os.path.getmtime(p),
    )

    while len(versions) > max_versions:
        old = versions.pop(0)
        try:
            shutil.rmtree(old)
            log_debug(f"Removed old texture version: {os.path.basename(old)}", _MODULE)
        except Exception as e:
            log_error(f"Failed to remove old version: {e}", _MODULE)


def clear_region_cache(context, uv_region_id: str):
    """Delete all cached data for a UV region."""
    region_dir = get_region_dir(context, uv_region_id)
    if os.path.isdir(region_dir):
        shutil.rmtree(region_dir)
        log_info(f"Cache cleared for region '{uv_region_id}'.", _MODULE)


def clear_project_cache(context):
    """Delete all cached data for the current project."""
    base = get_cache_base_path(context)
    project = get_project_name(context)
    proj_dir = os.path.join(base, _safe_name(project))
    if os.path.isdir(proj_dir):
        shutil.rmtree(proj_dir)
        log_info(f"Project cache cleared: {project}", _MODULE)


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
