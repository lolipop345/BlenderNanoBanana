"""
BlenderNanoBanana - Logging Utilities

Provides consistent logging with optional debug mode.
Reads enable_debug_logging from addon preferences.
"""

import sys
from datetime import datetime


_PREFIX = "[NanoBanana]"


def _is_debug() -> bool:
    try:
        import bpy
        prefs = bpy.context.preferences.addons[__package__.split(".")[0]].preferences
        return prefs.enable_debug_logging
    except Exception:
        return False


def _push_viewport(msg: str, level: str):
    """Send message to viewport log display (non-blocking, fails silently)."""
    try:
        from ..core.log_display import push
        push(msg, level)
    except Exception:
        pass


def log_info(msg: str, module: str = ""):
    tag = f"{_PREFIX}[{module}] " if module else f"{_PREFIX} "
    print(f"{tag}{msg}")
    _push_viewport(msg, "INFO")


def log_ok(msg: str, module: str = ""):
    tag = f"{_PREFIX}[{module}] " if module else f"{_PREFIX} "
    print(f"{tag}{msg}")
    _push_viewport(msg, "OK")


def log_debug(msg: str, module: str = ""):
    if _is_debug():
        tag = f"{_PREFIX}[DEBUG][{module}] " if module else f"{_PREFIX}[DEBUG] "
        print(f"{tag}{msg}")
        # Debug messages only go to console, not viewport


def log_warning(msg: str, module: str = ""):
    tag = f"{_PREFIX}[WARN][{module}] " if module else f"{_PREFIX}[WARN] "
    print(f"{tag}{msg}", file=sys.stderr)
    _push_viewport(msg, "WARN")


def log_error(msg: str, module: str = "", exc: Exception = None):
    tag = f"{_PREFIX}[ERROR][{module}] " if module else f"{_PREFIX}[ERROR] "
    print(f"{tag}{msg}", file=sys.stderr)
    _push_viewport(msg, "ERROR")
    if exc and _is_debug():
        import traceback
        traceback.print_exc()
