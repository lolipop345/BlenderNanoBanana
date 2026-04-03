"""
BlenderNanoBanana - Nano Banana Vision API Integration

Sends texture generation requests to Google's Nano Banana vision model.
Receives generated texture images (base64-encoded PNG/EXR).

Request format:
  POST <nano_banana_api_url>
  {
    "json_spec": {...},             # Gemini-generated texture parameters
    "visual_context": [base64...],  # Viewport + reference images
    "maps_to_generate": [...],      # ["albedo", "normal", ...]
    "engine_specs": {...},          # Per-map size, format, file_ext
  }

Response format:
  {
    "maps": {
      "albedo":    {"data": base64_str, "format": "png"},
      "normal":    {"data": base64_str, "format": "png"},
      ...
    }
  }
"""

import json
from typing import Optional, Dict, Any, List

from .api_client import APIClient
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "NanoBananaAPI"


def generate_textures(
    api_key: str,
    json_spec: Dict[str, Any],
    maps_to_generate: List[str],
    engine_specs: Dict[str, Any],
    visual_context_b64: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Call Nano Banana API to generate PBR texture maps.

    Args:
        api_key: Google API key
        json_spec: Gemini-generated texture parameter spec
        maps_to_generate: List of map names to generate (e.g. ["albedo", "normal"])
        engine_specs: Per-map config {"albedo": {"size": 2048, "format": "sRGB"}, ...}
        visual_context_b64: Optional list of base64-encoded context images

    Returns:
        {"maps": {"albedo": {"data": b64, "format": "png"}, ...}} or None.
    """
    api_url = "https://nano-banana.googleapis.com/v1beta/models/generateTextures"

    client = APIClient(api_key=api_key, base_url="")

    payload = {
        "json_spec": json_spec,
        "maps_to_generate": maps_to_generate,
        "engine_specs": engine_specs,
    }

    if visual_context_b64:
        payload["visual_context"] = visual_context_b64

    log_debug(
        f"Requesting {maps_to_generate} maps from Nano Banana...", _MODULE
    )

    try:
        response = client.post_json(api_url, payload, timeout=60.0)
        maps = response.get("maps", {})
        if maps:
            log_info(f"Received {len(maps)} texture maps from Nano Banana.", _MODULE)
        else:
            log_error("Nano Banana returned empty maps.", _MODULE)
            return None
        return response
    except Exception as e:
        log_error(f"Nano Banana API call failed: {e}", _MODULE, e)
        return None


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
    api_url = "https://nano-banana.googleapis.com/v1beta/models/generateReference"

    client = APIClient(api_key=api_key, base_url="")

    payload: Dict[str, Any] = {
        "purpose": "reference_image",
        "semantic_tag": tag_definition.get("id", "unknown"),
        "tag_definition": tag_definition,
        "quality": "high",
    }
    if viewport_b64:
        payload["visual_context"] = [viewport_b64]

    try:
        response = client.post_json(api_url, payload, timeout=30.0)
        image_data = response.get("image_data") or response.get("data")
        if image_data:
            log_info("Reference image generated.", _MODULE)
            return image_data
        log_error(f"Unexpected Nano Banana response: {list(response.keys())}", _MODULE)
        return None
    except Exception as e:
        log_error(f"Reference generation failed: {e}", _MODULE, e)
        return None
