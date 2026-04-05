"""
BlenderNanoBanana - Gemini Image API Integration

Generates PBR texture maps using the Gemini 3.1 Flash Image model
(gemini-3.1-flash-image-preview) via the google-genai SDK.

UV layout image is sent as compressed context so Gemini adapts
the texture to the mesh UV structure.
"""

from typing import Optional, Dict, Any, List
import base64
import time
import io

from ..config.constants import (
    GEMINI_IMAGE_MODEL_ID,
    GEMINI_IMAGE_TIMEOUT,
    GEMINI_IMAGE_RETRY_COUNT,
)
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "GeminiImageAPI"

# Per-map prompt descriptions
_MAP_PROMPTS = {
    "albedo":       "diffuse color / albedo map, sRGB color space, base color without any lighting or shadows",
    "normal":       "tangent-space normal map, RGB encoded (red=X, green=Y, blue=Z), blue-dominant, for surface micro-detail",
    "roughness":    "roughness / microsurface map, grayscale, white=fully rough, black=perfectly smooth",
    "metallic":     "metallic map, grayscale, white=pure metal, black=non-metal (dielectric)",
    "ao":           "ambient occlusion map, grayscale, baked self-shadowing, white=fully lit, black=occluded",
    "emission":     "emission / self-illumination map, shows glowing or emissive areas in color",
    "height":       "height / parallax map, grayscale, white=surface high points, black=surface low points",
    "displacement": "displacement map, grayscale, white=maximum displacement outward, black=maximum inward",
}


def _compress_b64(b64_str: str, max_size: int = 512) -> str:
    """
    Decode a base64 image, resize to max_size on the longest axis,
    and re-encode as JPEG (much smaller than PNG) for upload.
    Falls back to original data on any error.
    """
    try:
        from PIL import Image
        data = base64.b64decode(b64_str)
        img = Image.open(io.BytesIO(data))
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        log_debug(f"Image compression failed (using original): {e}", _MODULE)
        return b64_str


def _make_client(api_key: str, timeout_sec: int = 120):
    """
    Create a genai.Client with patched httpx timeouts.

    The default httpx write timeout (~5s) is too short for uploading UV wireframe
    images, causing WriteTimeout errors.  We set write/read to 120s while keeping
    connect at 30s, and clear _http_options.timeout so the SDK does not override
    the patched values on each request.
    """
    from google import genai
    import httpx

    client = genai.Client(api_key=api_key, http_options={"timeout": timeout_sec})

    hx_timeout = httpx.Timeout(timeout=120.0, connect=30.0)

    try:
        client._api_client._httpx_client._timeout = hx_timeout
    except Exception as e:
        log_debug(f"Could not patch sync httpx _timeout: {e}", _MODULE)

    try:
        client._api_client._async_httpx_client._timeout = hx_timeout
    except Exception as e:
        log_debug(f"Could not patch async httpx _timeout: {e}", _MODULE)

    try:
        client._api_client._http_options.timeout = None
    except Exception as e:
        log_debug(f"Could not patch _http_options.timeout: {e}", _MODULE)

    return client


def make_shared_client(api_key: str):
    """
    Create a single genai.Client to be reused across all parallel map calls.

    httpx.Client (which backs genai.Client) is thread-safe for concurrent
    requests, so sharing one instance avoids the overhead of opening N separate
    connection pools when generating N maps in parallel.
    """
    return _make_client(api_key)


def generate_textures(
    api_key: str,
    json_spec: Dict[str, Any],
    maps_to_generate: List[str],
    engine_specs: Dict[str, Any],
    visual_context_b64: Optional[List[str]] = None,
    progress_cb=None,
    cancel_flag=None,
) -> Optional[Dict[str, Any]]:
    """
    Generate PBR texture maps via Gemini Image API.

    Sends the UV layout (and optionally viewport) image as compressed context
    so Gemini understands the mesh shape and UV structure. Each map gets a
    UV-aware prompt that instructs Gemini to cover the full UV 0-1 space.

    Returns:
        {"maps": {"albedo": {"data": b64, "mime_type": "image/png"}, ...}} or None.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai is not installed yet. Please wait for dependencies to install.")

    client = _make_client(api_key, GEMINI_IMAGE_TIMEOUT)

    results: Dict[str, Dict[str, str]] = {}
    total = len(maps_to_generate)

    # Compress and prepare context images (UV layout first, then viewport)
    context_parts = []
    if visual_context_b64:
        for img_b64 in visual_context_b64[:2]:   # max 2 images
            if not img_b64:
                continue
            try:
                compressed = _compress_b64(img_b64, max_size=512)
                context_parts.append(
                    types.Part.from_bytes(
                        data=base64.b64decode(compressed),
                        mime_type="image/jpeg"
                    )
                )
                log_debug("Context image compressed and added.", _MODULE)
            except Exception as e:
                log_debug(f"Could not compress context image: {e}", _MODULE)

    # UV-aware prompt suffix
    if context_parts:
        uv_suffix = (
            " The reference image shows the UV layout of the 3D mesh. "
            "Generate a texture that fills the full UV 0-1 space and adapts "
            "to the UV island arrangement. The texture should be consistent "
            "across the entire UV space, not tiled. "
            "1:1 square aspect ratio. No text, no watermarks."
        )
    else:
        uv_suffix = (
            " Seamless, tileable. "
            "1:1 square aspect ratio. No text, no watermarks."
        )

    import concurrent.futures
    import threading
    
    completed_count = 0
    progress_lock = threading.Lock()

    def generate_single_map(map_name: str) -> tuple:
        nonlocal completed_count
        if cancel_flag is not None and cancel_flag.is_set():
            return map_name, None, None

        map_cfg = engine_specs.get(map_name, {})
        prompt  = _build_map_prompt(map_name, json_spec, map_cfg) + uv_suffix
        request_parts = context_parts + [prompt]

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="1:1")
        )

        log_info(f"Generating {map_name} ({'with UV context' if context_parts else 'text-only'})...", _MODULE)

        try:
            image_b64, mime_type = _call_image_api_with_retry(client, request_parts, config, map_name)
            log_info(f"Done: {map_name}", _MODULE)
            
            # Update progress
            with progress_lock:
                completed_count += 1
                if progress_cb and not (cancel_flag and cancel_flag.is_set()):
                    progress_cb(completed_count / total, f"Completed {map_name} ({completed_count}/{total})")
                    
            return map_name, {"data": image_b64, "mime_type": mime_type}, None
        except Exception as e:
            return map_name, None, e

    # Run generations in parallel
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(maps_to_generate), 8)) as executor:
        futures = {executor.submit(generate_single_map, m): m for m in maps_to_generate}
        for future in concurrent.futures.as_completed(futures):
            m_name, m_result, m_err = future.result()
            if m_err:
                log_error(f"Failed '{m_name}': {m_err}", _MODULE)
                raise RuntimeError(f"Gemini Image API failed for '{m_name}': {m_err}") from m_err
            if m_result:
                results[m_name] = m_result

    return {"maps": results} if results else None


def generate_uv_atlas_map(
    api_key: str,
    map_name: str,
    base_prompt: str,
    island_material_desc: str,
    uv_wireframe_b64: Optional[str],
    map_cfg: Dict[str, Any],
    client=None,
) -> tuple:
    """
    Generate ONE UV atlas map (e.g. albedo) in a single Gemini Image API call.

    Sends:
    - The clean UV wireframe image (island outlines, no colors, no labels)
    - Text describing which island area gets which material

    Gemini handles material placement, blending and UV-space composition
    entirely on its own. We just get back the finished atlas.

    Returns (base64_str, mime_type). Raises RuntimeError on failure.
    """
    try:
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai not installed.")

    if client is None:
        client = _make_client(api_key)
    map_desc = _MAP_PROMPTS.get(map_name, f"{map_name} texture map")

    # ── Build the prompt ──────────────────────────────────────────────────────
    if island_material_desc:
        island_section = (
            f"UV island material assignments: {island_material_desc}. "
            "Each entry is: islandID(orientation)=MaterialName. "
            "Apply the specified material texture to each corresponding UV island area "
            "shown in the wireframe image. "
        )
    else:
        island_section = ""

    prompt = (
        f"Generate a high-quality {map_desc} UV texture atlas for a 3D character mesh. "
        f"Overall context: {base_prompt}. "
        f"{island_section}"
        "The reference image shows the UV island wireframe layout in the 0-1 UV space. "
        "Paint each UV island with the correct material. "
        "Areas outside UV islands (black space) should remain dark/empty. "
        "Do NOT show the wireframe lines in the output — only the texture content. "
        "Do NOT include any text, labels, watermarks, or UI elements. "
        "Full 1:1 square aspect ratio. Professional PBR game asset quality."
    )

    # ── Build request parts ───────────────────────────────────────────────────
    request_parts = []

    if uv_wireframe_b64:
        try:
            request_parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(uv_wireframe_b64),
                    mime_type="image/jpeg",
                )
            )
        except Exception as e:
            log_debug(f"UV wireframe attach failed: {e}", _MODULE)

    request_parts.append(prompt)

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="1:1"),
    )

    log_info(
        f"Generating UV atlas: {map_name}"
        f" ({'with UV wireframe' if uv_wireframe_b64 else 'text-only'})"
        f" | islands: {len(island_material_desc.split(';')) if island_material_desc else 0}",
        _MODULE,
    )

    return _call_image_api_with_retry(client, request_parts, config, map_name)


def generate_single_map_call(
    api_key: str,
    map_name: str,
    json_spec: Dict[str, Any],
    map_cfg: Dict[str, Any],
) -> tuple:
    """
    Generate ONE texture map for ONE material tag.
    Called in parallel by texture_generator.ThreadPoolExecutor.

    Each call creates its own patched genai.Client so multiple threads
    don't share state. Returns (base64_str, mime_type).
    Raises RuntimeError on failure.
    """
    try:
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai not installed.")

    client = _make_client(api_key, GEMINI_IMAGE_TIMEOUT)
    prompt = _build_map_prompt(map_name, json_spec, map_cfg)
    prompt += (
        " Seamless, tileable, square 1:1 aspect ratio."
        " Professional PBR game asset. No text, no watermarks, no UI elements."
    )

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="1:1"),
    )

    return _call_image_api_with_retry(client, [prompt], config, map_name)


def generate_reference_image(
    api_key: str,
    tag_definition: Dict[str, Any],
    viewport_b64: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a single reference image for a UV region.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai is not installed yet. Please wait for dependencies to install.")

    client = _make_client(api_key, GEMINI_IMAGE_TIMEOUT)

    tag_name    = tag_definition.get("name", "material")
    description = tag_definition.get("description", "")
    realism     = tag_definition.get("realism", "realistic")
    detail      = tag_definition.get("detail_level", "medium")

    prompt = (
        f"Generate a {realism} reference image for a '{tag_name}' material texture. "
        f"Description: {description}. "
        f"Detail level: {detail}. "
        "The image should show the material's surface texture clearly, "
        "suitable for use as a PBR texture reference. "
        "Square composition, close-up surface view. No text, no watermarks."
    )

    request_parts = [prompt]
    if viewport_b64:
        try:
            compressed = _compress_b64(viewport_b64, max_size=512)
            request_parts = [
                types.Part.from_bytes(data=base64.b64decode(compressed), mime_type="image/jpeg"),
                prompt,
            ]
        except Exception as e:
            log_debug(f"Could not compress viewport for reference: {e}", _MODULE)

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="1:1")
    )

    log_debug(f"Generating reference image for tag '{tag_name}'...", _MODULE)

    try:
        image_b64, _ = _call_image_api_with_retry(client, request_parts, config, "reference")
        log_info(f"Reference image generated for '{tag_name}'.", _MODULE)
        return image_b64
    except Exception as e:
        log_error(f"Failed to generate reference image: {e}", _MODULE, e)
        return None


# ── Internal helpers ───────────────────────────────────────────────────────────

def _build_map_prompt(map_name: str, spec: Dict[str, Any], map_cfg: Dict[str, Any]) -> str:
    """Build the per-map image prompt from the JSON spec."""
    map_desc     = _MAP_PROMPTS.get(map_name, f"{map_name} texture map")
    material     = spec.get("material_type", "generic material")
    detail       = spec.get("detail_level", "medium")
    surface      = spec.get("surface_characteristic", "")
    roughness    = spec.get("roughness_profile", "")
    imperfection = spec.get("imperfection_level", "subtle")
    pattern      = spec.get("texture_pattern", "")
    wear         = spec.get("wear_level", "new")
    color_temp   = spec.get("color_temperature", "neutral")
    color_var    = spec.get("color_variation", "subtle_variation")
    special      = spec.get("special_properties", "")
    fmt          = map_cfg.get("format", "")

    parts = [
        f"Generate a high-quality {map_desc}.",
        f"Material type: {material}.",
        f"Detail level: {detail}.",
    ]
    if surface:
        parts.append(f"Surface characteristic: {surface}.")
    if roughness:
        parts.append(f"Roughness profile: {roughness}.")
    if imperfection:
        parts.append(f"Imperfection level: {imperfection}.")
    if pattern and pattern != "none":
        parts.append(f"Texture pattern: {pattern}.")
    if wear:
        parts.append(f"Wear level: {wear}.")
    if map_name == "albedo":
        parts.append(f"Color temperature: {color_temp}. Color variation: {color_var}.")
    if special:
        parts.append(f"Special properties: {special}.")
    if fmt:
        parts.append(f"Color space: {fmt}.")

    return " ".join(parts)


def _call_image_api_with_retry(
    client: Any,
    parts: list,
    config: Any,
    map_name: str,
) -> tuple:
    """
    Call Gemini Image API with retries. Returns (base64_str, mime_type).
    Raises RuntimeError if all attempts fail.
    """
    last_error = "Unknown error"
    max_attempts = GEMINI_IMAGE_RETRY_COUNT + 1

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL_ID,
                contents=parts,
                config=config,
            )

            if not response.candidates:
                # Check if the prompt was blocked before generation
                try:
                    fb = response.prompt_feedback
                    block = getattr(fb, "block_reason", None)
                    if block:
                        last_error = f"Prompt blocked by safety filter: {block}"
                        log_error(f"[{map_name}] {last_error}", _MODULE)
                        raise RuntimeError(last_error)  # no point retrying a blocked prompt
                except RuntimeError:
                    raise
                except Exception:
                    pass
                last_error = "API returned no candidates (possible safety block or quota)."
                log_error(f"[{map_name}] attempt {attempt}: {last_error}", _MODULE)
                continue

            candidate = response.candidates[0]
            finish_reason = str(getattr(candidate, "finish_reason", "UNKNOWN"))
            log_info(f"[{map_name}] finish_reason={finish_reason}", _MODULE)

            for part in candidate.content.parts:
                # Primary path: inline_data bytes
                inline = getattr(part, "inline_data", None)
                if inline is not None:
                    data = getattr(inline, "data", None)
                    if data:
                        mime = getattr(inline, "mime_type", None) or "image/png"
                        return base64.b64encode(data).decode("utf-8"), mime

                # Fallback: as_image() → PIL Image
                if hasattr(part, "as_image"):
                    try:
                        img = part.as_image()
                        if img is not None:
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/png"
                    except Exception as ae:
                        log_debug(f"as_image() failed: {ae}", _MODULE)

            # No image found — log text response + finish reason
            try:
                text_resp = response.text
            except Exception:
                text_resp = None

            if text_resp:
                last_error = f"finish={finish_reason} — model returned text: {text_resp[:300]}"
            else:
                part_types = [type(p).__name__ for p in candidate.content.parts]
                last_error = f"finish={finish_reason} — no image in parts: {part_types}"
            log_error(f"[{map_name}] attempt {attempt}: {last_error}", _MODULE)

        except Exception as e:
            import traceback
            err_type = type(e).__name__
            err_msg  = str(e)
            log_error(
                f"[{map_name}] attempt {attempt} [{err_type}]: {err_msg}\n{traceback.format_exc()}",
                _MODULE, e
            )
            last_error = f"{err_type}: {err_msg}"

        if attempt < max_attempts:
            wait = 3.0 * attempt
            log_debug(f"Retrying '{map_name}' in {wait:.0f}s...", _MODULE)
            time.sleep(wait)

    raise RuntimeError(f"All attempts failed for '{map_name}': {last_error}")
