"""
BlenderNanoBanana - Prompt Engineer (Gemini 3 Flash Integration)

Calls Gemini 3 Flash with semantic context → returns JSON texture specs.
Specs are cached to avoid redundant API calls for the same tag+engine combo.
"""

import os
import hashlib
from typing import Optional, Dict, Any, List

from .semantic_adapter import build_gemini_context
from ..api.google_llm import generate_texture_spec
from ..utils.serialization import load_json, save_json
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "PromptEngineer"


def get_texture_spec(
    context,
    api_key: str,
    tag_id: str,
    tag_definition: dict,
    engine_spec: dict,
    project_name: str,
    viewport_image_path: Optional[str] = None,
    reference_image_paths: Optional[List[str]] = None,
    force_regenerate: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Get a texture spec JSON for a UV region.

    Checks spec cache first, then calls Gemini 3 Flash if needed.

    Args:
        context: Blender context
        api_key: Google API key
        tag_id: Semantic tag identifier
        tag_definition: Full tag definition dict
        engine_spec: Engine preset dict (Unity/Roblox/etc.)
        project_name: Project name for cache organization
        viewport_image_path: Optional viewport screenshot path
        reference_image_paths: Optional list of reference image paths
        force_regenerate: Skip cache and regenerate

    Returns:
        JSON spec dict, or None on failure.
    """
    cache_path = _get_spec_cache_path(context, project_name, tag_id, engine_spec)

    # Check cache
    if not force_regenerate and os.path.isfile(cache_path):
        cached = load_json(cache_path)
        if cached and "spec" in cached:
            log_debug(f"Using cached spec for tag='{tag_id}'.", _MODULE)
            return cached["spec"]

    # Build Gemini context
    gemini_ctx = build_gemini_context(
        tag_id=tag_id,
        tag_definition=tag_definition,
        engine_spec=engine_spec,
        viewport_image_path=viewport_image_path,
        reference_image_paths=reference_image_paths,
    )

    log_info(f"Calling Gemini 3 Flash for tag='{tag_id}', engine='{engine_spec.get('id')}'...", _MODULE)

    spec = generate_texture_spec(
        api_key=api_key,
        system_prompt=gemini_ctx["system_prompt"],
        user_prompt=gemini_ctx["user_prompt"],
        images=gemini_ctx["images"],
    )

    if spec is None:
        log_error("Gemini 3 Flash returned no spec.", _MODULE)
        return None

    # Validate required fields
    spec = _validate_and_fill_spec(spec, tag_definition)

    # Cache the result
    save_json(cache_path, {
        "tag_id": tag_id,
        "engine_id": engine_spec.get("id"),
        "spec": spec,
    })

    log_info(f"Texture spec cached: {cache_path}", _MODULE)
    return spec


def _validate_and_fill_spec(spec: dict, tag_def: dict) -> dict:
    """
    Ensure required fields exist. Fill missing from tag hints as fallback.
    """
    hints = tag_def.get("gemini_hints", {})

    defaults = {
        "material_type": hints.get("material_type", "generic"),
        "detail_level": tag_def.get("detail_level", "medium"),
        "surface_characteristic": "smooth",
        "roughness_profile": "medium",
    }

    for key, default_val in defaults.items():
        if key not in spec or not spec[key]:
            spec[key] = default_val

    return spec


def _get_spec_cache_path(context, project_name: str, tag_id: str, engine_spec: dict) -> str:
    """Build a deterministic cache file path for a tag+engine combination."""
    from .cache_manager import get_cache_base_path
    base = get_cache_base_path(context)
    safe_proj = _safe_name(project_name)
    engine_id = engine_spec.get("id", "custom")
    # Use a hash-based filename to keep it tidy
    key = f"{tag_id}_{engine_id}"
    fname = f"gemini_spec_{hashlib.md5(key.encode()).hexdigest()[:8]}.json"
    return os.path.join(base, safe_proj, "gemini_specs", fname)


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
