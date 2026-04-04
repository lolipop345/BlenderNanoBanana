"""
BlenderNanoBanana - Texture Generation Pipeline (pure Python)

Flow:
  1. Load engine preset
  2. Visual context (viewport screenshot + UV layout PNG)
     — UV layout is already annotated with island IDs and material tags
  3. Gemini Flash: prompt + annotated UV image → JSON material spec
  4. Gemini Image API: JSON spec + UV layout + viewport → texture maps
  5. Save to cache
"""

import os
import threading
from typing import Optional, Dict, List, Callable

from .prompt_engineer import get_spec_from_prompt
from .cache_manager import save_texture_version, get_cache_base_path, get_project_name
from ..api.google_vision import generate_textures
from ..utils.image_processing import base64_to_file, image_to_base64
from ..utils.logging import log_info, log_debug, log_error
from ..config.engine_presets import ENGINE_PRESETS

_MODULE = "TextureGenerator"

_cancel_flag = threading.Event()


def request_cancel():
    _cancel_flag.set()


def run_generation_pipeline(
    context,
    api_key: str,
    prompt: str,
    uv_region_id: str,
    engine_id: str,
    enabled_maps: List[str],
    progress_cb: Optional[Callable[[float, str], None]] = None,
    viewport_path: Optional[str] = None,
    uv_layout_path: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """
    Generate PBR texture maps from a text prompt + visual context.

    Returns dict of map_name → saved file path, or None on failure/cancel.
    """
    _cancel_flag.clear()

    def _p(frac: float, msg: str):
        log_debug(f"[{frac:.0%}] {msg}", _MODULE)
        if progress_cb:
            progress_cb(frac, msg)

    def _cancelled() -> bool:
        if _cancel_flag.is_set():
            _p(0.0, "Cancelled.")
            return True
        return False

    # ── 1. Engine preset ──────────────────────────────────────────────────────
    _p(0.0, "Loading engine preset...")
    engine_spec = ENGINE_PRESETS.get(engine_id)
    if engine_spec is None:
        log_error(f"Unknown engine preset: '{engine_id}'", _MODULE)
        return None
    engine_spec = _apply_enabled_maps(engine_spec, enabled_maps)

    if _cancelled(): return None

    # ── 2. Visual context ─────────────────────────────────────────────────────
    _p(0.05, "Loading visual context...")
    viewport_b64  = image_to_base64(viewport_path)  if viewport_path  else None
    uv_layout_b64 = image_to_base64(uv_layout_path) if uv_layout_path else None

    if _cancelled(): return None

    # ── 3. Gemini Flash: prompt + annotated UV image → JSON material spec ─────
    # The UV layout image already has island IDs and material tags drawn on it.
    _p(0.12, "Generating material spec...")
    spec = get_spec_from_prompt(
        api_key=api_key,
        user_prompt=prompt,
        viewport_image_path=viewport_path,
        uv_layout_path=uv_layout_path,
    )
    if spec is None:
        raise RuntimeError(
            "Material spec failed — check your Google API key in Addon Preferences."
        )

    if _cancelled(): return None

    # ── 4. Gemini Image API → texture maps ────────────────────────────────────
    _p(0.25, f"Generating {len(enabled_maps)} map(s)...")

    engine_map_specs = {
        name: {
            "size":     cfg.get("size",     2048),
            "format":   cfg.get("format",   "sRGB"),
            "file_ext": cfg.get("file_ext", "png"),
        }
        for name, cfg in engine_spec["supported_maps"].items()
        if name in enabled_maps
    }

    # UV layout first (model should see the UV structure before the viewport)
    visual_context = []
    if uv_layout_b64: visual_context.append(uv_layout_b64)
    if viewport_b64:  visual_context.append(viewport_b64)

    def _map_p(frac: float, msg: str):
        _p(0.25 + frac * 0.65, msg)

    api_response = generate_textures(
        api_key=api_key,
        json_spec=spec,
        maps_to_generate=enabled_maps,
        engine_specs=engine_map_specs,
        visual_context_b64=visual_context or None,
        progress_cb=_map_p,
        cancel_flag=_cancel_flag,
    )

    if _cancelled(): return None
    if api_response is None:
        raise RuntimeError(
            "Gemini Image API returned no image. "
            "The model may have blocked the request or the API quota is exceeded."
        )

    # ── 6. Save maps ──────────────────────────────────────────────────────────
    _p(0.92, "Saving maps...")
    project_name = get_project_name(context)
    saved = _save_maps(
        context=context,
        maps_response=api_response.get("maps", {}),
        engine_map_specs=engine_map_specs,
        uv_region_id=uv_region_id,
        project_name=project_name,
    )
    if not saved:
        raise RuntimeError(
            "Maps were generated but could not be saved to disk. "
            "Check cache path in Addon Preferences."
        )

    # ── 7. Cache version entry ────────────────────────────────────────────────
    _p(0.97, "Saving to cache...")
    save_texture_version(
        context=context,
        uv_region_id=uv_region_id,
        texture_files=saved,
        metadata={
            "prompt": prompt,
            "engine_id": engine_id,
            "maps": enabled_maps,
            "gemini_spec": spec,
        },
    )

    _p(1.0, f"Done! {len(saved)} map(s) generated.")
    log_info(f"Pipeline complete: {list(saved.keys())}", _MODULE)
    return saved


# ── Helpers ───────────────────────────────────────────────────────────────────

def _apply_enabled_maps(engine_spec: dict, enabled_maps: List[str]) -> dict:
    import copy
    spec = copy.deepcopy(engine_spec)
    for name, cfg in spec["supported_maps"].items():
        cfg["enabled"] = name in enabled_maps
    return spec


def _save_maps(
    context,
    maps_response: dict,
    engine_map_specs: dict,
    uv_region_id: str,
    project_name: str,
) -> Dict[str, str]:
    out_dir = _output_dir(context, project_name, uv_region_id)
    os.makedirs(out_dir, exist_ok=True)
    saved = {}
    for map_name, map_data in maps_response.items():
        b64 = map_data.get("data") or map_data.get("image_data")
        if not b64:
            continue
        ext  = engine_map_specs.get(map_name, {}).get("file_ext", "png")
        path = os.path.join(out_dir, f"{map_name}.{ext}")
        if base64_to_file(b64, path):
            saved[map_name] = path
    return saved


def _output_dir(context, project_name: str, uv_region_id: str) -> str:
    base = get_cache_base_path(context)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
    return os.path.join(base, safe, uv_region_id, "_output")
