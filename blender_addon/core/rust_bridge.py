"""
BlenderNanoBanana - Python ↔ Rust Backend Bridge

Manages the Rust backend subprocess and provides HTTP JSON communication.
Rust server runs on localhost:7823 (tokio HTTP).

Endpoints:
  POST /analyze_mesh       → MeshAnalysis
  POST /analyze_uv_islands → UVAnalysis
  POST /pack_uv_islands    → UVPacking
  POST /process_texture    → TextureProcessing
  POST /optimize_maps      → MapOptimization
  GET  /health             → HealthCheck
"""

import os
import sys
import json
import time
import subprocess
import threading
import urllib.request
import urllib.error
from typing import Optional, Any

from ..config.constants import RUST_SERVER_PORT, RUST_SERVER_HOST, RUST_REQUEST_TIMEOUT


# ── Singleton ─────────────────────────────────────────────────────────────────

_rust_bridge_instance: Optional["RustBridge"] = None


def get_rust_bridge() -> "RustBridge":
    """Get or create the global RustBridge singleton."""
    global _rust_bridge_instance
    if _rust_bridge_instance is None:
        _rust_bridge_instance = RustBridge()
    return _rust_bridge_instance


# ── RustBridge ────────────────────────────────────────────────────────────────

class RustBridge:
    """
    Manages the Rust backend subprocess and HTTP communication.

    Lifecycle:
      start() → spawns subprocess, waits for /health OK
      stop()  → terminates subprocess gracefully
      call(endpoint, payload) → POST JSON, return response dict
    """

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._base_url = f"http://{RUST_SERVER_HOST}:{RUST_SERVER_PORT}"
        self._binary_path: Optional[str] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, binary_path: Optional[str] = None) -> bool:
        """
        Start the Rust backend subprocess.

        Args:
            binary_path: Path to rust binary. None = use bundled or preferences path.

        Returns:
            True if started and healthy, False otherwise.
        """
        with self._lock:
            if self.is_running():
                return True

            resolved_path = self._resolve_binary(binary_path)
            if not resolved_path:
                _log("Rust binary not found. Backend will be unavailable.")
                return False

            self._binary_path = resolved_path

            try:
                self._process = subprocess.Popen(
                    [resolved_path, "--port", str(RUST_SERVER_PORT)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    # Don't open a console window on Windows
                    creationflags=(subprocess.CREATE_NO_WINDOW
                                   if sys.platform == "win32" else 0),
                )
                _log(f"Rust process started (PID {self._process.pid}).")

                # Wait for the server to be ready (up to 10 seconds)
                if self._wait_for_health(timeout=10.0):
                    _log("Rust backend is ready.")
                    return True
                else:
                    _log("Rust backend did not become healthy in time.")
                    self.stop()
                    return False

            except FileNotFoundError:
                _log(f"Binary not found at: {resolved_path}")
                self._process = None
                return False
            except Exception as e:
                _log(f"Failed to start Rust backend: {e}")
                self._process = None
                return False

    def stop(self):
        """Terminate the Rust backend subprocess."""
        with self._lock:
            if self._process is None:
                return
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                _log("Rust backend stopped.")
            except Exception as e:
                _log(f"Error stopping Rust backend: {e}")
            finally:
                self._process = None

    def is_running(self) -> bool:
        """Check if the Rust subprocess is alive."""
        if self._process is None:
            return False
        # poll() returns None if process is still running
        return self._process.poll() is None

    def restart(self) -> bool:
        """Stop and restart the backend."""
        self.stop()
        return self.start(self._binary_path)

    # ── HTTP Communication ────────────────────────────────────────────────────

    def call(self, endpoint: str, payload: dict) -> dict:
        """
        POST JSON to a Rust backend endpoint.

        Args:
            endpoint: URL path, e.g. "/analyze_mesh"
            payload: dict to serialize as JSON body

        Returns:
            Response dict from Rust.

        Raises:
            RuntimeError: If backend is not running or request fails.
        """
        if not self.is_running():
            # Attempt auto-restart once
            _log("Backend not running — attempting restart...")
            if not self.start(self._binary_path):
                raise RuntimeError(
                    "Rust backend is not running. "
                    "Start it manually in Addon Preferences → Status."
                )

        url = self._base_url + endpoint
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=RUST_REQUEST_TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            raise RuntimeError(f"Rust backend HTTP error {e.code}: {body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Rust backend connection error: {e.reason}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Rust backend returned invalid JSON: {e}")

    def health_check(self) -> bool:
        """Return True if the backend responds to /health."""
        try:
            url = self._base_url + "/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    # ── Convenience Wrappers ──────────────────────────────────────────────────

    def analyze_mesh(self, vertices: list, faces: list, normals: list = None) -> dict:
        """
        Send mesh geometry to Rust for fast analysis.

        Returns:
            {
                "vertex_count": int,
                "face_count": int,
                "has_symmetry": bool,
                "symmetry_axis": str | null,
                "bounds": {"min": [x,y,z], "max": [x,y,z]},
                "is_manifold": bool
            }
        """
        payload = {
            "vertices": vertices,
            "faces": faces,
        }
        if normals is not None:
            payload["normals"] = normals
        return self.call("/analyze_mesh", payload)

    def analyze_uv_islands(self, uv_coordinates: list, seams: list = None) -> dict:
        """
        Detect UV islands and their properties via Rust.

        Returns:
            {
                "islands": [
                    {
                        "id": str,
                        "area": float,
                        "bounds": {"min": [u,v], "max": [u,v]},
                        "face_indices": [int, ...],
                        "symmetrical_to": str | null
                    },
                    ...
                ]
            }
        """
        payload = {"uv_coordinates": uv_coordinates}
        if seams is not None:
            payload["seams"] = seams
        return self.call("/analyze_uv_islands", payload)

    def pack_uv_islands(self, islands: list, canvas_size: int = 1024,
                        margin: float = 0.005) -> dict:
        """
        Pack UV islands optimally via Rust.

        Returns:
            {
                "packed_islands": [
                    {"id": str, "transform": {"offset": [u,v], "scale": float}},
                    ...
                ],
                "utilization": float
            }
        """
        return self.call("/pack_uv_islands", {
            "islands": islands,
            "canvas_size": canvas_size,
            "margin": margin,
        })

    def process_texture(self, image_data_b64: str, target_size: int,
                        output_format: str = "png",
                        color_space: str = "sRGB") -> dict:
        """
        Process and optimize a single texture image via Rust.

        Args:
            image_data_b64: Base64-encoded image bytes
            target_size: Output size in pixels (square)
            output_format: "png", "exr", "jpg", "tga"
            color_space: "sRGB", "linear_tangent", "linear_grayscale"

        Returns:
            {"image_data": str (base64), "width": int, "height": int, "format": str}
        """
        return self.call("/process_texture", {
            "image_data": image_data_b64,
            "target_size": target_size,
            "output_format": output_format,
            "color_space": color_space,
        })

    def optimize_maps(self, maps: dict, sizes: dict, formats: dict) -> dict:
        """
        Batch-optimize PBR texture maps via Rust.

        Args:
            maps: {"albedo": b64_str, "normal": b64_str, ...}
            sizes: {"albedo": 2048, "normal": 2048, ...}
            formats: {"albedo": "sRGB", "normal": "linear_tangent", ...}

        Returns:
            {"maps": {"albedo": b64_str, ...}, "sizes": {...}}
        """
        return self.call("/optimize_maps", {
            "maps": maps,
            "sizes": sizes,
            "formats": formats,
        })

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _resolve_binary(self, override_path: Optional[str] = None) -> Optional[str]:
        """
        Find the Rust backend binary.

        Priority:
        1. override_path argument
        2. Addon preferences rust_binary_path
        3. Bundled binary next to this addon directory
        """
        # 1. Explicit override
        if override_path and os.path.isfile(override_path):
            return override_path

        # 2. Addon preferences
        try:
            import bpy
            prefs = bpy.context.preferences.addons[__package__.split(".")[0]].preferences
            if prefs.rust_binary_path and os.path.isfile(prefs.rust_binary_path):
                return prefs.rust_binary_path
        except Exception:
            pass

        # 3. Bundled binary (next to the addon package)
        addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        binary_name = "nano_banana_backend.exe" if sys.platform == "win32" else "nano_banana_backend"
        bundled = os.path.join(addon_dir, "rust_backend", "target", "release", binary_name)
        if os.path.isfile(bundled):
            return bundled

        # Also check if compiled binary is next to addon dir
        adjacent = os.path.join(os.path.dirname(addon_dir), binary_name)
        if os.path.isfile(adjacent):
            return adjacent

        return None

    def _wait_for_health(self, timeout: float = 10.0) -> bool:
        """Poll /health until server is ready or timeout expires."""
        deadline = time.time() + timeout
        interval = 0.2
        while time.time() < deadline:
            if self.health_check():
                return True
            time.sleep(interval)
        return False


# ── Logging helper ────────────────────────────────────────────────────────────

def _log(msg: str):
    print(f"[NanoBanana::RustBridge] {msg}")
