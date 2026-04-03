"""
BlenderNanoBanana - Engine-Specific PBR Presets

Each engine defines:
- Supported texture maps
- Format and size requirements
- Default settings (ALL maps default to False/disabled)
- User enables only what they need
"""

# ─── Engine Preset Structure ──────────────────────────────────────────────────
#
# {
#   "id": str
#   "name": str
#   "description": str
#   "supported_maps": {
#     map_name: {
#       "enabled": bool          (default: False)
#       "size": int              (pixels)
#       "format": str            (sRGB / linear_tangent / linear_grayscale)
#       "file_ext": str          (exr / png / tga)
#       "description": str
#       "blender_socket": str    (Principled BSDF input name)
#     }
#   }
#   "material_shader": str
#   "notes": str
# }

ENGINE_PRESETS = {

    "unity": {
        "id": "unity",
        "name": "Unity (Standard / URP / HDRP)",
        "description": "Unity game engine - supports Standard, URP, and HDRP pipelines",
        "supported_maps": {
            "albedo": {
                "enabled": False,
                "size": 2048,
                "format": "sRGB",
                "file_ext": "png",
                "description": "Albedo (Base Color) - sRGB, 8-bit",
                "blender_socket": "Base Color",
                "unity_slot": "MainTex / _BaseMap"
            },
            "normal": {
                "enabled": False,
                "size": 2048,
                "format": "linear_tangent",
                "file_ext": "png",
                "description": "Normal Map - Tangent space, linear",
                "blender_socket": "Normal",
                "unity_slot": "BumpMap / _BumpMap"
            },
            "roughness": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Roughness - Linear grayscale",
                "blender_socket": "Roughness",
                "unity_slot": "SmoothnessMap (inverted)"
            },
            "metallic": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Metallic - Linear grayscale",
                "blender_socket": "Metallic",
                "unity_slot": "MetallicGlossMap"
            },
            "ao": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Ambient Occlusion - Linear grayscale",
                "blender_socket": "Ambient Occlusion",
                "unity_slot": "OcclusionMap"
            },
            "emission": {
                "enabled": False,
                "size": 2048,
                "format": "sRGB",
                "file_ext": "png",
                "description": "Emission / Glow - sRGB",
                "blender_socket": "Emission",
                "unity_slot": "EmissionMap"
            },
            "height": {
                "enabled": False,
                "size": 1024,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Height / Displacement - Linear grayscale",
                "blender_socket": "Height",
                "unity_slot": "ParallaxMap"
            },
        },
        "material_shader": "Standard / Lit",
        "notes": "For HDRP, use EXR format instead of PNG for better precision"
    },

    "roblox": {
        "id": "roblox",
        "name": "Roblox Studio",
        "description": "Roblox game platform - limited PBR support",
        "supported_maps": {
            "albedo": {
                "enabled": False,
                "size": 1024,
                "format": "sRGB",
                "file_ext": "png",
                "description": "Color Map - sRGB, 8-bit, max 1024px",
                "blender_socket": "Base Color",
                "roblox_slot": "ColorMap"
            },
            "normal": {
                "enabled": False,
                "size": 1024,
                "format": "linear_tangent",
                "file_ext": "png",
                "description": "Normal Map - Tangent space, max 1024px",
                "blender_socket": "Normal",
                "roblox_slot": "NormalMap"
            },
            "roughness": {
                "enabled": False,
                "size": 1024,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Roughness Map - Linear grayscale, max 1024px",
                "blender_socket": "Roughness",
                "roblox_slot": "RoughnessMap"
            },
            "metallic": {
                "enabled": False,
                "size": 1024,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Metalness Map - Linear grayscale, max 1024px",
                "blender_socket": "Metallic",
                "roblox_slot": "MetalnessMap"
            },
        },
        "material_shader": "SurfaceAppearance",
        "notes": "Roblox max texture size is 1024x1024. No emission or AO slots available."
    },

    "amazon_lumberyard": {
        "id": "amazon_lumberyard",
        "name": "Amazon Lumberyard / O3DE",
        "description": "Amazon's Lumberyard engine (now O3DE open-source)",
        "supported_maps": {
            "albedo": {
                "enabled": False,
                "size": 2048,
                "format": "sRGB",
                "file_ext": "tif",
                "description": "Diffuse / Base Color - sRGB",
                "blender_socket": "Base Color",
                "lumberyard_slot": "_diff"
            },
            "normal": {
                "enabled": False,
                "size": 2048,
                "format": "linear_tangent",
                "file_ext": "tif",
                "description": "Normal Map - Tangent space",
                "blender_socket": "Normal",
                "lumberyard_slot": "_ddn"
            },
            "roughness": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "tif",
                "description": "Roughness / Gloss",
                "blender_socket": "Roughness",
                "lumberyard_slot": "Roughness channel in _spec"
            },
            "metallic": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "tif",
                "description": "Metalness",
                "blender_socket": "Metallic",
                "lumberyard_slot": "Metalness channel in _spec"
            },
            "ao": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "tif",
                "description": "Ambient Occlusion",
                "blender_socket": "Ambient Occlusion",
                "lumberyard_slot": "_ao"
            },
            "emission": {
                "enabled": False,
                "size": 2048,
                "format": "sRGB",
                "file_ext": "tif",
                "description": "Emissive Map",
                "blender_socket": "Emission",
                "lumberyard_slot": "_em"
            },
        },
        "material_shader": "Standard PBR",
        "notes": "Lumberyard uses TIF format. O3DE accepts more formats."
    },

    "unreal": {
        "id": "unreal",
        "name": "Unreal Engine 5",
        "description": "Epic Games Unreal Engine 5 - Nanite, Lumen ready",
        "supported_maps": {
            "albedo": {
                "enabled": False,
                "size": 4096,
                "format": "sRGB",
                "file_ext": "png",
                "description": "Base Color - sRGB, up to 4096px",
                "blender_socket": "Base Color",
                "ue5_slot": "BaseColorTexture"
            },
            "normal": {
                "enabled": False,
                "size": 4096,
                "format": "linear_tangent",
                "file_ext": "png",
                "description": "Normal Map - Tangent space, DirectX style",
                "blender_socket": "Normal",
                "ue5_slot": "NormalTexture"
            },
            "roughness": {
                "enabled": False,
                "size": 4096,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Roughness - Packed in ORM (G channel)",
                "blender_socket": "Roughness",
                "ue5_slot": "ORM.G"
            },
            "metallic": {
                "enabled": False,
                "size": 4096,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Metallic - Packed in ORM (B channel)",
                "blender_socket": "Metallic",
                "ue5_slot": "ORM.B"
            },
            "ao": {
                "enabled": False,
                "size": 4096,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Ambient Occlusion - Packed in ORM (R channel)",
                "blender_socket": "Ambient Occlusion",
                "ue5_slot": "ORM.R"
            },
            "emission": {
                "enabled": False,
                "size": 2048,
                "format": "sRGB",
                "file_ext": "exr",
                "description": "Emissive - HDR recommended for Lumen",
                "blender_socket": "Emission",
                "ue5_slot": "EmissiveColorTexture"
            },
            "displacement": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "exr",
                "description": "Displacement - for Nanite tessellation",
                "blender_socket": "Height",
                "ue5_slot": "DisplacementMap"
            },
        },
        "material_shader": "M_Master_PBR",
        "notes": "UE5 packs Occlusion-Roughness-Metallic into one ORM texture"
    },

    "custom": {
        "id": "custom",
        "name": "Custom Preset",
        "description": "User-defined engine settings - configure as needed",
        "supported_maps": {
            "albedo": {
                "enabled": False,
                "size": 2048,
                "format": "sRGB",
                "file_ext": "png",
                "description": "Albedo / Base Color",
                "blender_socket": "Base Color",
            },
            "normal": {
                "enabled": False,
                "size": 2048,
                "format": "linear_tangent",
                "file_ext": "png",
                "description": "Normal Map - Tangent space",
                "blender_socket": "Normal",
            },
            "roughness": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Roughness",
                "blender_socket": "Roughness",
            },
            "metallic": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Metallic",
                "blender_socket": "Metallic",
            },
            "ao": {
                "enabled": False,
                "size": 2048,
                "format": "linear_grayscale",
                "file_ext": "png",
                "description": "Ambient Occlusion",
                "blender_socket": "Ambient Occlusion",
            },
            "emission": {
                "enabled": False,
                "size": 2048,
                "format": "sRGB",
                "file_ext": "exr",
                "description": "Emission / Glow",
                "blender_socket": "Emission",
            },
            "height": {
                "enabled": False,
                "size": 1024,
                "format": "linear_grayscale",
                "file_ext": "exr",
                "description": "Height / Displacement",
                "blender_socket": "Height",
            },
        },
        "material_shader": "Principled BSDF",
        "notes": "Fully configurable - adjust sizes, formats, and maps as needed"
    },
}

# ─── Engine List (for UI dropdown) ────────────────────────────────────────────

ENGINE_ITEMS = [
    ("unity", "Unity", "Unity Standard / URP / HDRP"),
    ("roblox", "Roblox", "Roblox Studio"),
    ("amazon_lumberyard", "Amazon Lumberyard", "Amazon Lumberyard / O3DE"),
    ("unreal", "Unreal Engine 5", "Unreal Engine 5 (Nanite / Lumen)"),
    ("custom", "Custom", "User-defined settings"),
]

# ─── Texture Sizes (for UI dropdowns) ─────────────────────────────────────────

TEXTURE_SIZE_ITEMS = [
    ("256", "256 px", ""),
    ("512", "512 px", ""),
    ("1024", "1024 px", ""),
    ("2048", "2048 px (Recommended)", ""),
    ("4096", "4096 px", ""),
    ("8192", "8192 px (Ultra)", ""),
]

# ─── Map Format Items ─────────────────────────────────────────────────────────

MAP_FORMAT_ITEMS = [
    ("sRGB", "sRGB (Color maps)", "For albedo, emission - perceptual color space"),
    ("linear_tangent", "Linear Tangent (Normal maps)", "For tangent-space normal maps"),
    ("linear_grayscale", "Linear Grayscale (Data maps)", "For roughness, metallic, AO, displacement"),
]

# ─── File Extension Items ─────────────────────────────────────────────────────

FILE_EXT_ITEMS = [
    ("png", "PNG", "Lossless, 8-bit"),
    ("exr", "EXR", "HDR, 16/32-bit float, best quality"),
    ("tif", "TIF/TIFF", "Lossless, wide compatibility"),
    ("jpg", "JPG", "Lossy compression, smallest file size"),
    ("tga", "TGA", "Lossless, some engine compatibility"),
]
