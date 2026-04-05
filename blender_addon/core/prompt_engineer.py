"""
BlenderNanoBanana - Prompt Engineer (Fast Static Specs)

NO API calls for spec generation — instant lookup table for all common
material tags. This eliminates the Gemini Flash round-trip entirely,
cutting total generation time roughly in half.

If a tag is not in the lookup table, a fallback spec is built from the
tag name string alone (still no API call).
"""

from typing import Optional, Dict, Any
from ..utils.logging import log_info, log_debug

_MODULE = "PromptEngineer"


# ── Static PBR Spec Lookup Table ──────────────────────────────────────────────
# Key = lowercase tag name (or keyword within it)
# Provides instant specs without any LLM round-trip.

_STATIC_SPECS: Dict[str, Dict[str, Any]] = {
    "skin": {
        "material_type": "skin",
        "detail_level": "high",
        "surface_characteristic": "smooth_with_pores",
        "color_temperature": "warm",
        "roughness_profile": "slightly_rough",
        "imperfection_level": "subtle",
        "texture_pattern": "pores",
        "wear_level": "new",
        "color_variation": "subtle_variation",
        "special_properties": "human skin, subsurface scattering warmth, natural flesh tones",
    },
    "metal": {
        "material_type": "metal",
        "detail_level": "high",
        "surface_characteristic": "smooth",
        "color_temperature": "cool",
        "roughness_profile": "smooth",
        "imperfection_level": "subtle",
        "texture_pattern": "none",
        "wear_level": "slightly_worn",
        "color_variation": "uniform",
        "special_properties": "metallic, high reflectance, subtle surface scratches",
    },
    "steel": {
        "material_type": "steel",
        "detail_level": "high",
        "surface_characteristic": "smooth",
        "color_temperature": "cool",
        "roughness_profile": "smooth",
        "imperfection_level": "subtle",
        "texture_pattern": "none",
        "wear_level": "slightly_worn",
        "color_variation": "uniform",
        "special_properties": "brushed steel, metallic sheen, subtle grain",
    },
    "iron": {
        "material_type": "iron",
        "detail_level": "high",
        "surface_characteristic": "grainy",
        "color_temperature": "neutral",
        "roughness_profile": "slightly_rough",
        "imperfection_level": "noticeable",
        "texture_pattern": "grain",
        "wear_level": "worn",
        "color_variation": "subtle_variation",
        "special_properties": "cast iron, dark grey, slight rust hints",
    },
    "gold": {
        "material_type": "gold",
        "detail_level": "high",
        "surface_characteristic": "glossy",
        "color_temperature": "warm",
        "roughness_profile": "smooth",
        "imperfection_level": "pristine",
        "texture_pattern": "none",
        "wear_level": "new",
        "color_variation": "uniform",
        "special_properties": "pure gold, warm yellow metallic, high reflectance",
    },
    "leather": {
        "material_type": "leather",
        "detail_level": "high",
        "surface_characteristic": "grainy",
        "color_temperature": "warm",
        "roughness_profile": "slightly_rough",
        "imperfection_level": "subtle",
        "texture_pattern": "grain",
        "wear_level": "slightly_worn",
        "color_variation": "subtle_variation",
        "special_properties": "genuine leather, fine grain, natural texture",
    },
    "wood": {
        "material_type": "wood",
        "detail_level": "high",
        "surface_characteristic": "grainy",
        "color_temperature": "warm",
        "roughness_profile": "rough",
        "imperfection_level": "subtle",
        "texture_pattern": "grain",
        "wear_level": "slightly_worn",
        "color_variation": "strong_variation",
        "special_properties": "wooden surface, visible wood grain, natural knots",
    },
    "fabric": {
        "material_type": "fabric",
        "detail_level": "high",
        "surface_characteristic": "woven",
        "color_temperature": "neutral",
        "roughness_profile": "rough",
        "imperfection_level": "subtle",
        "texture_pattern": "woven",
        "wear_level": "new",
        "color_variation": "subtle_variation",
        "special_properties": "woven fabric, visible thread pattern, soft surface",
    },
    "cloth": {
        "material_type": "cloth",
        "detail_level": "high",
        "surface_characteristic": "woven",
        "color_temperature": "neutral",
        "roughness_profile": "rough",
        "imperfection_level": "subtle",
        "texture_pattern": "woven",
        "wear_level": "new",
        "color_variation": "subtle_variation",
        "special_properties": "soft cloth, woven texture, smooth fibers",
    },
    "shirt": {
        "material_type": "fabric",
        "detail_level": "high",
        "surface_characteristic": "woven",
        "color_temperature": "neutral",
        "roughness_profile": "slightly_rough",
        "imperfection_level": "subtle",
        "texture_pattern": "woven",
        "wear_level": "new",
        "color_variation": "uniform",
        "special_properties": "cotton shirt fabric, fine weave, soft material",
    },
    "pants": {
        "material_type": "denim",
        "detail_level": "high",
        "surface_characteristic": "woven",
        "color_temperature": "cool",
        "roughness_profile": "rough",
        "imperfection_level": "subtle",
        "texture_pattern": "woven",
        "wear_level": "slightly_worn",
        "color_variation": "subtle_variation",
        "special_properties": "denim fabric, diagonal twill, subtle fading",
    },
    "stone": {
        "material_type": "stone",
        "detail_level": "high",
        "surface_characteristic": "rough",
        "color_temperature": "neutral",
        "roughness_profile": "very_rough",
        "imperfection_level": "noticeable",
        "texture_pattern": "grainy",
        "wear_level": "worn",
        "color_variation": "strong_variation",
        "special_properties": "natural stone, irregular surface, rocky texture",
    },
    "plastic": {
        "material_type": "plastic",
        "detail_level": "medium",
        "surface_characteristic": "smooth",
        "color_temperature": "neutral",
        "roughness_profile": "smooth",
        "imperfection_level": "subtle",
        "texture_pattern": "none",
        "wear_level": "new",
        "color_variation": "uniform",
        "special_properties": "hard plastic, slightly glossy, minimal texture",
    },
    "rubber": {
        "material_type": "rubber",
        "detail_level": "medium",
        "surface_characteristic": "bumpy",
        "color_temperature": "neutral",
        "roughness_profile": "rough",
        "imperfection_level": "subtle",
        "texture_pattern": "bumpy",
        "wear_level": "new",
        "color_variation": "uniform",
        "special_properties": "rubber material, matte surface, slight texture",
    },
    "glass": {
        "material_type": "glass",
        "detail_level": "high",
        "surface_characteristic": "glossy",
        "color_temperature": "cool",
        "roughness_profile": "smooth",
        "imperfection_level": "pristine",
        "texture_pattern": "none",
        "wear_level": "new",
        "color_variation": "uniform",
        "special_properties": "transparent glass, highly reflective, clear",
    },
    "ceramic": {
        "material_type": "ceramic",
        "detail_level": "high",
        "surface_characteristic": "glossy",
        "color_temperature": "neutral",
        "roughness_profile": "smooth",
        "imperfection_level": "subtle",
        "texture_pattern": "none",
        "wear_level": "new",
        "color_variation": "uniform",
        "special_properties": "glazed ceramic, smooth porcelain-like surface",
    },
    "fur": {
        "material_type": "fur",
        "detail_level": "high",
        "surface_characteristic": "fuzzy",
        "color_temperature": "warm",
        "roughness_profile": "rough",
        "imperfection_level": "subtle",
        "texture_pattern": "grain",
        "wear_level": "new",
        "color_variation": "subtle_variation",
        "special_properties": "animal fur, directional fibers, soft appearance",
    },
    "hair": {
        "material_type": "hair",
        "detail_level": "ultra",
        "surface_characteristic": "smooth",
        "color_temperature": "warm",
        "roughness_profile": "smooth",
        "imperfection_level": "subtle",
        "texture_pattern": "grain",
        "wear_level": "new",
        "color_variation": "subtle_variation",
        "special_properties": "hair strands, directional flow, natural color",
    },
    "concrete": {
        "material_type": "concrete",
        "detail_level": "medium",
        "surface_characteristic": "rough",
        "color_temperature": "cool",
        "roughness_profile": "rough",
        "imperfection_level": "noticeable",
        "texture_pattern": "grainy",
        "wear_level": "worn",
        "color_variation": "subtle_variation",
        "special_properties": "poured concrete, aggregate texture, grey tones",
    },
    "emission": {
        "material_type": "emission",
        "detail_level": "medium",
        "surface_characteristic": "smooth",
        "color_temperature": "warm",
        "roughness_profile": "smooth",
        "imperfection_level": "pristine",
        "texture_pattern": "none",
        "wear_level": "new",
        "color_variation": "uniform",
        "special_properties": "emissive material, glowing, light-emitting surface",
    },
    "default": {
        "material_type": "generic",
        "detail_level": "high",
        "surface_characteristic": "smooth",
        "color_temperature": "neutral",
        "roughness_profile": "slightly_rough",
        "imperfection_level": "subtle",
        "texture_pattern": "none",
        "wear_level": "new",
        "color_variation": "subtle_variation",
        "special_properties": "",
    },
}


def get_spec_from_tag(tag_name: str) -> Dict[str, Any]:
    """
    Instantly return a PBR spec from a material tag name — NO API call.

    Looks up the tag in the static table. If not found, tries keyword matching,
    then falls back to generating a sensible spec from the tag name itself.
    """
    tag_lower = tag_name.lower().strip()

    # Exact match
    if tag_lower in _STATIC_SPECS:
        spec = dict(_STATIC_SPECS[tag_lower])
        log_info(f"Static spec (exact): {tag_name}", _MODULE)
        return spec

    # Keyword match (e.g. "Right Full Arm (Shirt)" → "shirt")
    for keyword, spec_template in _STATIC_SPECS.items():
        if keyword in tag_lower:
            spec = dict(spec_template)
            # Override material_type with full tag for better prompt accuracy
            spec["special_properties"] = f"{tag_name} material"
            log_info(f"Static spec (keyword '{keyword}'): {tag_name}", _MODULE)
            return spec

    # Fallback: build generic spec with tag name embedded
    log_info(f"Static spec (fallback): {tag_name}", _MODULE)
    spec = dict(_STATIC_SPECS["default"])
    spec["material_type"] = tag_name
    spec["special_properties"] = f"{tag_name} surface material"
    return spec


def get_spec_from_prompt(
    api_key: str,
    user_prompt: str,
    viewport_image_path=None,
    uv_layout_path=None,
    mesh_description=None,
) -> Optional[Dict[str, Any]]:
    """
    Backwards-compatible wrapper that extracts the tag name from the prompt
    and calls get_spec_from_tag — NO API call, returns instantly.
    """
    import re
    # Extract tag from "...Generate ONLY the 'TagName' material."
    match = re.search(r"Generate ONLY the '(.+?)' material", user_prompt)
    if match:
        return get_spec_from_tag(match.group(1))

    # No tag found — try keyword matching on the whole prompt
    prompt_lower = user_prompt.lower()
    for keyword in _STATIC_SPECS:
        if keyword != "default" and keyword in prompt_lower:
            spec = dict(_STATIC_SPECS[keyword])
            spec["special_properties"] = user_prompt[:120]
            return spec

    return dict(_STATIC_SPECS["default"])
