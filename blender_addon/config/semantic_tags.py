"""
BlenderNanoBanana - Standard Semantic Tag Definitions

Each tag has a rich definition that:
1. Describes what the UV region represents
2. Specifies expected detail and realism level
3. Provides hints for Gemini 3 Flash JSON spec generation
"""

# ─── Tag Structure ────────────────────────────────────────────────────────────
#
# {
#   "id": str               - Unique identifier
#   "name": str             - Display name
#   "category": str         - Grouping category
#   "description": str      - What this UV region represents
#   "detail_level": str     - low / medium / high / ultra
#   "realism": str          - photorealistic / realistic / stylized / cartoon / abstract
#   "special_notes": str    - Important notes for generation
#   "gemini_hints": dict    - Hints passed to Gemini for JSON spec generation
# }

SEMANTIC_TAGS = {

    # ── Character: Face & Head ────────────────────────────────────────────────

    "human_face": {
        "id": "human_face",
        "name": "Human Face",
        "category": "character_face",
        "description": "Realistic human face - skin, pores, subtle color variation",
        "detail_level": "high",
        "realism": "photorealistic",
        "special_notes": "Symmetrical features, anatomically accurate, natural skin imperfections",
        "gemini_hints": {
            "material_type": "skin",
            "texture_pattern": "pores",
            "imperfection_level": "subtle",
            "color_variation": "subtle_variation"
        }
    },

    "stylized_face": {
        "id": "stylized_face",
        "name": "Stylized Face",
        "category": "character_face",
        "description": "Cartoon or anime style face - simplified, expressive",
        "detail_level": "medium",
        "realism": "stylized",
        "special_notes": "Exaggerated features OK, smooth gradients, bold colors",
        "gemini_hints": {
            "material_type": "skin",
            "texture_pattern": "none",
            "imperfection_level": "pristine",
            "color_variation": "subtle_variation"
        }
    },

    "creature_face": {
        "id": "creature_face",
        "name": "Creature / Monster Face",
        "category": "character_face",
        "description": "Non-human creature face - scales, fur, alien textures",
        "detail_level": "high",
        "realism": "realistic",
        "special_notes": "Unique surface features, irregular patterns, biological authenticity",
        "gemini_hints": {
            "material_type": "scales",
            "texture_pattern": "scales",
            "imperfection_level": "noticeable",
            "color_variation": "strong_variation"
        }
    },

    # ── Character: Body ───────────────────────────────────────────────────────

    "human_skin": {
        "id": "human_skin",
        "name": "Human Body Skin",
        "category": "character_body",
        "description": "Human body skin - arms, legs, torso",
        "detail_level": "medium",
        "realism": "photorealistic",
        "special_notes": "Match tone with face UV, natural skin variation",
        "gemini_hints": {
            "material_type": "skin",
            "texture_pattern": "pores",
            "imperfection_level": "subtle",
            "color_variation": "subtle_variation"
        }
    },

    "stylized_skin": {
        "id": "stylized_skin",
        "name": "Stylized Body Skin",
        "category": "character_body",
        "description": "Cartoon/stylized body skin",
        "detail_level": "low",
        "realism": "stylized",
        "special_notes": "Smooth, minimal detail, color-consistent with face",
        "gemini_hints": {
            "material_type": "skin",
            "texture_pattern": "none",
            "imperfection_level": "pristine",
            "color_variation": "uniform"
        }
    },

    # ── Clothing ──────────────────────────────────────────────────────────────

    "fabric_clothing": {
        "id": "fabric_clothing",
        "name": "Fabric Clothing",
        "category": "clothing",
        "description": "Woven fabric - cotton, linen, polyester",
        "detail_level": "medium",
        "realism": "realistic",
        "special_notes": "Natural weave pattern, fabric drape, subtle dye variation",
        "gemini_hints": {
            "material_type": "fabric",
            "texture_pattern": "woven",
            "imperfection_level": "subtle",
            "color_variation": "subtle_variation"
        }
    },

    "leather_clothing": {
        "id": "leather_clothing",
        "name": "Leather Clothing",
        "category": "clothing",
        "description": "Genuine or faux leather - jacket, pants, boots",
        "detail_level": "high",
        "realism": "realistic",
        "special_notes": "Grain pattern, crease marks, natural sheen",
        "gemini_hints": {
            "material_type": "leather",
            "texture_pattern": "grain",
            "imperfection_level": "noticeable",
            "color_variation": "subtle_variation"
        }
    },

    "knitted_clothing": {
        "id": "knitted_clothing",
        "name": "Knitted / Wool Clothing",
        "category": "clothing",
        "description": "Knitted fabric - sweaters, wool coats",
        "detail_level": "medium",
        "realism": "realistic",
        "special_notes": "Visible stitch pattern, soft fibers, slightly rough surface",
        "gemini_hints": {
            "material_type": "fabric",
            "texture_pattern": "knit",
            "imperfection_level": "subtle",
            "color_variation": "subtle_variation"
        }
    },

    # ── Armor & Equipment ─────────────────────────────────────────────────────

    "metal_armor": {
        "id": "metal_armor",
        "name": "Metal Armor",
        "category": "equipment",
        "description": "Metallic armor plating - steel, iron, fantasy metals",
        "detail_level": "high",
        "realism": "realistic",
        "special_notes": "Scratches, dents, worn edges, reflective surfaces",
        "gemini_hints": {
            "material_type": "metal",
            "texture_pattern": "none",
            "imperfection_level": "noticeable",
            "color_variation": "subtle_variation"
        }
    },

    "worn_metal": {
        "id": "worn_metal",
        "name": "Worn / Rusted Metal",
        "category": "equipment",
        "description": "Heavily used metal with rust, patina, corrosion",
        "detail_level": "high",
        "realism": "realistic",
        "special_notes": "Heavy weathering, rust spots, peeling surface, patina buildup",
        "gemini_hints": {
            "material_type": "metal",
            "texture_pattern": "none",
            "imperfection_level": "weathered",
            "color_variation": "strong_variation"
        }
    },

    "fantasy_armor": {
        "id": "fantasy_armor",
        "name": "Fantasy / Magic Armor",
        "category": "equipment",
        "description": "Stylized fantasy armor with magical properties",
        "detail_level": "high",
        "realism": "stylized",
        "special_notes": "Ornate engravings, glowing runes, otherworldly materials",
        "gemini_hints": {
            "material_type": "metal",
            "texture_pattern": "brickwork",
            "imperfection_level": "pristine",
            "color_variation": "strong_variation"
        }
    },

    # ── Natural Materials ─────────────────────────────────────────────────────

    "wood_surface": {
        "id": "wood_surface",
        "name": "Wood Surface",
        "category": "natural",
        "description": "Natural wood - planks, furniture, floors",
        "detail_level": "medium",
        "realism": "realistic",
        "special_notes": "Wood grain direction, knots, annual rings",
        "gemini_hints": {
            "material_type": "wood",
            "texture_pattern": "grain",
            "imperfection_level": "subtle",
            "color_variation": "subtle_variation"
        }
    },

    "stone_surface": {
        "id": "stone_surface",
        "name": "Stone / Rock Surface",
        "category": "natural",
        "description": "Natural stone - walls, floors, boulders",
        "detail_level": "medium",
        "realism": "realistic",
        "special_notes": "Natural cracks, rough surface, mineral variation",
        "gemini_hints": {
            "material_type": "stone",
            "texture_pattern": "none",
            "imperfection_level": "noticeable",
            "color_variation": "strong_variation"
        }
    },

    "ground_terrain": {
        "id": "ground_terrain",
        "name": "Ground / Terrain",
        "category": "natural",
        "description": "Ground surface - dirt, grass, sand, mud",
        "detail_level": "medium",
        "realism": "realistic",
        "special_notes": "Mix of materials, organic variation, natural weathering",
        "gemini_hints": {
            "material_type": "terrain",
            "texture_pattern": "grain",
            "imperfection_level": "weathered",
            "color_variation": "strong_variation"
        }
    },

    # ── Architecture ──────────────────────────────────────────────────────────

    "brick_wall": {
        "id": "brick_wall",
        "name": "Brick Wall",
        "category": "architecture",
        "description": "Brick and mortar wall",
        "detail_level": "medium",
        "realism": "realistic",
        "special_notes": "Regular brick pattern, mortar joints, surface weathering",
        "gemini_hints": {
            "material_type": "brick",
            "texture_pattern": "brickwork",
            "imperfection_level": "noticeable",
            "color_variation": "subtle_variation"
        }
    },

    "concrete_surface": {
        "id": "concrete_surface",
        "name": "Concrete Surface",
        "category": "architecture",
        "description": "Poured or precast concrete",
        "detail_level": "medium",
        "realism": "realistic",
        "special_notes": "Smooth or rough surface, formwork marks, cracks",
        "gemini_hints": {
            "material_type": "stone",
            "texture_pattern": "none",
            "imperfection_level": "subtle",
            "color_variation": "uniform"
        }
    },

    # ── Props & Objects ───────────────────────────────────────────────────────

    "plastic_surface": {
        "id": "plastic_surface",
        "name": "Plastic Surface",
        "category": "prop",
        "description": "Smooth plastic - cases, toys, furniture",
        "detail_level": "low",
        "realism": "realistic",
        "special_notes": "Uniform surface, slight gloss, minor scratches",
        "gemini_hints": {
            "material_type": "plastic",
            "texture_pattern": "none",
            "imperfection_level": "subtle",
            "color_variation": "uniform"
        }
    },

    "glass_surface": {
        "id": "glass_surface",
        "name": "Glass Surface",
        "category": "prop",
        "description": "Glass or crystal - bottles, windows, gems",
        "detail_level": "medium",
        "realism": "realistic",
        "special_notes": "Transparent-compatible, reflections, slight impurities",
        "gemini_hints": {
            "material_type": "glass",
            "texture_pattern": "none",
            "imperfection_level": "pristine",
            "color_variation": "subtle_variation"
        }
    },

}

# ─── Categories (for UI grouping) ─────────────────────────────────────────────

TAG_CATEGORIES = {
    "character_face": "Character: Face",
    "character_body": "Character: Body",
    "clothing": "Clothing",
    "equipment": "Equipment & Armor",
    "natural": "Natural Materials",
    "architecture": "Architecture",
    "prop": "Props & Objects",
    "custom": "Custom Tags",
}

# ─── Detail Level Descriptions ────────────────────────────────────────────────

DETAIL_LEVELS = {
    "low": "Low - Simple, minimal detail (512-1024px)",
    "medium": "Medium - Balanced detail (1024-2048px)",
    "high": "High - Detailed, production quality (2048-4096px)",
    "ultra": "Ultra - Maximum detail (4096px+)",
}

# ─── Realism Levels ───────────────────────────────────────────────────────────

REALISM_LEVELS = {
    "photorealistic": "Photorealistic - Indistinguishable from photography",
    "realistic": "Realistic - Convincing, slightly stylized",
    "stylized": "Stylized - Intentionally simplified or exaggerated",
    "cartoon": "Cartoon - Bold, flat, minimal shading",
    "abstract": "Abstract - Non-representational, pattern-based",
}
