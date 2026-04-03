"""
BlenderNanoBanana - Project Manager

Tracks per-project state: UV region assignments, tag history, generation log.
Saves/loads a project index JSON file alongside the cache.
"""

import os
import time
from typing import Optional, Dict, Any, List

from .cache_manager import get_cache_base_path, get_project_name
from ..utils.serialization import load_json, save_json
from ..utils.logging import log_info, log_debug

_MODULE = "ProjectManager"

# In-memory project state (cleared on new project load)
_project_state: Dict[str, Any] = {}


def load_project(context) -> dict:
    """Load the project index from disk into memory."""
    global _project_state
    index_path = _get_index_path(context)
    data = load_json(index_path)
    if data:
        _project_state = data
        log_debug(f"Project loaded: {get_project_name(context)}", _MODULE)
    else:
        _project_state = _empty_project(context)
    return _project_state


def save_project(context):
    """Persist the in-memory project state to disk."""
    index_path = _get_index_path(context)
    _project_state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_json(index_path, _project_state)
    log_debug(f"Project saved: {get_project_name(context)}", _MODULE)


def get_project_state() -> dict:
    """Return current in-memory project state."""
    return _project_state


def record_tag_assignment(context, uv_region_id: str, tag_id: str):
    """Record that a tag was applied to a UV region."""
    _ensure_loaded(context)
    regions = _project_state.setdefault("regions", {})
    region = regions.setdefault(uv_region_id, {})
    region["tag_id"] = tag_id
    region["tag_set_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_project(context)


def record_generation(context, uv_region_id: str, maps: List[str],
                      engine_id: str, version_dir: str):
    """Log a completed texture generation."""
    _ensure_loaded(context)
    regions = _project_state.setdefault("regions", {})
    region = regions.setdefault(uv_region_id, {})
    history = region.setdefault("generation_history", [])
    history.append({
        "engine_id": engine_id,
        "maps": maps,
        "version_dir": version_dir,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    region["latest_version_dir"] = version_dir
    save_project(context)


def get_region_info(uv_region_id: str) -> dict:
    """Return stored info for a UV region, or empty dict."""
    return _project_state.get("regions", {}).get(uv_region_id, {})


def get_all_regions() -> Dict[str, dict]:
    """Return all UV region records."""
    return _project_state.get("regions", {})


# ── Private ───────────────────────────────────────────────────────────────────

def _get_index_path(context) -> str:
    base = get_cache_base_path(context)
    project = get_project_name(context)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in project)
    return os.path.join(base, safe, "project_index.json")


def _empty_project(context) -> dict:
    return {
        "project_name": get_project_name(context),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "regions": {},
    }


def _ensure_loaded(context):
    """Load project from disk if not already in memory."""
    if not _project_state:
        load_project(context)
