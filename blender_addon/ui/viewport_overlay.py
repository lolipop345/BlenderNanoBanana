"""
BlenderNanoBanana - UI Viewport Overlay Module

Thin wrapper — actual draw logic lives in core/viewport_overlay.py.
This module handles registration of the draw handler from the UI layer.
"""

from ..core import viewport_overlay as _core_overlay


def register():
    _core_overlay.register()


def unregister():
    _core_overlay.unregister()
