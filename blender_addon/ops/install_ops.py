"""
BlenderNanoBanana - Dependency Install Operator

Installs missing Python packages into Blender's bundled Python.
Shows progress in the console. Reports success/failure in the UI.
"""

import bpy
from bpy.types import Operator


class NANOBANANA_OT_install_dependencies(Operator):
    """Install missing Python dependencies into Blender's Python"""
    bl_idname = "nanobanana.install_dependencies"
    bl_label = "Install Dependencies"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        from ..install_dependencies import install_all_missing, check_all

        self.report({"INFO"}, "Installing dependencies... (check System Console for progress)")

        succeeded, failed = install_all_missing()

        if failed:
            self.report(
                {"ERROR"},
                f"Failed to install: {', '.join(failed)}. "
                "Open the System Console (Window → Toggle System Console) for details."
            )
            return {"CANCELLED"}

        if succeeded:
            self.report(
                {"INFO"},
                f"Successfully installed: {', '.join(succeeded)}. "
                "Restart Blender to complete setup."
            )
        else:
            self.report({"INFO"}, "All dependencies were already installed.")

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
