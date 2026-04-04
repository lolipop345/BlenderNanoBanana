"""
BlenderNanoBanana - HTTP API Client

Shared HTTP client with authentication, retry logic, and timeout handling.
Used by google_llm.py and google_vision.py.
"""

import json
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from ..config.constants import API_REQUEST_TIMEOUT, API_MAX_RETRIES, API_RETRY_DELAY_SEC


class APIClient:
    """Thin HTTP wrapper with retry logic and JSON handling."""

    def __init__(self, api_key: str, base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def post_json(self, url: str, payload: dict,
                  extra_headers: Optional[Dict[str, str]] = None,
                  timeout: float = API_REQUEST_TIMEOUT) -> dict:
        """
        POST JSON to a URL. Returns parsed response dict.

        Raises:
            RuntimeError on HTTP error or network failure.
            ValueError on invalid JSON response.
        """
        full_url = url if url.startswith("http") else self.base_url + url
        data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(full_url, data=data, headers=headers, method="POST")

        last_error = None
        for attempt in range(1, API_MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = resp.read().decode("utf-8")
                    return json.loads(body)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8")
                # Extract just the message field from JSON error body if possible
                short_msg = _extract_error_message(body, e.code)
                if e.code in (429, 503):
                    # Rate limit / service unavailable — retry
                    last_error = RuntimeError(short_msg)
                    time.sleep(API_RETRY_DELAY_SEC * attempt)
                    continue
                raise RuntimeError(short_msg)
            except urllib.error.URLError as e:
                last_error = RuntimeError(f"Network error: {e.reason}")
                if attempt < API_MAX_RETRIES:
                    time.sleep(API_RETRY_DELAY_SEC)
                    continue
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON response: {e}")

        raise last_error or RuntimeError("API request failed after retries.")


def _extract_error_message(body: str, code: int) -> str:
    """
    Return a short, viewport-friendly error string from an API error body.
    Extracts the 'message' field from JSON if available, otherwise truncates raw body.
    """
    try:
        data = json.loads(body)
        msg = data.get("error", {}).get("message") or data.get("message", "")
        if msg:
            # Truncate at first period or 120 chars
            short = msg.split(".")[0][:120]
            return f"API {code}: {short}"
    except Exception:
        pass
    # Fallback: raw body truncated
    return f"API {code}: {body[:100]}"
