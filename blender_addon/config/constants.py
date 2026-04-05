"""
BlenderNanoBanana - Central Configuration
All magic numbers, enums, and settings live here.
"""

# ─── API Settings ─────────────────────────────────────────────────────────────

# Gemini 3 Flash - JSON Spec Generator (text)
GEMINI_MODEL_ID = "gemini-3-flash-preview"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com"

# Gemini 3.1 Flash Image - Texture / Reference Image Generator
GEMINI_IMAGE_MODEL_ID = "gemini-3.1-flash-image-preview"
GEMINI_IMAGE_TIMEOUT = 120      # seconds
GEMINI_IMAGE_RETRY_COUNT = 2    # fewer retries since each attempt is slow
GEMINI_IMAGE_RETRY_DELAY = 2.0  # seconds

# General API
API_REQUEST_TIMEOUT = 60.0      # seconds
API_DEFAULT_TIMEOUT = 60
API_MAX_RETRIES = 3
API_RETRY_DELAY_SEC = 2.0       # seconds between retries

# ─── Cache Settings ───────────────────────────────────────────────────────────

CACHE_ENABLED = True
CACHE_AUTO_CLEANUP = True
CACHE_MAX_VERSIONS_PER_REGION = 5
CACHE_SUBDIR_REFERENCES = "references"
CACHE_SUBDIR_TEXTURES = "textures"
CACHE_SUBDIR_VIEWPORT = "viewport_captures"
CACHE_SUBDIR_PROJECTS = "projects"
CACHE_METADATA_FILENAME = "metadata.json"
CACHE_PROJECT_INDEX_FILENAME = "project_index.json"

# ─── UV Analysis Settings ─────────────────────────────────────────────────────

UV_ISLAND_THRESHOLD = 0.001       # Min UV distance to separate islands
UV_SYMMETRY_TOLERANCE = 0.01      # Tolerance for mirror detection
UV_SEAM_DETECTION_ANGLE = 30.0    # Degrees - edges sharper than this are seam candidates
UV_MIN_ISLAND_AREA = 0.0001       # Islands smaller than this are ignored
UV_PACK_MARGIN = 0.005            # Margin between packed islands

# ─── Viewport Overlay Settings ────────────────────────────────────────────────

OVERLAY_UV_ISLAND_COLOR = (0.2, 0.8, 1.0, 0.4)        # Selected UV highlight
OVERLAY_UV_HIGHLIGHT_COLOR = (0.2, 0.8, 1.0, 0.8)     # Alias used by draw code
OVERLAY_UV_ISLAND_OUTLINE = (0.1, 0.6, 0.9, 0.9)      # Island outline
OVERLAY_SEAM_COLOR = (1.0, 0.2, 0.2, 0.9)              # Seam lines
OVERLAY_SYMMETRY_COLOR = (0.4, 1.0, 0.4, 0.6)          # Symmetrical regions
OVERLAY_TAG_LABEL_COLOR = (1.0, 1.0, 1.0, 0.9)         # Tag text
OVERLAY_TAG_BG_COLOR = (0.0, 0.0, 0.0, 0.6)            # Tag text background
OVERLAY_LINE_WIDTH = 2.0
OVERLAY_FONT_SIZE = 12
OVERLAY_OPACITY = 0.8

# ─── Texture Settings ─────────────────────────────────────────────────────────

TEXTURE_PREFIX = "generated_"
MATERIAL_PREFIX = "mat_"
TEXTURE_DEFAULT_SIZE = 2048
TEXTURE_THUMBNAIL_SIZE = 128

# Supported texture formats
TEXTURE_FORMATS = ["png", "exr", "jpg"]
TEXTURE_FORMAT_DEFAULT_COLOR = "png"     # For albedo (sRGB)
TEXTURE_FORMAT_DEFAULT_DATA = "exr"      # For normal/roughness/metallic

# ─── Seam Tag Colors ──────────────────────────────────────────────────────────
# Known tag keywords → fixed RGBA color. Unknown tags get hash-based color at runtime.

SEAM_TAG_COLORS = {
    "metallic":  (1.0, 0.80, 0.00, 1.0),  # gold
    "metal":     (1.0, 0.80, 0.00, 1.0),  # gold
    "fabric":    (0.3, 0.50, 1.00, 1.0),  # blue
    "cloth":     (0.3, 0.50, 1.00, 1.0),  # blue
    "skin":      (1.0, 0.50, 0.50, 1.0),  # pink
    "wood":      (0.6, 0.30, 0.10, 1.0),  # brown
    "stone":     (0.6, 0.60, 0.60, 1.0),  # grey
    "rock":      (0.6, 0.60, 0.60, 1.0),  # grey
    "glass":     (0.5, 0.90, 1.00, 1.0),  # light cyan
    "plastic":   (0.9, 0.30, 0.90, 1.0),  # purple
    "rubber":    (0.2, 0.20, 0.20, 1.0),  # dark
    "leather":   (0.5, 0.25, 0.05, 1.0),  # dark brown
    "emission":  (1.0, 1.00, 0.20, 1.0),  # bright yellow
    "emissive":  (1.0, 1.00, 0.20, 1.0),  # bright yellow
}

# ─── Naming Conventions ───────────────────────────────────────────────────────

UV_REGION_PREFIX = "uv_"
SEMANTIC_TAG_CUSTOM_PREFIX = "custom_"

# ─── Gemini JSON Schema ───────────────────────────────────────────────────────
# Used with structured outputs - forces Gemini to return exact valid JSON

GEMINI_TEXTURE_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "material_type": {
            "type": "string",
            "description": "Primary material: skin, fabric, metal, wood, stone, leather, plastic, etc."
        },
        "detail_level": {
            "type": "string",
            "enum": ["low", "medium", "high", "ultra"]
        },
        "surface_characteristic": {
            "type": "string",
            "description": "Surface quality: smooth, rough, glossy, matte, woven, grainy, etc."
        },
        "color_temperature": {
            "type": "string",
            "enum": ["warm", "cool", "neutral"]
        },
        "roughness_profile": {
            "type": "string",
            "description": "Roughness description: smooth, slightly_rough, rough, very_rough"
        },
        "imperfection_level": {
            "type": "string",
            "enum": ["pristine", "subtle", "noticeable", "weathered", "damaged"]
        },
        "texture_pattern": {
            "type": "string",
            "description": "Pattern: none, woven, grain, scales, pores, knit, brickwork, etc."
        },
        "wear_level": {
            "type": "string",
            "enum": ["new", "slightly_worn", "worn", "heavily_worn", "antique"]
        },
        "color_variation": {
            "type": "string",
            "enum": ["uniform", "subtle_variation", "strong_variation", "patterned"]
        },
        "special_properties": {
            "type": "string",
            "description": "Any additional material-specific properties"
        }
    },
    "required": [
        "material_type",
        "detail_level",
        "surface_characteristic",
        "roughness_profile"
    ]
}
