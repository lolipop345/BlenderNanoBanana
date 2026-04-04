"""
BlenderNanoBanana - Prompt Engineer

Calls Gemini 3 Flash with user's text prompt → returns JSON texture spec.
"""

import os
import base64
from typing import Optional, Dict, Any, List

from ..api.google_llm import generate_texture_spec, generate_text
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "PromptEngineer"

_SPEC_SYSTEM_PROMPT = """\
You are a PBR texture specialist. The user describes a surface or material.
Return ONLY a valid JSON object — no markdown, no explanation, just JSON.
Required fields:
{
  "material_type": "<primary material: leather, metal, fabric, wood, stone, skin, plastic, etc.>",
  "detail_level": "<low|medium|high|ultra>",
  "surface_characteristic": "<smooth|rough|glossy|matte|woven|grainy|bumpy|etc.>",
  "color_temperature": "<warm|cool|neutral>",
  "roughness_profile": "<smooth|slightly_rough|rough|very_rough>",
  "imperfection_level": "<pristine|subtle|noticeable|weathered|damaged>",
  "texture_pattern": "<none|grain|woven|scales|pores|knit|brickwork|etc.>",
  "wear_level": "<new|slightly_worn|worn|heavily_worn|antique>",
  "color_variation": "<uniform|subtle_variation|strong_variation|patterned>",
  "special_properties": "<any additional relevant details, or empty string>"
}
"""


def get_spec_from_prompt(
    api_key: str,
    user_prompt: str,
    viewport_image_path: Optional[str] = None,
    uv_layout_path: Optional[str] = None,
    mesh_description: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Ask Gemini 3 Flash to generate a PBR texture spec from the user's description.

    Args:
        api_key: Google API key
        user_prompt: User's free-text material description
        viewport_image_path: Optional viewport screenshot for visual context
        uv_layout_path: Optional UV layout image for structural context
        mesh_description: Optional AI-generated mesh description

    Returns:
        JSON spec dict or None on failure.
    """
    images = _load_images(uv_layout_path, viewport_image_path)

    user_msg = f"Material description: {user_prompt}"
    if mesh_description:
        user_msg += f"\nMesh analysis: {mesh_description}"

    log_info(f"Generating texture spec from prompt: {user_prompt[:80]}", _MODULE)

    # generate_texture_spec raises RuntimeError on API failure — let it propagate
    spec = generate_texture_spec(
        api_key=api_key,
        system_prompt=_SPEC_SYSTEM_PROMPT,
        user_prompt=user_msg,
        images=images or None,
    )

    if spec is None:
        raise RuntimeError("Gemini Flash returned no spec (empty response).")

    spec = _validate_spec(spec, user_prompt)
    log_info(f"Spec: {spec}", _MODULE)
    return spec


def get_mesh_description(
    api_key: str,
    viewport_image_path: Optional[str] = None,
    uv_layout_path: Optional[str] = None,
) -> Optional[str]:
    """
    Ask Gemini 3 Flash to briefly describe the mesh from viewport/UV images.
    Used as extra context to improve texture spec accuracy.
    """
    images = _load_images(uv_layout_path, viewport_image_path)
    if not images:
        return None

    system = (
        "You are a 3D asset analyst. Given a viewport screenshot and/or UV layout, "
        "describe in 1-2 sentences what kind of object it is and its surface material. "
        "Be factual and brief. No markdown."
    )
    user = "Analyse the image(s) and describe this 3D mesh object."

    description = generate_text(
        api_key=api_key,
        system_prompt=system,
        user_prompt=user,
        images=images,
        timeout=20.0,
    )
    if description:
        log_info(f"Mesh description: {description[:100]}", _MODULE)
    return description


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_images(
    *paths: Optional[str],
) -> List[Dict[str, str]]:
    """Load image files as base64 inline_data dicts for Gemini."""
    result = []
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
            result.append({"mime_type": mime, "data": data})
        except Exception:
            pass
    return result


def _validate_spec(spec: dict, user_prompt: str) -> dict:
    """Ensure all required fields are present."""
    # Infer material_type from prompt if missing
    prompt_lower = user_prompt.lower()
    material_hint = "generic"
    for keyword in ["leather", "metal", "fabric", "wood", "stone", "skin",
                    "plastic", "glass", "rubber", "cloth", "fur", "ceramic"]:
        if keyword in prompt_lower:
            material_hint = keyword
            break

    defaults = {
        "material_type": material_hint,
        "detail_level": "medium",
        "surface_characteristic": "smooth",
        "color_temperature": "neutral",
        "roughness_profile": "medium",
        "imperfection_level": "subtle",
        "texture_pattern": "none",
        "wear_level": "new",
        "color_variation": "subtle_variation",
        "special_properties": "",
    }
    for key, val in defaults.items():
        if key not in spec or not spec[key]:
            spec[key] = val
    return spec
