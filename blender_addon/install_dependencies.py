"""
BlenderNanoBanana - Dependency Installer

Installs required Python packages into Blender's bundled Python automatically
on first addon enable, and manually via the "Install Dependencies" button.

Key behaviours:
  - Auto-install runs in a background daemon thread → Blender never freezes
  - After install, refreshes sys.path so packages are importable immediately
    without restarting Blender
  - Uses sys.executable so packages always go into Blender's own Python,
    never a system Python
"""

import sys
import subprocess
import importlib
import threading
from typing import List, Tuple

# ── Required packages ─────────────────────────────────────────────────────────
#
# (import_name, pip_package_name, min_version)
# import_name  = what you `import` in Python
# pip_package  = what pip installs
# min_version  = minimum acceptable version ("" = any)

REQUIRED_PACKAGES: List[Tuple[str, str, str]] = [
    ("PIL",    "Pillow", "9.0.0"),
    ("numpy",  "numpy",  "1.21.0"),
    ("google.genai", "google-genai", ""),
]


# ── Status ────────────────────────────────────────────────────────────────────

_install_lock   = threading.Lock()
_install_thread: threading.Thread = None
_install_done   = False
_install_log: List[str] = []


def _log(msg: str):
    print(f"[NanoBanana::Deps] {msg}")
    _install_log.append(msg)
    try:
        from .core.log_display import push
        push(msg, "INFO")
    except Exception:
        pass


# ── Package helpers ───────────────────────────────────────────────────────────

def is_installed(import_name: str) -> bool:
    """Return True if the package can be imported right now."""
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def get_missing_packages() -> List[Tuple[str, str, str]]:
    """Return entries from REQUIRED_PACKAGES that are not yet importable."""
    return [(imp, pkg, ver) for imp, pkg, ver in REQUIRED_PACKAGES
            if not is_installed(imp)]


def _refresh_sys_path():
    """
    After a pip subprocess installs a package, Python's import machinery
    may not know about it yet (cached directory listings).

    This re-adds Blender's site-packages directories and flushes the
    import cache so newly installed packages are findable without restart.
    """
    try:
        import site
        # Standard site-packages (Blender's Python)
        for path in site.getsitepackages():
            if path not in sys.path:
                sys.path.append(path)
        # User site-packages
        try:
            user_site = site.getusersitepackages()
            if user_site and user_site not in sys.path:
                sys.path.insert(0, user_site)
        except Exception:
            pass
    except Exception:
        pass
    importlib.invalidate_caches()


def ensure_pip() -> bool:
    """Bootstrap pip into Blender's Python if it's missing."""
    try:
        import pip  # noqa: F401
        return True
    except ImportError:
        pass
    _log("pip not found — bootstrapping with ensurepip...")
    try:
        import ensurepip
        ensurepip.bootstrap(upgrade=True)
        importlib.invalidate_caches()
        return True
    except Exception as e:
        _log(f"ensurepip failed: {e}")
        return False


def install_package(pip_package: str, min_version: str = "") -> bool:
    """
    Install a pip package using Blender's own Python executable (sys.executable).
    Blocks the calling thread (not the main thread) until pip finishes.

    Returns True on success.
    """
    pkg_spec = f"{pip_package}>={min_version}" if min_version else pip_package
    cmd = [
        sys.executable,
        "-m", "pip", "install",
        "--upgrade",
        "--no-warn-script-location",
        pkg_spec,
    ]
    _log(f"Installing {pkg_spec} ...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0:
            _log(f"✓ {pip_package} installed")
            _refresh_sys_path()
            return True
        _log(f"✗ {pip_package} failed:\n{result.stderr.strip()}")
        return False
    except subprocess.TimeoutExpired:
        _log(f"✗ {pip_package} timed out")
        return False
    except Exception as e:
        _log(f"✗ {pip_package} error: {e}")
        return False


# ── Main install routine ──────────────────────────────────────────────────────

def install_all_missing() -> Tuple[List[str], List[str]]:
    """
    Install every package in REQUIRED_PACKAGES that isn't importable.
    Meant to be called from a background thread (auto-install) or directly
    from the manual "Install Dependencies" operator.

    Returns (succeeded, failed) lists of pip package names.
    """
    missing = get_missing_packages()
    if not missing:
        _log("All dependencies already installed.")
        return [], []

    _log(f"Installing {len(missing)} missing package(s): "
         f"{[pkg for _, pkg, _ in missing]}")

    if not ensure_pip():
        failed = [pkg for _, pkg, _ in missing]
        _log("Cannot install — pip not available.")
        return [], failed

    succeeded, failed = [], []
    for _imp, pkg, ver in missing:
        if install_package(pkg, ver):
            succeeded.append(pkg)
        else:
            failed.append(pkg)

    return succeeded, failed


# ── Background auto-install ───────────────────────────────────────────────────

def auto_install_in_background():
    """
    Launch a daemon thread to install missing packages.
    Returns immediately — Blender's UI is never blocked.

    The thread acquires _install_lock so a second call while one is already
    running does nothing.
    """
    global _install_thread, _install_done

    if _install_done:
        return   # already ran this session

    if _install_thread is not None and _install_thread.is_alive():
        return   # already running

    def _worker():
        global _install_done
        with _install_lock:
            try:
                missing = get_missing_packages()
                if missing:
                    succeeded, failed = install_all_missing()
                    if succeeded:
                        _log(f"Auto-installed: {succeeded}. "
                             "Packages are now available (no restart needed).")
                    if failed:
                        _log(f"Auto-install failed for: {failed}. "
                             "Use Addon Preferences → 'Install Dependencies'.")
                else:
                    _log("All dependencies present.")
            except Exception as e:
                _log(f"Auto-install error: {e}")
            finally:
                _install_done = True

    _install_thread = threading.Thread(target=_worker, name="NB-DepInstall", daemon=True)
    _install_thread.start()


# ── Status check (for preferences UI) ────────────────────────────────────────

def check_all() -> dict:
    """
    Return status of all required packages.

    Result:
        {
            "all_ok": bool,
            "installing": bool,   # True if background thread is still running
            "packages": [{"name": str, "import": str, "installed": bool}, ...]
        }
    """
    installing = (_install_thread is not None and _install_thread.is_alive())
    packages = [
        {"name": pkg, "import": imp, "installed": is_installed(imp)}
        for imp, pkg, _ in REQUIRED_PACKAGES
    ]
    return {
        "all_ok": all(p["installed"] for p in packages),
        "installing": installing,
        "packages": packages,
    }
