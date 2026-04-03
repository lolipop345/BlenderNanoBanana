"""
BlenderNanoBanana - Model Operators

ReadModel: Analyze active mesh via Rust backend.
CaptureViewport: Take a viewport screenshot for context.
StartRustBackend: Manually start the Rust subprocess.
"""

import bpy
from bpy.types import Operator

from ..core.model_analyzer import analyze_active_mesh
from ..core.viewport_handler import capture_and_store
from ..core.cache_manager import get_project_name


class NANOBANANA_OT_read_model(Operator):
    """Analyze the active mesh and display info in the Model panel"""
    bl_idname = "nanobanana.read_model"
    bl_label = "Read Model"
    bl_options = {"REGISTER"}

    def execute(self, context):
        result = analyze_active_mesh(context)
        if result is None:
            self.report({"WARNING"}, "No active mesh found. Select a mesh object.")
            return {"CANCELLED"}

        # Store result in scene custom properties for the UI panel
        context.scene["nb_model_data"] = result
        self.report({"INFO"},
                    f"Model: {result['vertex_count']} verts, "
                    f"{result['face_count']} faces, "
                    f"symmetry={result['has_symmetry']}")
        return {"FINISHED"}


class NANOBANANA_OT_capture_viewport(Operator):
    """Capture the current 3D viewport as a reference context image"""
    bl_idname = "nanobanana.capture_viewport"
    bl_label = "Capture Viewport"
    bl_options = {"REGISTER"}

    def execute(self, context):
        project_name = get_project_name(context)
        path = capture_and_store(context, project_name)
        if path:
            self.report({"INFO"}, f"Viewport captured: {path}")
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, "Viewport capture failed.")
            return {"CANCELLED"}


class NANOBANANA_OT_start_rust_backend(Operator):
    """Start the Rust backend subprocess"""
    bl_idname = "nanobanana.start_rust_backend"
    bl_label = "Start Rust Backend"
    bl_options = {"REGISTER"}

    def execute(self, context):
        from ..core.rust_bridge import get_rust_bridge
        bridge = get_rust_bridge()
        if bridge.is_running():
            self.report({"INFO"}, "Rust backend is already running.")
            return {"FINISHED"}

        success = bridge.start()
        if success:
            self.report({"INFO"}, "Rust backend started successfully.")
            return {"FINISHED"}
        else:
            self.report({"ERROR"},
                        "Failed to start Rust backend. "
                        "Check the binary path in Addon Preferences → Advanced.")
            return {"CANCELLED"}


class NANOBANANA_OT_stop_rust_backend(Operator):
    """Stop the Rust backend subprocess"""
    bl_idname = "nanobanana.stop_rust_backend"
    bl_label = "Stop Rust Backend"
    bl_options = {"REGISTER"}

    def execute(self, context):
        from ..core.rust_bridge import get_rust_bridge
        bridge = get_rust_bridge()
        bridge.stop()
        self.report({"INFO"}, "Rust backend stopped.")
        return {"FINISHED"}


# ── Registration ───────────────────────────────────────────────────────────────

CLASSES = [
    NANOBANANA_OT_read_model,
    NANOBANANA_OT_capture_viewport,
    NANOBANANA_OT_start_rust_backend,
    NANOBANANA_OT_stop_rust_backend,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
