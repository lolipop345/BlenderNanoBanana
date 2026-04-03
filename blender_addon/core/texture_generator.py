"""
BlenderNanoBanana - Texture Generation Orchestrator

Full pipeline:
  1. Get semantic tag + engine preset
  2. Call Gemini 3 Flash → JSON texture spec
  3. Send JSON spec + visual context to Nano Banana → texture images
  4. Process images via Rust backend (optimize, color space, resize)
  5. Save to cache
  6. Auto-create Blender material

This is the main generation entry point called by texture_ops.py operator.
"""

import os
import time
from typing import Optional, Dict, Any, List, Callable

from .prompt_engineer import get_texture_spec
from .reference_generator import get_or_generate_references
from .cache_manager import (
    save_texture_version,
    get_cache_base_path,
    get_project_name,
)
from .viewport_handler import get_latest_capture
from .semantic_manager import get_tag
from ..api.google_vision import generate_textures
from ..utils.image_processing import base64_to_file, image_to_base64
from ..utils.mesh_utils import create_pbr_material, apply_material_to_object
from ..utils.logging import log_info, log_debug, log_error
from ..config.engine_presets import ENGINE_PRESETS

_MODULE = "TextureGenerator"


def run_generation_pipeline(
    context,
    api_key: str,
    uv_region_id: str,
    tag_id: str,
    engine_id: str,
    enabled_maps: List[str],
    progress_cb: Optional[Callable[[float, str], None]] = None,
    auto_generate_refs: bool = True,
    force_new_spec: bool = False,
) -> Optional[Dict[str, str]]:
    """
    Run the full texture generation pipeline for a UV region.

    Args:
        context: Blender context
        api_key: Google API key
        uv_region_id: UV island identifier
        tag_id: Semantic tag (e.g. "human_face")
        engine_id: Engine preset (e.g. "unity")
        enabled_maps: List of map names to generate (e.g. ["albedo", "normal"])
        progress_cb: Optional callback(fraction: float, message: str)
        auto_generate_refs: Generate references before texture gen if none exist
        force_new_spec: Force Gemini to regenerate spec (skip cache)

    Returns:
        Dict of map_name → saved file path, or None on failure.
    """
    def _progress(frac: float, msg: str):
        log_debug(f"[{frac:.0%}] {msg}", _MODULE)
        if progress_cb:
            progress_cb(frac, msg)

    project_name = get_project_name(context)

    # ── Step 1: Load tag and engine ────────────────────────────────────────────
    _progress(0.0, "Loading semantic tag and engine preset...")

    tag_def = get_tag(tag_id)
    if tag_def is None:
        log_error(f"Unknown semantic tag: '{tag_id}'", _MODULE)
        return None

    engine_spec = ENGINE_PRESETS.get(engine_id)
    if engine_spec is None:
        log_error(f"Unknown engine preset: '{engine_id}'", _MODULE)
        return None

    # Mark which maps are enabled (override preset)
    engine_spec = _apply_enabled_maps(engine_spec, enabled_maps)

    # ── Step 2: Get viewport screenshot ───────────────────────────────────────
    _progress(0.05, "Loading viewport context...")
    viewport_path = get_latest_capture(context, project_name)
    viewport_b64 = image_to_base64(viewport_path) if viewport_path else None

    # ── Step 3: Generate / retrieve reference images ──────────────────────────
    _progress(0.1, "Checking reference images...")
    ref_paths = []
    if auto_generate_refs:
        ref_paths = get_or_generate_references(
            context=context,
            api_key=api_key,
            uv_region_id=uv_region_id,
            tag_definition=tag_def,
            project_name=project_name,
        )
    ref_b64_list = [image_to_base64(p) for p in ref_paths if p]
    ref_b64_list = [b for b in ref_b64_list if b]

    # ── Step 4: Gemini 3 Flash → JSON spec ────────────────────────────────────
    _progress(0.2, "Calling Gemini 3 Flash for texture spec...")

    spec = get_texture_spec(
        context=context,
        api_key=api_key,
        tag_id=tag_id,
        tag_definition=tag_def,
        engine_spec=engine_spec,
        project_name=project_name,
        viewport_image_path=viewport_path,
        reference_image_paths=ref_paths,
        force_regenerate=force_new_spec,
    )

    if spec is None:
        log_error("Gemini spec generation failed.", _MODULE)
        return None

    log_info(f"Texture spec: {spec}", _MODULE)

    # ── Step 5: Nano Banana → texture images ──────────────────────────────────
    _progress(0.4, f"Generating {len(enabled_maps)} texture maps via Nano Banana...")

    engine_map_specs = {
        name: {
            "size": cfg.get("size", 2048),
            "format": cfg.get("format", "sRGB"),
            "file_ext": cfg.get("file_ext", "png"),
        }
        for name, cfg in engine_spec["supported_maps"].items()
        if name in enabled_maps
    }

    visual_context = []
    if viewport_b64:
        visual_context.append(viewport_b64)
    visual_context.extend(ref_b64_list)

    api_response = generate_textures(
        api_key=api_key,
        json_spec=spec,
        maps_to_generate=enabled_maps,
        engine_specs=engine_map_specs,
        visual_context_b64=visual_context if visual_context else None,
    )

    if api_response is None:
        log_error("Nano Banana texture generation failed.", _MODULE)
        return None

    # ── Step 6: Process textures via Rust backend ──────────────────────────────
    _progress(0.7, "Processing textures with Rust backend...")

    maps_response = api_response.get("maps", {})
    processed_files = _process_and_save_maps(
        context=context,
        maps_response=maps_response,
        engine_map_specs=engine_map_specs,
        uv_region_id=uv_region_id,
        project_name=project_name,
    )

    if not processed_files:
        log_error("No texture maps could be saved.", _MODULE)
        return None

    # ── Step 7: Save to cache ─────────────────────────────────────────────────
    _progress(0.85, "Saving to cache...")

    version_dir = save_texture_version(
        context=context,
        uv_region_id=uv_region_id,
        texture_files=processed_files,
        metadata={
            "tag_id": tag_id,
            "engine_id": engine_id,
            "maps": enabled_maps,
            "gemini_spec": spec,
        },
    )

    # ── Step 8: Create Blender material ──────────────────────────────────────
    _progress(0.92, "Creating Blender material...")

    mat_name = f"NB_{uv_region_id}_{tag_id}_{engine_id}"
    mat = create_pbr_material(mat_name, processed_files)

    obj = context.active_object
    if obj:
        apply_material_to_object(context, obj, mat)

    _progress(1.0, f"Done! Generated {len(processed_files)} maps.")
    log_info(f"Pipeline complete. Maps: {list(processed_files.keys())}", _MODULE)

    return processed_files


def _apply_enabled_maps(engine_spec: dict, enabled_maps: List[str]) -> dict:
    """Return a copy of engine_spec with enabled flags set based on enabled_maps list."""
    import copy
    spec_copy = copy.deepcopy(engine_spec)
    for map_name, cfg in spec_copy["supported_maps"].items():
        cfg["enabled"] = map_name in enabled_maps
    return spec_copy


def _process_and_save_maps(
    context,
    maps_response: dict,
    engine_map_specs: dict,
    uv_region_id: str,
    project_name: str,
) -> Dict[str, str]:
    """
    Process received texture maps through Rust backend and save to temp dir.

    Returns dict of map_name → file_path.
    """
    import tempfile

    output_dir = _get_temp_output_dir(context, project_name, uv_region_id)
    os.makedirs(output_dir, exist_ok=True)

    processed = {}

    for map_name, map_data in maps_response.items():
        image_b64 = map_data.get("data") or map_data.get("image_data")
        if not image_b64:
            continue

        map_cfg = engine_map_specs.get(map_name, {})
        target_size = map_cfg.get("size", 2048)
        color_space = map_cfg.get("format", "sRGB")
        file_ext = map_cfg.get("file_ext", "png")

        # Try Rust processing
        final_b64 = _rust_process_map(image_b64, target_size, file_ext, color_space)
        if final_b64 is None:
            final_b64 = image_b64  # Use raw if Rust unavailable

        # Save to temp file
        filepath = os.path.join(output_dir, f"{map_name}.{file_ext}")
        if base64_to_file(final_b64, filepath):
            processed[map_name] = filepath
            log_debug(f"Saved map: {map_name}.{file_ext}", _MODULE)
        else:
            log_error(f"Failed to save map: {map_name}", _MODULE)

    return processed


def _rust_process_map(image_b64: str, target_size: int,
                      output_format: str, color_space: str) -> Optional[str]:
    """Process a texture map via Rust backend. Returns processed base64 or None."""
    try:
        from .rust_bridge import get_rust_bridge
        bridge = get_rust_bridge()
        if not bridge.is_running():
            return None

        result = bridge.process_texture(
            image_data_b64=image_b64,
            target_size=target_size,
            output_format=output_format,
            color_space=color_space,
        )
        return result.get("image_data")
    except Exception as e:
        log_debug(f"Rust processing skipped: {e}", _MODULE)
        return None


def _get_temp_output_dir(context, project_name: str, uv_region_id: str) -> str:
    base = get_cache_base_path(context)
    safe_proj = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
    return os.path.join(base, safe_proj, uv_region_id, "_temp_output")
