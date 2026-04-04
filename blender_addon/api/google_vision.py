"""
BlenderNanoBanana - Gemini Image API Integration

Generates PBR texture maps and reference images using the Gemini 3.1 Flash Image
model (gemini-3.1-flash-image-preview) via the standard generateContent endpoint.

Each texture map is generated with a separate API call — the Gemini image API
produces one image per call.

Endpoint:
  POST https://generativelanguage.googleapis.com/v1beta/models/
       gemini-3.1-flash-image-preview:generateContent

Request:
  {
    "contents": [
      {
        "role": "user",
        "parts": [
          {"text": "<prompt>"},
          {"inline_data": {"mime_type": "image/png", "data": "<base64>"}},  # optional refs
          ...
        ]
      }
    ],
    "generationConfig": {
      "responseModalities": ["IMAGE"],
      "imageConfig": {"aspectRatio": "1:1", "imageSize": "2K"}
    }
  }

Response:
  {
    "candidates": [{
      "content": {
        "parts": [
          {"inline_data": {"mime_type": "image/png", "data": "<base64>"}}
        ]
      }
    }]
  }
"""

from typing import Optional, Dict, Any, List

from .api_client import APIClient
from ..config.constants import (
    GEMINI_IMAGE_MODEL_ID,
    GEMINI_API_BASE_URL,
    GEMINI_IMAGE_TIMEOUT,
    GEMINI_IMAGE_RETRY_COUNT,
)
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "GeminiImageAPI"

_ENDPOINT = f"/v1beta/models/{GEMINI_IMAGE_MODEL_ID}:generateContent"

# Size mapping: texture pixel size → Gemini imageSize token.
# Minimum is "1K" — gemini-3.1-flash-image-preview doesn't reliably support "512".
_SIZE_MAP = {
    512:  "1K",
    1024: "1K",
    2048: "2K",
    4096: "4K",
}

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

    Calls the API once per requested map (Gemini generates 1 image per call).

    Args:
        api_key: Google API key
        json_spec: Gemini-generated texture parameter spec
        maps_to_generate: List of map names (e.g. ["albedo", "normal"])
        engine_specs: Per-map config {"albedo": {"size": 2048, "format": "sRGB"}, ...}
        visual_context_b64: Optional list of base64-encoded reference/viewport images
        progress_cb: Optional callable(frac: float, msg: str) for per-map progress

    Returns:
        {"maps": {"albedo": {"data": b64, "mime_type": "image/png"}, ...}} or None.
    """
    client = APIClient(api_key=api_key, base_url=GEMINI_API_BASE_URL)

    results: Dict[str, Dict[str, str]] = {}
    total = len(maps_to_generate)

    for idx, map_name in enumerate(maps_to_generate):
        if cancel_flag is not None and cancel_flag.is_set():
            log_info("Generation cancelled by user.", _MODULE)
            break
        if progress_cb:
            progress_cb(idx / total, f"Generating {map_name}...")

        map_cfg = engine_specs.get(map_name, {})
        size_px = map_cfg.get("size", 2048)
        image_size = _SIZE_MAP.get(size_px, "2K")

        prompt = _build_map_prompt(map_name, json_spec, map_cfg)
        payload = _build_image_payload(prompt, image_size, visual_context_b64)

        log_debug(f"Requesting {map_name} map ({image_size})...", _MODULE)
        log_info(f"Generating {map_name} ({idx+1}/{total})...", _MODULE)

        image_b64, mime_type = _call_image_api(client, payload, map_name)
        if image_b64:
            results[map_name] = {"data": image_b64, "mime_type": mime_type}
            log_info(f"Done: {map_name}", _MODULE)
        else:
            log_error(f"Failed to generate: {map_name} — continuing with other maps", _MODULE)

    if not results:
        return None

    return {"maps": results}


def generate_reference_image(
    api_key: str,
    tag_definition: Dict[str, Any],
    viewport_b64: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a single reference image for a UV region.

    Args:
        api_key: Google API key
        tag_definition: Semantic tag definition dict
        viewport_b64: Optional base64-encoded viewport screenshot

    Returns:
        Base64-encoded PNG image string, or None on failure.
    """
    client = APIClient(api_key=api_key, base_url=GEMINI_API_BASE_URL)

    tag_name = tag_definition.get("name", "material")
    description = tag_definition.get("description", "")
    realism = tag_definition.get("realism", "realistic")
    detail = tag_definition.get("detail_level", "medium")

    prompt = (
        f"Generate a {realism} reference image for a '{tag_name}' material texture. "
        f"Description: {description}. "
        f"Detail level: {detail}. "
        "The image should show the material's surface texture clearly, "
        "suitable for use as a PBR texture reference. "
        "Square composition, close-up surface view."
    )

    context_images = [viewport_b64] if viewport_b64 else None
    payload = _build_image_payload(prompt, "1K", context_images)

    log_debug(f"Generating reference image for tag '{tag_name}'...", _MODULE)

    image_b64, _ = _call_image_api(client, payload, "reference")
    if image_b64:
        log_info(f"Reference image generated for '{tag_name}'.", _MODULE)
    return image_b64


# ── Internal helpers ───────────────────────────────────────────────────────────

def _build_map_prompt(map_name: str, spec: Dict[str, Any], map_cfg: Dict[str, Any]) -> str:
    """Build the text prompt for a specific texture map."""
    map_desc = _MAP_PROMPTS.get(map_name, f"{map_name} texture map")

    material = spec.get("material_type", "generic material")
    detail = spec.get("detail_level", "medium")
    surface = spec.get("surface_characteristic", "")
    roughness = spec.get("roughness_profile", "")
    imperfection = spec.get("imperfection_level", "subtle")
    pattern = spec.get("texture_pattern", "")
    wear = spec.get("wear_level", "new")
    color_temp = spec.get("color_temperature", "neutral")
    color_var = spec.get("color_variation", "subtle_variation")
    special = spec.get("special_properties", "")
    engine_format = map_cfg.get("format", "")

    parts = [
        f"Generate a seamless, tileable {map_desc}.",
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
    if engine_format:
        parts.append(f"Color space: {engine_format}.")
    parts.append(
        "Square 1:1 aspect ratio. High quality, professional game asset."
        " No text, no watermarks, no UI elements."
    )

    return " ".join(parts)


def _build_image_payload(
    prompt: str,
    image_size: str,
    context_images_b64: Optional[List[str]],
) -> dict:
    """Build the Gemini generateContent payload for image generation."""
    parts = [{"text": prompt}]

    # Attach reference/viewport images as inline_data (API max 14 images)
    if context_images_b64:
        for img_b64 in context_images_b64[:14]:
            if img_b64:
                parts.append({
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": img_b64,
                    }
                })

    return {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {
                "aspectRatio": "1:1",   # strict — never change this
                "imageSize": image_size,
            },
        },
    }


def _call_image_api(
    client: APIClient,
    payload: dict,
    map_name: str,
) -> tuple:
    """
    POST to the Gemini image endpoint and extract the image from the response.

    Returns:
        (base64_str, mime_type) or (None, None) on failure.
    """
    for attempt in range(1, GEMINI_IMAGE_RETRY_COUNT + 1):
        try:
            response = client.post_json(_ENDPOINT, payload, timeout=GEMINI_IMAGE_TIMEOUT)
            b64, mime = _parse_image_response(response)
            if b64:
                return b64, mime
            # Log what the API actually returned so we can diagnose
            _log_response_debug(response, map_name, attempt)
        except Exception as e:
            log_error(f"API error for '{map_name}' (attempt {attempt}): {e}", _MODULE, e)

    return None, None


def _log_response_debug(response: dict, map_name: str, attempt: int):
    """Log a concise summary of a non-image response to console for debugging."""
    try:
        candidates = response.get("candidates", [])
        if not candidates:
            # Could be a promptFeedback block
            feedback = response.get("promptFeedback", {})
            reason = feedback.get("blockReason", "unknown")
            print(f"[NanaBanana::GeminiImageAPI] '{map_name}' attempt {attempt}: "
                  f"no candidates — blockReason={reason}")
            log_error(f"Generation blocked for '{map_name}': {reason}", _MODULE)
            return

        cand = candidates[0]
        finish = cand.get("finishReason", "?")
        parts = cand.get("content", {}).get("parts", [])
        text_parts = [p.get("text", "")[:120] for p in parts if "text" in p]
        print(f"[NanaBanana::GeminiImageAPI] '{map_name}' attempt {attempt}: "
              f"finishReason={finish}, text={text_parts}")
        log_error(f"No image for '{map_name}' (finish={finish})", _MODULE)
    except Exception:
        log_error(f"No image in response for '{map_name}' (attempt {attempt}).", _MODULE)


def _parse_image_response(response: dict) -> tuple:
    """
    Extract inline_data image from a Gemini generateContent response.

    Returns:
        (base64_str, mime_type) or (None, None).
    """
    try:
        candidates = response.get("candidates", [])
        if not candidates:
            return None, None

        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inline_data")
            if inline and inline.get("data"):
                return inline["data"], inline.get("mime_type", "image/png")

        return None, None
    except (KeyError, IndexError):
        return None, None
