"""
BlenderNanoBanana - Reference Image Generator

Generates reference images for UV regions via Nano Banana.
Uses viewport screenshot + semantic tag as context.
Stores results in cache.
"""

from typing import Optional, List

from .cache_manager import save_reference_image, get_reference_images
from .viewport_handler import get_latest_capture
from ..api.google_vision import generate_reference_image
from ..utils.image_processing import image_to_base64
from ..utils.logging import log_info, log_debug, log_error

_MODULE = "ReferenceGenerator"


def generate_references(
    context,
    api_key: str,
    uv_region_id: str,
    tag_definition: dict,
    project_name: str,
    count: int = 3,
) -> List[str]:
    """
    Generate reference images for a UV region.

    Args:
        context: Blender context
        api_key: Google API key
        uv_region_id: UV island identifier
        tag_definition: Semantic tag definition dict
        project_name: Used for cache organization
        count: Number of references to generate

    Returns:
        List of paths to saved reference images.
    """
    saved_paths = []

    # Get viewport context image
    viewport_b64 = None
    viewport_path = get_latest_capture(context, project_name)
    if viewport_path:
        viewport_b64 = image_to_base64(viewport_path)
        log_debug(f"Using viewport context: {viewport_path}", _MODULE)

    log_info(f"Generating {count} reference images for region '{uv_region_id}'...", _MODULE)

    for i in range(count):
        log_debug(f"Generating reference {i+1}/{count}...", _MODULE)

        image_b64 = generate_reference_image(
            api_key=api_key,
            tag_definition=tag_definition,
            viewport_b64=viewport_b64,
        )

        if image_b64 is None:
            log_error(f"Reference {i+1} generation failed.", _MODULE)
            continue

        saved = save_reference_image(
            context=context,
            uv_region_id=uv_region_id,
            image_b64=image_b64,
            metadata={
                "tag_id": tag_definition.get("id"),
                "index": i + 1,
                "total_requested": count,
            },
        )
        if saved:
            saved_paths.append(saved)

    log_info(f"Generated {len(saved_paths)}/{count} references for '{uv_region_id}'.", _MODULE)
    return saved_paths


def get_or_generate_references(
    context,
    api_key: str,
    uv_region_id: str,
    tag_definition: dict,
    project_name: str,
    count: int = 3,
    force: bool = False,
) -> List[str]:
    """
    Return existing references or generate new ones if none exist.

    Args:
        force: Always generate new references even if cached ones exist.
    """
    if not force:
        existing = get_reference_images(context, uv_region_id)
        if existing:
            log_debug(f"Using {len(existing)} cached references for '{uv_region_id}'.", _MODULE)
            return existing

    return generate_references(
        context=context,
        api_key=api_key,
        uv_region_id=uv_region_id,
        tag_definition=tag_definition,
        project_name=project_name,
        count=count,
    )
