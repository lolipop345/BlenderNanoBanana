"""
BlenderNanoBanana - Dependency Install Operator

Manual "Install Dependencies" button for Addon Preferences.
Auto-install runs automatically in the background on addon enable —
this button is a fallback if auto-install fails (e.g. no internet on first use).
"""

import bpy
from bpy.types import Operator


class NANOBANANA_OT_install_dependencies(Operator):
    """Install missing Python dependencies into Blender's Python (runs in background)"""
    bl_idname = "nanobanana.install_dependencies"
    bl_label = "Install Dependencies"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        from ..install_dependencies import check_all, auto_install_in_background

        status = check_all()

        if status["installing"]:
            self.report({"INFO"}, "Installation already running — check System Console for progress.")
            return {"FINISHED"}

        if status["all_ok"]:
            self.report({"INFO"}, "All dependencies are already installed.")
            return {"FINISHED"}

        # Reset _install_done so the background worker runs again
        import blender_addon.install_dependencies as _dep  # noqa
        try:
            from .. import install_dependencies as _dep
            _dep._install_done = False
        except Exception:
            pass

        auto_install_in_background()

        missing_names = [p["name"] for p in status["packages"] if not p["installed"]]
        self.report(
            {"INFO"},
            f"Installing {missing_names} in background — check System Console for progress. "
            "Packages will be available immediately after install (no restart needed)."
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


CLASSES = [NANOBANANA_OT_install_dependencies]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
