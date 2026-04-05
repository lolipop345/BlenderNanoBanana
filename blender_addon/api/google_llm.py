"""
BlenderNanoBanana - Gemini 3 Flash API Integration

Calls Gemini 3 Flash with structured outputs (response_mime_type: application/json)
to generate clean JSON texture parameter specs using the google-genai SDK.

No prose output — only validated JSON matching GEMINI_TEXTURE_SPEC_SCHEMA.
"""

import json
import base64
import io
from typing import Optional, Dict, Any, List

from ..config.constants import (
    GEMINI_MODEL_ID,
    GEMINI_TEXTURE_SPEC_SCHEMA,
)

from ..utils.logging import log_info, log_debug, log_error

_MODULE = "GeminiLLM"

_LLM_TIMEOUT_SEC  = 120   # seconds for JSON spec generation
_TEXT_TIMEOUT_SEC = 120   # seconds for plain-text generation

# Max pixel size for images sent to LLM (compress before upload)
_MAX_LLM_IMAGE_SIZE = 768


def _compress_image_b64(b64_str: str, max_size: int = _MAX_LLM_IMAGE_SIZE) -> tuple:
    """
    Resize + JPEG-compress a base64 image.
    Returns (compressed_b64, mime_type).
    Falls back to the original PNG on error.
    """
    try:
        from PIL import Image
        data = base64.b64decode(b64_str)
        img = Image.open(io.BytesIO(data))
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"
    except Exception as e:
        log_debug(f"Image compression failed (using original): {e}", _MODULE)
        return b64_str, "image/png"


def _make_client(api_key: str, timeout_sec: int):
    """
    Create a genai.Client and apply three patches to prevent WriteTimeout:

    1. patch _httpx_client._timeout
    2. patch _async_httpx_client._timeout
    3. patch _http_options.timeout = None

    Using 300s for write/read instead of None to prevent infinite hangs if the
    API server fails to respond.
    """
    from google import genai
    import httpx

    # connect=60s, write/read/pool = 300s (prevent 40-minute infinite hangs)
    hx_no_timeout = httpx.Timeout(timeout=300.0, connect=60.0)

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
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai is not installed yet. Please wait for dependencies to install.")

    client = _make_client(api_key, _LLM_TIMEOUT_SEC)

    parts = [user_prompt]
    if images:
        for img in images:
            compressed_b64, mime = _compress_image_b64(img["data"])
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(compressed_b64),
                    mime_type=mime,
                )
            )

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=GEMINI_TEXTURE_SPEC_SCHEMA,
    )

    log_debug(f"Calling Gemini ({GEMINI_MODEL_ID}) for texture spec...", _MODULE)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL_ID,
            contents=parts,
            config=config,
        )
        if response.text:
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            spec = json.loads(text)
            log_info(f"Gemini spec generated: {list(spec.keys())}", _MODULE)
            return spec
        log_error("Gemini returned no text for spec.", _MODULE)
        return None
    except Exception as e:
        import traceback
        err_type = type(e).__name__
        err_msg = str(e)
        log_error(
            f"Gemini API call failed ({err_type}): {err_msg}\n{traceback.format_exc()}",
            _MODULE, e
        )
        raise RuntimeError(f"Gemini Flash API error ({err_type}): {err_msg}") from e


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
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai is not installed yet. Please wait for dependencies to install.")

    t_sec = max(int(timeout), _TEXT_TIMEOUT_SEC)
    client = _make_client(api_key, t_sec)

    parts = [user_prompt]
    if images:
        for img in images:
            compressed_b64, mime = _compress_image_b64(img["data"])
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(compressed_b64),
                    mime_type=mime,
                )
            )

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
    )

    log_debug(f"Calling Gemini ({GEMINI_MODEL_ID}) for text...", _MODULE)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL_ID,
            contents=parts,
            config=config,
        )
        return response.text
    except Exception as e:
        import traceback
        log_error(
            f"Gemini text call failed: {e}\n{traceback.format_exc()}",
            _MODULE, e
        )
        return None
