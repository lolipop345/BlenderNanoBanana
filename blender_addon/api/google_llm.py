"""
BlenderNanoBanana - Gemini 3 Flash API Integration

Calls Gemini 3 Flash with structured outputs (response_mime_type: application/json)
to generate clean JSON texture parameter specs.

No prose output — only validated JSON matching GEMINI_TEXTURE_SPEC_SCHEMA.
"""

import json
from typing import Optional, Dict, Any, List

from .api_client import APIClient
from ..config.constants import (
    GEMINI_MODEL_ID,
    GEMINI_API_BASE_URL,
    GEMINI_TEXTURE_SPEC_SCHEMA,
)

from ..utils.logging import log_info, log_debug, log_error

_MODULE = "GeminiLLM"

# Gemini generateContent endpoint
_ENDPOINT_TEMPLATE = "/v1beta/models/{model}:generateContent"


def generate_texture_spec(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    images: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Call Gemini 3 Flash to generate a structured JSON texture spec.

    Uses structured outputs: response_mime_type=application/json + json_schema
    to enforce the GEMINI_TEXTURE_SPEC_SCHEMA.

    Args:
        api_key: Google API key
        system_prompt: System instruction (role/constraints)
        user_prompt: User message (what to generate)
        images: Optional list of {"mime_type": str, "data": base64_str}

    Returns:
        Parsed JSON dict matching the texture spec schema, or None on failure.
    """
    client = APIClient(api_key=api_key, base_url=GEMINI_API_BASE_URL)
    endpoint = _ENDPOINT_TEMPLATE.format(model=GEMINI_MODEL_ID)

    payload = _build_payload(system_prompt, user_prompt, images)

    log_debug(f"Calling Gemini 3 Flash ({GEMINI_MODEL_ID})...", _MODULE)

    try:
        response = client.post_json(endpoint, payload, timeout=30.0)
        spec = _parse_response(response)
        if spec:
            log_info(f"Gemini spec generated: {list(spec.keys())}", _MODULE)
        return spec
    except Exception as e:
        # Re-raise so the caller can surface a real error message to the UI
        log_error(f"Gemini API call failed: {e}", _MODULE, e)
        raise RuntimeError(f"Gemini Flash API error: {e}") from e


def generate_text(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    images: Optional[List[Dict[str, str]]] = None,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    Call Gemini 3 Flash and return a plain-text response (no JSON schema).

    Args:
        api_key: Google API key
        system_prompt: System instruction
        user_prompt: User message
        images: Optional list of {"mime_type": str, "data": base64_str}
        timeout: Request timeout in seconds

    Returns:
        Response text string, or None on failure.
    """
    client = APIClient(api_key=api_key, base_url=GEMINI_API_BASE_URL)
    endpoint = _ENDPOINT_TEMPLATE.format(model=GEMINI_MODEL_ID)

    parts = [{"text": user_prompt}]
    if images:
        for img in images:
            parts.append({
                "inline_data": {
                    "mime_type": img["mime_type"],
                    "data": img["data"],
                }
            })

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": parts}],
    }

    log_debug(f"Calling Gemini 3 Flash (text, {GEMINI_MODEL_ID})...", _MODULE)

    try:
        response = client.post_json(endpoint, payload, timeout=timeout)
        candidates = response.get("candidates", [])
        if not candidates:
            return None
        parts_resp = candidates[0].get("content", {}).get("parts", [])
        return parts_resp[0].get("text", "") if parts_resp else None
    except Exception as e:
        log_error(f"Gemini text call failed: {e}", _MODULE, e)
        return None


def _build_payload(system_prompt: str, user_prompt: str,
                   images: Optional[List[Dict[str, str]]]) -> dict:
    """Build the Gemini API request payload with structured output config."""
    # User content parts
    parts = [{"text": user_prompt}]

    # Add images as inline_data parts
    if images:
        for img in images:
            parts.append({
                "inline_data": {
                    "mime_type": img["mime_type"],
                    "data": img["data"],
                }
            })

    return {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": {
            # Force JSON output — no prose, no markdown
            "response_mime_type": "application/json",
            "response_schema": GEMINI_TEXTURE_SPEC_SCHEMA,
            # temperature intentionally omitted — Gemini 3 docs strongly recommend
            # keeping it at the default (1.0); lowering it causes looping/degraded output
        },
    }


def _parse_response(response: dict) -> Optional[Dict[str, Any]]:
    """Extract and parse the JSON spec from a Gemini API response."""
    try:
        candidates = response.get("candidates", [])
        if not candidates:
            log_error("Gemini returned no candidates.", _MODULE)
            return None

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            log_error("Gemini response has no content parts.", _MODULE)
            return None

        text = parts[0].get("text", "")
        if not text:
            log_error("Gemini response text is empty.", _MODULE)
            return None

        spec = json.loads(text)
        return spec

    except json.JSONDecodeError as e:
        log_error(f"Failed to parse Gemini JSON response: {e}", _MODULE)
        return None
    except (KeyError, IndexError) as e:
        log_error(f"Unexpected Gemini response structure: {e}", _MODULE)
        return None
