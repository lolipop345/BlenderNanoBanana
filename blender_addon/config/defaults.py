"""
BlenderNanoBanana - Default UI Values and Settings
"""

# ─── API Defaults ─────────────────────────────────────────────────────────────

DEFAULT_GOOGLE_API_KEY = ""
DEFAULT_NANO_BANANA_API_URL = ""

# ─── Cache Defaults ───────────────────────────────────────────────────────────

DEFAULT_CACHE_MAX_VERSIONS = 5
DEFAULT_CACHE_AUTO_CLEANUP = True
DEFAULT_CACHE_BASE_PATH = ""  # Empty = use addon directory

# ─── Generation Defaults ──────────────────────────────────────────────────────

DEFAULT_ENGINE_PRESET = "unity"
DEFAULT_TEXTURE_SIZE = "2048"
DEFAULT_GENERATE_REFERENCES = True
DEFAULT_REFERENCES_COUNT = 3  # How many reference images to generate

# ─── UV Analysis Defaults ─────────────────────────────────────────────────────

DEFAULT_DETECT_SYMMETRY = True
DEFAULT_AUTO_DETECT_ISLANDS = True
DEFAULT_SHOW_VIEWPORT_OVERLAY = True

# ─── Unwrap Defaults ──────────────────────────────────────────────────────────

DEFAULT_UNWRAP_METHOD = "angle_based"  # angle_based or conformal
DEFAULT_UNWRAP_FILL_HOLES = True
DEFAULT_UNWRAP_CORRECT_ASPECT = True
DEFAULT_PACK_AFTER_UNWRAP = True
DEFAULT_PACK_MARGIN = 0.005

# ─── Semantic Tag Defaults ────────────────────────────────────────────────────

DEFAULT_SEMANTIC_TAG = "fabric_clothing"
DEFAULT_DETAIL_LEVEL = "medium"
DEFAULT_REALISM_LEVEL = "realistic"

# ─── Viewport Overlay Defaults ────────────────────────────────────────────────

DEFAULT_OVERLAY_OPACITY = 0.5
DEFAULT_OVERLAY_SHOW_TAGS = True
DEFAULT_OVERLAY_SHOW_SEAMS = True
DEFAULT_OVERLAY_SHOW_ISLANDS = True
