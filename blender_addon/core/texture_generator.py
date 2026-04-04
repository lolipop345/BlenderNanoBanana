"""
BlenderNanoBanana - Texture Generation Orchestrator

Pipeline:
  1. Load tag + engine preset
  2. Viewport screenshot + UV layout (pre-computed on main thread)
  3. AI mesh auto-describe (Gemini 3 Flash text call, optional)
  4. Gemini 3 Flash → JSON texture spec
  5. Gemini Image API → texture images (UV layout + viewport as visual context)
  6. Process via Rust backend
  7. Save to cache

Reference image generation has been removed — UV layout + viewport gives the
AI everything it needs to generate accurate textures.
"""

import os
import threading
from typing import Optional, Dict, Any, List, Callable

from .prompt_engineer import get_texture_spec, get_mesh_description
from .cache_manager import (
    save_texture_version,
    get_cache_base_path,
    get_project_name,
)
from .viewport_handler import get_latest_capture
from .semantic_manager import get_tag
from ..api.google_vision import generate_textures
from ..utils.image_processing import base64_to_file, image_to_base64
from ..utils.logging import log_info, log_debug, log_error
from ..config.engine_presets import ENGINE_PRESETS

_MODULE = "TextureGenerator"

# Cancel flag — set by cancel operator, cleared at pipeline start
_cancel_flag = threading.Event()


def request_cancel():
    """Signal the running pipeline to stop at the next checkpoint."""
    _cancel_flag.set()


def run_generation_pipeline(
    context,
    api_key: str,
    uv_region_id: str,
    tag_id: str,
    engine_id: str,
    enabled_maps: List[str],
    progress_cb: Optional[Callable[[float, str], None]] = None,
    force_new_spec: bool = False,
    viewport_path: Optional[str] = None,
    uv_layout_path: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """
    Run the texture generation pipeline.

    Returns dict of map_name → saved file path, or None on failure/cancel.
    """
    _cancel_flag.clear()

    def _progress(frac: float, msg: str):
        log_debug(f"[{frac:.0%}] {msg}", _MODULE)
        if progress_cb:
            progress_cb(frac, msg)

    def _cancelled() -> bool:
        if _cancel_flag.is_set():
            _progress(0.0, "Cancelled.")
            return True
        return False

    project_name = get_project_name(context)

    # ── Step 1: Load tag and engine ───────────────────────────────────────────
    _progress(0.0, "Loading tag and engine preset...")
    if _cancelled():
        return None

    tag_def = get_tag(tag_id)
    if tag_def is None:
        log_error(f"Unknown semantic tag: '{tag_id}'", _MODULE)
        return None

    engine_spec = ENGINE_PRESETS.get(engine_id)
    if engine_spec is None:
        log_error(f"Unknown engine preset: '{engine_id}'", _MODULE)
        return None

    engine_spec = _apply_enabled_maps(engine_spec, enabled_maps)

    # ── Step 2: Load visual context ───────────────────────────────────────────
    _progress(0.05, "Loading visual context...")
    if _cancelled():
        return None

    if viewport_path is None:
        viewport_path = get_latest_capture(context, project_name)
    viewport_b64 = image_to_base64(viewport_path) if viewport_path else None
    uv_layout_b64 = image_to_base64(uv_layout_path) if uv_layout_path else None

    # ── Step 3: AI mesh auto-description ─────────────────────────────────────
    _progress(0.08, "AI analysing mesh...")
    if _cancelled():
        return None

    mesh_description = None
    try:
        mesh_description = get_mesh_description(
            api_key=api_key,
            viewport_image_path=viewport_path,
            uv_layout_path=uv_layout_path,
        )
    except Exception as e:
        log_debug(f"Mesh description skipped: {e}", _MODULE)

    if _cancelled():
        return None

    # ── Step 4: Gemini 3 Flash → JSON spec ───────────────────────────────────
    _progress(0.15, "Generating texture spec...")

    spec = get_texture_spec(
        context=context,
        api_key=api_key,
        tag_id=tag_id,
        tag_definition=tag_def,
        engine_spec=engine_spec,
        project_name=project_name,
        viewport_image_path=viewport_path,
        reference_image_paths=[],
        force_regenerate=force_new_spec,
        mesh_description=mesh_description,
    )

    if spec is None:
        log_error("Gemini spec generation failed.", _MODULE)
        return None

    if _cancelled():
        return None

    log_info(f"Texture spec: {spec}", _MODULE)

    # ── Step 5: Gemini Image API → texture maps ───────────────────────────────
    _progress(0.3, f"Generating {len(enabled_maps)} map(s)...")

    engine_map_specs = {
        name: {
            "size": cfg.get("size", 2048),
            "format": cfg.get("format", "sRGB"),
            "file_ext": cfg.get("file_ext", "png"),
        }
        for name, cfg in engine_spec["supported_maps"].items()
        if name in enabled_maps
    }

    # Build visual context: UV layout first, then viewport
    visual_context = []
    if uv_layout_b64:
        visual_context.append(uv_layout_b64)
    if viewport_b64:
        visual_context.append(viewport_b64)

    def _map_progress(frac: float, msg: str):
        _progress(0.3 + frac * 0.5, msg)

    api_response = generate_textures(
        api_key=api_key,
        json_spec=spec,
        maps_to_generate=enabled_maps,
        engine_specs=engine_map_specs,
        visual_context_b64=visual_context if visual_context else None,
        progress_cb=_map_progress,
        cancel_flag=_cancel_flag,
    )

    if _cancelled():
        return None

    if api_response is None:
        log_error("Texture generation failed.", _MODULE)
        return None

    # ── Step 6: Process via Rust backend ─────────────────────────────────────
    _progress(0.82, "Processing textures...")
    if _cancelled():
        return None

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
    _progress(0.95, "Saving to cache...")

    save_texture_version(
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

    _progress(1.0, f"Done! {len(processed_files)} map(s) generated.")
    log_info(f"Pipeline complete. Maps: {list(processed_files.keys())}", _MODULE)
    return processed_files


def _apply_enabled_maps(engine_spec: dict, enabled_maps: List[str]) -> dict:
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

        final_b64 = _rust_process_map(image_b64, target_size, file_ext, color_space)
        if final_b64 is None:
            final_b64 = image_b64

        filepath = os.path.join(output_dir, f"{map_name}.{file_ext}")
        if base64_to_file(final_b64, filepath):
            processed[map_name] = filepath
            log_debug(f"Saved: {map_name}.{file_ext}", _MODULE)
        else:
            log_error(f"Failed to save: {map_name}", _MODULE)

    return processed


def _rust_process_map(image_b64: str, target_size: int,
                      output_format: str, color_space: str) -> Optional[str]:
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
