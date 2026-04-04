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


def _make_client(api_key: str, timeout_sec: int):
    """
    Create a genai.Client and apply three patches to prevent WriteTimeout:

    1. patch _httpx_client._timeout     → unlimited write/read/pool, 60s connect
    2. patch _async_httpx_client._timeout → same
    3. patch _http_options.timeout = None → SDK passes timeout=None to httpx.send(),
       which then falls back to _timeout (our unlimited value) instead of
       passing timeout=120 which would override our patch.

    Confirmed working in Blender 4.5 LTS + google-genai 1.70.0 + httpx 0.28.1.
    """
    from google import genai
    import httpx

    # connect=60s, write/read/pool = unlimited (None)
    hx_no_timeout = httpx.Timeout(timeout=None, connect=60.0)

    client = genai.Client(api_key=api_key, http_options={"timeout": timeout_sec})

    # Patch 1 & 2: httpx client _timeout attributes
    try:
        client._api_client._httpx_client._timeout = hx_no_timeout
    except Exception as e:
        log_debug(f"Could not patch sync httpx _timeout: {e}", _MODULE)

    try:
        client._api_client._async_httpx_client._timeout = hx_no_timeout
    except Exception as e:
        log_debug(f"Could not patch async httpx _timeout: {e}", _MODULE)

    # Patch 3: _http_options.timeout → None so SDK doesn't override _timeout per-request
    try:
        client._api_client._http_options.timeout = None
    except Exception as e:
        log_debug(f"Could not patch _http_options.timeout: {e}", _MODULE)

    return client


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
    # Timeout is now properly unlimited so we can safely upload these.
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

    # UV-aware prompt suffix — adapts the texture to the UV layout shown
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

    for idx, map_name in enumerate(maps_to_generate):
        if cancel_flag is not None and cancel_flag.is_set():
            log_info("Generation cancelled by user.", _MODULE)
            break

        if progress_cb:
            progress_cb(idx / total, f"Generating {map_name}...")

        map_cfg = engine_specs.get(map_name, {})
        prompt  = _build_map_prompt(map_name, json_spec, map_cfg) + uv_suffix

        # UV layout image goes FIRST, then the text prompt
        request_parts = context_parts + [prompt]

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="1:1"
            )
        )

        log_info(f"Generating {map_name} ({idx+1}/{total}) "
                 f"({'with UV context' if context_parts else 'text-only'})...", _MODULE)

        try:
            image_b64, mime_type = _call_image_api_with_retry(client, request_parts, config, map_name)
            results[map_name] = {"data": image_b64, "mime_type": mime_type}
            log_info(f"Done: {map_name}", _MODULE)
        except Exception as e:
            raise RuntimeError(f"Gemini Image API failed for '{map_name}': {e}") from e

    return {"maps": results} if results else None


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
                last_error = "API returned no candidates."
                log_error(f"No candidates for '{map_name}' (attempt {attempt})", _MODULE)
                continue

            for part in response.candidates[0].content.parts:
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

            # No image found — check for text refusal
            try:
                text_resp = response.text
            except Exception:
                text_resp = None

            if text_resp:
                last_error = f"Model returned text instead of image: {text_resp[:200]}"
            else:
                last_error = "No image data found in response parts."
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
