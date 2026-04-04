"""
BlenderNanoBanana - Gemini Image API Integration

Generates PBR texture maps using the Gemini 3.1 Flash Image model
(gemini-3.1-flash-image-preview) via the standard generateContent endpoint.

Pipeline context:
  The caller (texture_generator.py) first combines everything —
  user prompt + island tags + UV island positions — into one enriched text,
  then converts it to a JSON material spec via Gemini Flash, then passes
  that spec here. Each map gets a tailored natural-language prompt built
  from the spec fields.

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

    One API call per map. The json_spec (produced from the fully-combined prompt)
    drives per-map natural-language prompts.

    Args:
        api_key: Google API key
        json_spec: Material spec dict from Gemini Flash (already derived from
                   combined prompt = user text + island tags + UV positions)
        maps_to_generate: List of map names e.g. ["albedo", "normal"]
        engine_specs: Per-map config {"albedo": {"size": 2048, "format": "sRGB"}, ...}
        visual_context_b64: Optional list of base64 images (UV layout first, then viewport)
        progress_cb: Optional callable(frac: float, msg: str)
        cancel_flag: Optional threading.Event — set to stop generation

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
        prompt  = _build_map_prompt(map_name, json_spec, map_cfg)
        payload = _build_image_payload(prompt, visual_context_b64)

        log_info(f"Generating {map_name} ({idx+1}/{total})...", _MODULE)

        try:
            image_b64, mime_type = _call_image_api(client, payload, map_name)
        except RuntimeError as e:
            # Re-raise with map context so the UI message is informative
            raise RuntimeError(str(e)) from e

        results[map_name] = {"data": image_b64, "mime_type": mime_type}
        log_info(f"Done: {map_name}", _MODULE)

    return {"maps": results} if results else None


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
    payload = _build_image_payload(prompt, context_images)

    log_debug(f"Generating reference image for tag '{tag_name}'...", _MODULE)

    image_b64, _ = _call_image_api(client, payload, "reference")
    if image_b64:
        log_info(f"Reference image generated for '{tag_name}'.", _MODULE)
    return image_b64


# ── Internal helpers ───────────────────────────────────────────────────────────

def _build_map_prompt(map_name: str, spec: Dict[str, Any], map_cfg: Dict[str, Any]) -> str:
    """
    Build the per-map image prompt from the JSON spec.

    The spec was generated by Gemini Flash from the fully-combined prompt
    (user text + island tags + UV island positions), so all that context
    is already baked into spec's fields.
    """
    map_desc      = _MAP_PROMPTS.get(map_name, f"{map_name} texture map")
    material      = spec.get("material_type", "generic material")
    detail        = spec.get("detail_level", "medium")
    surface       = spec.get("surface_characteristic", "")
    roughness     = spec.get("roughness_profile", "")
    imperfection  = spec.get("imperfection_level", "subtle")
    pattern       = spec.get("texture_pattern", "")
    wear          = spec.get("wear_level", "new")
    color_temp    = spec.get("color_temperature", "neutral")
    color_var     = spec.get("color_variation", "subtle_variation")
    special       = spec.get("special_properties", "")
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
        "Square 1:1 aspect ratio. High quality, professional PBR game asset."
        " No text, no watermarks, no UI elements."
    )

    return " ".join(parts)


def _build_image_payload(
    prompt: str,
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
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": "1:1",
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
    last_error = None
    for attempt in range(1, GEMINI_IMAGE_RETRY_COUNT + 1):
        try:
            response = client.post_json(_ENDPOINT, payload, timeout=GEMINI_IMAGE_TIMEOUT)
            b64, mime = _parse_image_response(response)
            if b64:
                return b64, mime
            # No image in response — log details and store reason
            reason = _log_response_debug(response, map_name, attempt)
            last_error = reason
        except Exception as e:
            log_error(f"API error for '{map_name}' (attempt {attempt}): {e}", _MODULE, e)
            last_error = str(e)

    # All attempts failed — raise so the pipeline surfaces this to the UI
    raise RuntimeError(
        f"Gemini Image API failed for '{map_name}': {last_error or 'no image returned'}"
    )


def _log_response_debug(response: dict, map_name: str, attempt: int) -> str:
    """
    Log a concise summary of a non-image response and return a short reason string
    that can be surfaced to the UI.
    """
    try:
        candidates = response.get("candidates", [])
        if not candidates:
            feedback = response.get("promptFeedback", {})
            block = feedback.get("blockReason", "unknown")
            msg = f"request blocked ({block})"
            print(f"[NanaBanana::GeminiImageAPI] '{map_name}' attempt {attempt}: "
                  f"no candidates — blockReason={block}")
            log_error(f"Generation blocked for '{map_name}': {block}", _MODULE)
            return msg

        cand = candidates[0]
        finish = cand.get("finishReason", "?")
        parts = cand.get("content", {}).get("parts", [])
        text_parts = [p.get("text", "")[:120] for p in parts if "text" in p]
        msg = f"finishReason={finish}"
        print(f"[NanaBanana::GeminiImageAPI] '{map_name}' attempt {attempt}: "
              f"{msg}, model text={text_parts}")
        log_error(f"No image for '{map_name}' ({msg})", _MODULE)
        return msg
    except Exception:
        log_error(f"No image in response for '{map_name}' (attempt {attempt}).", _MODULE)
        return "unexpected response format"


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
