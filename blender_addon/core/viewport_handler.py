"""
BlenderNanoBanana - Viewport Handler

Captures viewport screenshots and stores them as reference context images.
"""

import os
import time
from typing import Optional

from ..utils.viewport_utils import capture_viewport_screenshot
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "ViewportHandler"


def capture_and_store(context, project_name: str) -> Optional[str]:
    """
    Capture the current 3D viewport and store it in the project cache.

    Args:
        context: Blender context
        project_name: Name used for the cache subfolder (e.g. blend filename)

    Returns:
        Absolute path of the saved screenshot, or None on failure.
    """
    cache_dir = _get_viewport_cache_dir(context, project_name)
    os.makedirs(cache_dir, exist_ok=True)

    timestamp = int(time.time())
    filename = f"context_{timestamp}.png"
    output_path = os.path.join(cache_dir, filename)

    log_debug(f"Capturing viewport to: {output_path}", _MODULE)

    success = capture_viewport_screenshot(context, output_path)
    if success:
        log_info(f"Viewport captured: {filename}", _MODULE)
        _cleanup_old_captures(cache_dir, keep=10)
        return output_path
    else:
        log_error("Viewport capture failed.", _MODULE)
        return None


def get_latest_capture(context, project_name: str) -> Optional[str]:
    """Return path to the most recently captured viewport image, or None."""
    cache_dir = _get_viewport_cache_dir(context, project_name)
    if not os.path.isdir(cache_dir):
        return None

    captures = [
        os.path.join(cache_dir, f)
        for f in os.listdir(cache_dir)
        if f.startswith("context_") and f.endswith(".png")
    ]
    if not captures:
        return None

    return max(captures, key=os.path.getmtime)


def _get_viewport_cache_dir(context, project_name: str) -> str:
    from .cache_manager import get_cache_base_path
    base = get_cache_base_path(context)
    safe_name = _safe_project_name(project_name)
    return os.path.join(base, safe_name, "viewport_captures")


def _safe_project_name(name: str) -> str:
    """Strip unsafe filesystem characters from a project name."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _cleanup_old_captures(cache_dir: str, keep: int = 10):
    """Delete oldest viewport captures if count exceeds `keep`."""
    try:
        files = sorted(
            [os.path.join(cache_dir, f) for f in os.listdir(cache_dir)
             if f.startswith("context_") and f.endswith(".png")],
            key=os.path.getmtime,
        )
        while len(files) > keep:
            old = files.pop(0)
            os.remove(old)
            log_debug(f"Removed old capture: {os.path.basename(old)}", _MODULE)
    except Exception as e:
        log_error(f"Cleanup error: {e}", _MODULE)
