"""
BlenderNanoBanana - Dependency Installer

Installs required Python packages into Blender's bundled Python.
Called automatically on first addon enable, or manually via the
"Install Dependencies" button in Addon Preferences.

Uses:
  1. ensurepip  → bootstraps pip if Blender's Python doesn't have it
  2. subprocess → calls Blender's own Python executable to pip install
"""

import sys
import subprocess
import importlib
from typing import List, Tuple

# ── Required packages ─────────────────────────────────────────────────────────
#
# Each entry: (import_name, pip_package_name, min_version_str)
# import_name   = what you `import` in Python
# pip_package   = what pip installs
# min_version   = minimum acceptable version (empty = any)

REQUIRED_PACKAGES: List[Tuple[str, str, str]] = [
    ("google.generativeai", "google-generativeai", "0.8.0"),
    ("PIL",                 "Pillow",               "10.0.0"),
    ("requests",            "requests",             "2.31.0"),
    ("numpy",               "numpy",                "1.24.0"),
]


def is_installed(import_name: str) -> bool:
    """Return True if the package can be imported."""
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def get_missing_packages() -> List[Tuple[str, str, str]]:
    """Return list of packages that are not yet installed."""
    return [
        (imp, pkg, ver)
        for imp, pkg, ver in REQUIRED_PACKAGES
        if not is_installed(imp)
    ]


def ensure_pip() -> bool:
    """Bootstrap pip into Blender's Python if it's missing."""
    try:
        import pip  # noqa: F401
        return True
    except ImportError:
        pass

    print("[NanoBanana] pip not found — bootstrapping with ensurepip...")
    try:
        import ensurepip
        ensurepip.bootstrap(upgrade=True)
        # Reload pip
        import importlib
        importlib.invalidate_caches()
        return True
    except Exception as e:
        print(f"[NanoBanana] ensurepip failed: {e}")
        return False


def install_package(pip_package: str, min_version: str = "") -> bool:
    """
    Install a pip package into Blender's Python using subprocess.

    Uses sys.executable so we always target Blender's bundled Python,
    not any system Python that might be on PATH.
    """
    pkg_spec = f"{pip_package}>={min_version}" if min_version else pip_package

    cmd = [
        sys.executable,       # Blender's Python
        "-m", "pip",
        "install",
        "--upgrade",
        "--no-warn-script-location",
        pkg_spec,
    ]

    print(f"[NanoBanana] Installing: {pkg_spec}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print(f"[NanoBanana] ✓ Installed: {pip_package}")
            return True
        else:
            print(f"[NanoBanana] ✗ Failed to install {pip_package}:")
            print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print(f"[NanoBanana] ✗ Timeout installing {pip_package}")
        return False
    except Exception as e:
        print(f"[NanoBanana] ✗ Error installing {pip_package}: {e}")
        return False


def _vlog(msg: str, level: str = "INFO"):
    """Push to viewport log if available."""
    try:
        from .core.log_display import push
        push(msg, level)
    except Exception:
        pass


def install_all_missing() -> Tuple[List[str], List[str]]:
    """
    Install all missing packages.

    Returns:
        (succeeded, failed) — lists of pip package names.
    """
    missing = get_missing_packages()
    if not missing:
        print("[NanoBanana] All dependencies already installed.")
        return [], []

    print(f"[NanoBanana] Installing {len(missing)} missing package(s)...")
    _vlog(f"Installing {len(missing)} package(s)...", "INFO")

    # Make sure pip is available
    if not ensure_pip():
        failed = [pkg for _, pkg, _ in missing]
        print("[NanoBanana] Cannot install — pip not available.")
        return [], failed

    succeeded = []
    failed = []

    for _imp, pkg, ver in missing:
        _vlog(f"Installing {pkg}...", "INFO")
        if install_package(pkg, ver):
            succeeded.append(pkg)
            _vlog(f"{pkg} installed", "OK")
        else:
            failed.append(pkg)
            _vlog(f"Failed: {pkg}", "ERROR")

    # Invalidate import cache so newly installed modules are found
    importlib.invalidate_caches()

    if succeeded:
        _vlog("Done! Restart Blender.", "OK")

    return succeeded, failed


def check_all() -> dict:
    """
    Check status of all required packages.

    Returns:
        {
            "all_ok": bool,
            "packages": [
                {"name": str, "import": str, "installed": bool},
                ...
            ]
        }
    """
    packages = []
    for imp, pkg, ver in REQUIRED_PACKAGES:
        packages.append({
            "name": pkg,
            "import": imp,
            "installed": is_installed(imp),
        })

    all_ok = all(p["installed"] for p in packages)
    return {"all_ok": all_ok, "packages": packages}
