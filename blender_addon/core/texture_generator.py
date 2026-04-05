"""
BlenderNanoBanana - Texture Generation Pipeline (Single-Call UV Atlas Mode)

The CORRECT and CHEAP approach:
  - Send ONE clean UV wireframe image to Gemini
  - Describe each island's material in the text prompt
  - Gemini generates the complete UV atlas in ONE call per map type
  - Total API calls = number of enabled maps (e.g. 5 maps = 5 calls)
  - No compositing, no per-tag loops, no post-processing

Cost comparison for 29 UV islands, 3 tags, 5 maps:
  Old (per-tag):   3 × 5 = 15 calls
  Old (per-island): 29 × 5 = 145 calls
  NEW (per-map):   5 calls  ← this file
"""

import os
import base64
import threading
import concurrent.futures
from typing import Optional, Dict, List, Callable

from .cache_manager import save_texture_version, get_cache_base_path, get_project_name
from ..api.google_vision import generate_uv_atlas_map
from ..utils.image_processing import base64_to_file
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
    island_data: Optional[List[Dict]] = None,
    island_tags: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, str]]:
    """
    Generate a full UV atlas texture set with ONE Gemini call per map type.

    Args:
        prompt:       User's base description (e.g. "Soviet soldier")
        island_tags:  {island_id: "Metal"} — the per-island material assignments
        island_data:  UV island list from nb_uv_analysis (for position descriptions)
        uv_layout_path: Path to the clean UV wireframe PNG (sent to Gemini)

    Returns: {map_name: file_path} or None on failure.
    """
    _cancel_flag.clear()

    def _p(frac: float, msg: str):
        log_debug(f"[{frac:.0%}] {msg}", _MODULE)
        if progress_cb:
            progress_cb(frac, msg)

    # ── 1. Engine preset ──────────────────────────────────────────────────────
    _p(0.0, "Loading engine preset...")
    engine_spec = ENGINE_PRESETS.get(engine_id)
    if engine_spec is None:
        log_error(f"Unknown engine preset: '{engine_id}'", _MODULE)
        return None

    engine_map_specs = {
        name: {
            "size":     cfg.get("size",     2048),
            "format":   cfg.get("format",   "sRGB"),
            "file_ext": cfg.get("file_ext", "png"),
        }
        for name, cfg in engine_spec["supported_maps"].items()
        if name in enabled_maps
    }

    # ── 2. Build island material description ──────────────────────────────────
    _p(0.02, "Building island descriptions...")
    island_material_desc = _build_island_desc(island_data or [], island_tags or {})
    log_info(f"Island material description: {island_material_desc[:200]}", _MODULE)

    # ── 3. Load UV wireframe (clean, no annotation) ───────────────────────────
    _p(0.04, "Loading UV layout...")
    uv_wireframe_b64 = _load_and_compress_uv(uv_layout_path)

    if _cancel_flag.is_set():
        return None

    # ── 4. Generate ALL maps in parallel (one API call each) ─────────────────
    total_maps = len(enabled_maps)
    completed = 0
    completed_lock = threading.Lock()

    _p(0.06, f"Generating {total_maps} UV atlas maps in parallel...")

    # Create ONE shared client — avoids N separate httpx connection pools
    from ..api.google_vision import make_shared_client
    shared_client = make_shared_client(api_key)

    results: Dict[str, str] = {}  # map_name → base64
    map_errors: Dict[str, str] = {}

    def gen_map(map_name: str):
        if _cancel_flag.is_set():
            return map_name, None, None
        try:
            image_b64, mime = generate_uv_atlas_map(
                api_key=api_key,
                map_name=map_name,
                base_prompt=prompt,
                island_material_desc=island_material_desc,
                uv_wireframe_b64=uv_wireframe_b64,
                map_cfg=engine_map_specs.get(map_name, {}),
                client=shared_client,
            )
            return map_name, image_b64, None
        except Exception as e:
            return map_name, None, e

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(total_maps, 8)) as exc:
        futures = {exc.submit(gen_map, m): m for m in enabled_maps}
        for future in concurrent.futures.as_completed(futures):
            map_name, b64, err = future.result()
            with completed_lock:
                completed += 1
                frac = 0.06 + (completed / total_maps) * 0.84
            if err:
                err_str = str(err)
                map_errors[map_name] = err_str
                log_error(f"Failed [{map_name}]: {err_str}", _MODULE)
                _p(frac, f"✗ {map_name}: {err_str[:80]}")
            elif b64:
                results[map_name] = b64
                _p(frac, f"✓ {map_name} ({completed}/{total_maps})")

    if _cancel_flag.is_set():
        return None

    if not results:
        # Surface the actual per-map errors so the user sees what went wrong
        details = "; ".join(f"{k}: {v[:120]}" for k, v in map_errors.items())
        raise RuntimeError(f"No images generated. Errors — {details}")

    # ── 5. Save maps ──────────────────────────────────────────────────────────
    _p(0.91, "Saving maps...")
    out_dir = _output_dir(context, get_project_name(context), uv_region_id)
    os.makedirs(out_dir, exist_ok=True)
    saved: Dict[str, str] = {}

    for map_name, b64 in results.items():
        ext  = engine_map_specs.get(map_name, {}).get("file_ext", "png")
        path = os.path.join(out_dir, f"{map_name}.{ext}")
        if base64_to_file(b64, path):
            saved[map_name] = path

    if not saved:
        raise RuntimeError("Maps generated but could not be saved to disk.")

    # ── 6. Cache entry ─────────────────────────────────────────────────────────
    _p(0.97, "Saving to cache...")
    save_texture_version(
        context=context,
        uv_region_id=uv_region_id,
        texture_files=saved,
        metadata={
            "prompt": prompt,
            "engine_id": engine_id,
            "maps": enabled_maps,
            "island_material_desc": island_material_desc,
        },
    )

    _p(1.0, f"Done! {len(saved)} map(s) generated.")
    log_info(f"Pipeline complete: {list(saved.keys())}", _MODULE)
    return saved


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_island_desc(island_data: List[Dict], island_tags: Dict[str, str]) -> str:
    """
    Build a strict, unambiguous description of each tagged UV island's orientation.

    Uses exact degree values so Gemini can orient textures correctly.

    Example output:
      "uv_001(upright)=Metal; uv_002(rotated_CW_90deg)=Skin; uv_003(mirrored_rotated_CCW_45deg)=Wood"

    Positive rotation = CW as seen in the UV layout image.
    """
    if not island_data or not island_tags:
        return ""

    parts = []
    for island in island_data:
        iid = island.get("id", "?")
        tag = island_tags.get(iid)
        if not tag:
            continue

        rot     = island.get("rotation_deg", 0.0)
        flipped = island.get("is_flipped", False)
        orient  = _orient_label(rot, flipped)
        
        parts.append(f"{iid}({orient})={tag}")

    return "; ".join(parts)


def _orient_label(rot: float, flipped: bool) -> str:
    """
    Return a strict, unambiguous orientation string for a UV island.

    Args:
        rot:     Rotation in degrees, positive = CW as seen in the UV layout image.
        flipped: True if the island has CW winding (mirrored geometry).

    Examples:
        ( 0.0, False) → "upright"
        (90.0, False) → "rotated_CW_90deg"
        (-45.0, False) → "rotated_CCW_45deg"
        (180.0, False) → "upside_down"
        ( 0.0, True)  → "mirrored"
        (90.0, True)  → "mirrored_rotated_CW_90deg"
    """
    UPRIGHT_THRESH = 8.0  # degrees — below this, treat as upright

    rot_abs = abs(rot)
    is_upside_down = rot_abs > 172.0  # ±180° ± 8° tolerance

    if flipped:
        if is_upside_down:
            return "mirrored_upside_down"
        if rot_abs < UPRIGHT_THRESH:
            return "mirrored"
        direction = "CW" if rot > 0 else "CCW"
        return f"mirrored_rotated_{direction}_{rot_abs:.0f}deg"

    if is_upside_down:
        return "upside_down"
    if rot_abs < UPRIGHT_THRESH:
        return "upright"

    direction = "CW" if rot > 0 else "CCW"
    return f"rotated_{direction}_{rot_abs:.0f}deg"


def _load_and_compress_uv(uv_layout_path: Optional[str]) -> Optional[str]:
    """
    Load the UV layout PNG, compress to 768px JPEG for fast upload.
    Returns base64 string or None.
    """
    if not uv_layout_path or not os.path.isfile(uv_layout_path):
        return None
    try:
        import io
        from PIL import Image
        img = Image.open(uv_layout_path).convert("RGB")
        img.thumbnail((512, 512))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        log_error(f"UV layout compression failed: {e}", _MODULE)
        # Fallback: raw file
        try:
            with open(uv_layout_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return None


def _output_dir(context, project_name: str, uv_region_id: str) -> str:
    base = get_cache_base_path(context)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
    return os.path.join(base, safe, uv_region_id, "_output")
