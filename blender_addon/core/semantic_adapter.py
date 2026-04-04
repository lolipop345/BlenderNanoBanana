"""
BlenderNanoBanana - Semantic Context Builder

Assembles the context payload sent to Gemini 3 Flash for JSON spec generation.
Combines: semantic tag definition + viewport image + reference images + engine spec.
"""

import os
import base64
from typing import Optional, Dict, Any, List

from ..utils.logging import log_debug

_MODULE = "SemanticAdapter"


def build_gemini_context(
    tag_id: str,
    tag_definition: dict,
    engine_spec: dict,
    viewport_image_path: Optional[str] = None,
    reference_image_paths: Optional[List[str]] = None,
    mesh_description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the context dict sent to Gemini 3 Flash.

    Returns:
        {
            "tag_id": str,
            "tag_definition": dict,
            "engine_spec": dict,
            "system_prompt": str,
            "user_prompt": str,
            "images": [{"mime_type": str, "data": base64_str}, ...],
        }
    """
    system_prompt = _build_system_prompt(tag_definition, engine_spec, mesh_description)
    user_prompt = _build_user_prompt(tag_id, tag_definition, engine_spec)
    images = _collect_images(viewport_image_path, reference_image_paths)

    log_debug(
        f"Built Gemini context for tag='{tag_id}', "
        f"images={len(images)}, engine='{engine_spec.get('id', 'unknown')}'",
        _MODULE,
    )

    return {
        "tag_id": tag_id,
        "tag_definition": tag_definition,
        "engine_spec": engine_spec,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "images": images,
    }


def _build_system_prompt(tag_def: dict, engine_spec: dict,
                         mesh_description: Optional[str] = None) -> str:
    """
    System instruction for Gemini: generate compact JSON texture parameters.
    No prose, no descriptions, just structured property values.
    """
    detail = tag_def.get("detail_level", "medium")
    realism = tag_def.get("realism", "realistic")
    notes = tag_def.get("special_notes", "")

    prompt = (
        "You are a texture parameter generator. "
        "Your ONLY job is to output a valid JSON object with texture properties. "
        "Do NOT write any text before or after the JSON. "
        "Do NOT explain anything. "
        "The JSON controls a PBR texture generator for a game engine. "
        f"Target engine: {engine_spec.get('name', 'Unknown')}. "
        f"Material detail level: {detail}. "
        f"Realism style: {realism}. "
    )
    if notes:
        prompt += f"Notes: {notes}. "
    if mesh_description:
        prompt += f"Mesh analysis: {mesh_description}. "
    prompt += "Output JSON with these exact fields and nothing else."
    return prompt


def _build_user_prompt(tag_id: str, tag_def: dict, engine_spec: dict) -> str:
    """User message asking Gemini to generate texture spec JSON."""
    hints = tag_def.get("gemini_hints", {})
    hint_str = ", ".join(f"{k}={v}" for k, v in hints.items()) if hints else ""

    maps = [
        name for name, cfg in engine_spec.get("supported_maps", {}).items()
        if cfg.get("enabled", False)
    ]
    maps_str = ", ".join(maps) if maps else "albedo"

    return (
        f"Generate texture parameters for UV region type: {tag_def.get('name', tag_id)}. "
        f"Description: {tag_def.get('description', '')}. "
        + (f"Hints: {hint_str}. " if hint_str else "")
        + f"Maps to generate: {maps_str}. "
        "Output a JSON object with: material_type, detail_level, surface_characteristic, "
        "color_temperature, roughness_profile, imperfection_level, texture_pattern, "
        "wear_level, color_variation, special_properties."
    )


def _collect_images(
    viewport_path: Optional[str],
    reference_paths: Optional[List[str]],
) -> List[Dict[str, str]]:
    """
    Encode image files as base64 for the Gemini multimodal API.

    Returns list of {"mime_type": "image/png", "data": base64_str}.
    """
    images = []
    all_paths = []

    if viewport_path and os.path.isfile(viewport_path):
        all_paths.append(viewport_path)

    if reference_paths:
        for p in reference_paths:
            if p and os.path.isfile(p):
                all_paths.append(p)

    for path in all_paths:
        try:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
            images.append({"mime_type": mime, "data": data})
        except Exception:
            pass

    return images
