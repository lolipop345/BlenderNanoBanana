"""
BlenderNanoBanana - Semantic Tag Manager

Manages standard tag library + custom tags per project.
Custom tags are stored in the project cache as JSON.
"""

import os
from typing import Optional, Dict, Any, List

from ..config.semantic_tags import SEMANTIC_TAGS, TAG_CATEGORIES
from ..utils.serialization import load_json, save_json
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "SemanticManager"

# Custom tags added by the user (in-memory + persisted to JSON)
_custom_tags: Dict[str, dict] = {}


def get_tag(tag_id: str) -> Optional[dict]:
    """Return tag definition by ID. Checks standard library then custom tags."""
    if tag_id in SEMANTIC_TAGS:
        return SEMANTIC_TAGS[tag_id]
    if tag_id in _custom_tags:
        return _custom_tags[tag_id]
    return None


def get_all_tags() -> Dict[str, dict]:
    """Return all tags (standard + custom)."""
    combined = dict(SEMANTIC_TAGS)
    combined.update(_custom_tags)
    return combined


def get_tags_for_category(category: str) -> List[dict]:
    """Return all tags belonging to a category."""
    return [
        tag for tag in get_all_tags().values()
        if tag.get("category") == category
    ]


def get_categories() -> Dict[str, str]:
    """Return the category id→display name mapping."""
    return TAG_CATEGORIES


def add_custom_tag(tag_id: str, tag_def: dict) -> bool:
    """Add or update a custom tag definition."""
    if not tag_id or not isinstance(tag_def, dict):
        return False
    tag_def["id"] = tag_id
    _custom_tags[tag_id] = tag_def
    log_info(f"Custom tag added: '{tag_id}'", _MODULE)
    return True


def remove_custom_tag(tag_id: str) -> bool:
    """Remove a custom tag. Standard tags cannot be removed."""
    if tag_id in _custom_tags:
        del _custom_tags[tag_id]
        log_info(f"Custom tag removed: '{tag_id}'", _MODULE)
        return True
    return False


def apply_tag_to_region(context, uv_region_id: str, tag_id: str,
                        project_name: str) -> bool:
    """
    Associate a semantic tag with a UV region and persist to disk.

    Stores: <cache>/<project>/<uv_region_id>/semantic_tag.json
    """
    tag = get_tag(tag_id)
    if tag is None:
        log_error(f"Unknown tag: '{tag_id}'", _MODULE)
        return False

    from .cache_manager import get_cache_base_path
    base = get_cache_base_path(context)
    safe_proj = _safe_name(project_name)
    tag_file = os.path.join(base, safe_proj, uv_region_id, "semantic_tag.json")

    data = {
        "uv_region_id": uv_region_id,
        "tag_id": tag_id,
        "tag_definition": tag,
    }
    save_json(tag_file, data)
    log_debug(f"Tag '{tag_id}' applied to region '{uv_region_id}'.", _MODULE)
    return True


def get_tag_for_region(context, uv_region_id: str, project_name: str) -> Optional[dict]:
    """Load the semantic tag data for a UV region from disk."""
    from .cache_manager import get_cache_base_path
    base = get_cache_base_path(context)
    safe_proj = _safe_name(project_name)
    tag_file = os.path.join(base, safe_proj, uv_region_id, "semantic_tag.json")
    return load_json(tag_file)


def load_custom_tags(context, project_name: str):
    """Load custom tags from a project-local JSON file."""
    global _custom_tags
    from .cache_manager import get_cache_base_path
    base = get_cache_base_path(context)
    safe_proj = _safe_name(project_name)
    custom_file = os.path.join(base, safe_proj, "custom_tags.json")
    data = load_json(custom_file)
    if data and isinstance(data, dict):
        _custom_tags = data
        log_debug(f"Loaded {len(_custom_tags)} custom tags.", _MODULE)


def save_custom_tags(context, project_name: str):
    """Persist custom tags to project-local JSON."""
    from .cache_manager import get_cache_base_path
    base = get_cache_base_path(context)
    safe_proj = _safe_name(project_name)
    custom_file = os.path.join(base, safe_proj, "custom_tags.json")
    save_json(custom_file, _custom_tags)
    log_debug(f"Saved {len(_custom_tags)} custom tags.", _MODULE)


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
