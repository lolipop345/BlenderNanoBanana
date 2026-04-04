"""
BlenderNanoBanana - Image Processing Utilities

Handles image loading, saving, resizing, and thumbnail generation
using Blender's built-in image types and optionally Pillow.
"""

import os
import base64
from typing import Optional, Tuple


def image_to_base64(filepath: Optional[str]) -> Optional[str]:
    """Read an image file and return base64-encoded string."""
    if not filepath or not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"[NanoBanana::ImageProcessing] Failed to encode image '{filepath}': {e}")
        return None


def base64_to_file(b64_data: str, output_path: str) -> bool:
    """Decode base64 image data and write to file."""
    if not b64_data or not output_path:
        return False
    try:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        data = base64.b64decode(b64_data)
        with open(output_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"[NanaBanana::ImageProcessing] Failed to write image: {e}")
        return False


def load_blender_image(filepath: str):
    """Load an image into Blender's image data block."""
    import bpy
    if filepath in bpy.data.images:
        return bpy.data.images[filepath]
    try:
        img = bpy.data.images.load(filepath)
        return img
    except Exception as e:
        print(f"[NanoBanana::ImageProcessing] Cannot load image '{filepath}': {e}")
        return None


def create_blender_image(name: str, width: int, height: int,
                         color=(0.0, 0.0, 0.0, 1.0)):
    """Create a new blank Blender image data block."""
    import bpy
    img = bpy.data.images.new(name, width=width, height=height)
    img.pixels = [c for _ in range(width * height) for c in color]
    return img


def save_blender_image(image, filepath: str, file_format: str = "PNG") -> bool:
    """Save a Blender image data block to disk."""
    import bpy
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        scene = bpy.context.scene
        settings = scene.render.image_settings
        orig_format = settings.file_format
        settings.file_format = file_format
        image.save_render(filepath, scene=scene)
        settings.file_format = orig_format
        return True
    except Exception as e:
        print(f"[NanoBanana::ImageProcessing] Failed to save image: {e}")
        return False


def generate_thumbnail(filepath: str, thumb_size: int = 128) -> Optional[str]:
    """
    Generate a small thumbnail and return its path.
    Tries Pillow first, falls back to skipping.
    """
    if not os.path.isfile(filepath):
        return None

    thumb_path = filepath.rsplit(".", 1)[0] + f"_thumb_{thumb_size}.png"
    if os.path.isfile(thumb_path):
        return thumb_path

    try:
        from PIL import Image
        with Image.open(filepath) as img:
            img.thumbnail((thumb_size, thumb_size))
            img.save(thumb_path, "PNG")
        return thumb_path
    except ImportError:
        # Pillow not available — skip thumbnail
        return None
    except Exception as e:
        print(f"[NanoBanana::ImageProcessing] Thumbnail error: {e}")
        return None


def get_image_size(filepath: str) -> Tuple[int, int]:
    """Return (width, height) of an image file. (0,0) on failure."""
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            return img.size
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: use Blender
    try:
        import bpy
        img = bpy.data.images.load(filepath)
        size = (img.size[0], img.size[1])
        bpy.data.images.remove(img)
        return size
    except Exception:
        return (0, 0)
