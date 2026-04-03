"""
BlenderNanoBanana - Blender Mesh Operation Utilities
"""

from typing import Optional, List, Tuple, Dict


def get_active_mesh_data(context):
    """
    Extract mesh data from the active object.

    Returns dict with vertices, faces, normals, uv_coords, or None.
    """
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return None

    import bpy
    import bmesh

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    vertices = [[v.co.x, v.co.y, v.co.z] for v in bm.verts]
    faces = [[v.index for v in f.verts] for f in bm.faces]
    normals = [[v.normal.x, v.normal.y, v.normal.z] for v in bm.verts]

    # UV coordinates
    uv_layer = bm.loops.layers.uv.active
    uv_coords = []
    if uv_layer:
        for face in bm.faces:
            for loop in face.loops:
                uv = loop[uv_layer].uv
                uv_coords.append([uv.x, uv.y])

    seams = [[e.verts[0].index, e.verts[1].index] for e in bm.edges if e.seam]

    bm.free()

    return {
        "vertices": vertices,
        "faces": faces,
        "normals": normals,
        "uv_coords": uv_coords,
        "seams": seams,
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "object_name": obj.name,
    }


def apply_material_to_object(context, obj, material) -> bool:
    """Assign a material to an object's first material slot."""
    if obj is None or obj.type != "MESH":
        return False
    if len(obj.material_slots) == 0:
        obj.data.materials.append(material)
    else:
        obj.material_slots[0].material = material
    return True


def create_pbr_material(name: str, texture_paths: Dict[str, str]):
    """
    Create a Principled BSDF material and wire up texture maps.

    Args:
        name: Material name
        texture_paths: {"albedo": path, "normal": path, "roughness": path, ...}

    Returns:
        bpy.types.Material
    """
    import bpy

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    # Output
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (800, 0)

    # Principled BSDF
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    x_offset = -400

    # Socket name → (node_type, colorspace, bsdf_input, use_normal_map)
    MAP_CONFIG = {
        "albedo":    ("ShaderNodeTexImage", "sRGB", "Base Color", False),
        "normal":    ("ShaderNodeTexImage", "Non-Color", "Normal", True),
        "roughness": ("ShaderNodeTexImage", "Non-Color", "Roughness", False),
        "metallic":  ("ShaderNodeTexImage", "Non-Color", "Metallic", False),
        "ao":        ("ShaderNodeTexImage", "Non-Color", None, False),
        "emission":  ("ShaderNodeTexImage", "sRGB", "Emission Color", False),
        "height":    ("ShaderNodeTexImage", "Non-Color", None, False),
    }

    y_pos = 400
    for map_name, filepath in texture_paths.items():
        if not filepath or map_name not in MAP_CONFIG:
            continue

        node_type, colorspace, bsdf_socket, use_normal_map = MAP_CONFIG[map_name]

        tex_node = nodes.new(node_type)
        tex_node.location = (x_offset, y_pos)

        try:
            tex_node.image = bpy.data.images.load(filepath)
            tex_node.image.colorspace_settings.name = colorspace
        except Exception:
            pass

        if use_normal_map:
            # Add Normal Map node between texture and BSDF
            nmap = nodes.new("ShaderNodeNormalMap")
            nmap.location = (x_offset + 200, y_pos)
            links.new(tex_node.outputs["Color"], nmap.inputs["Color"])
            if bsdf_socket:
                links.new(nmap.outputs["Normal"], bsdf.inputs[bsdf_socket])
        elif bsdf_socket:
            links.new(tex_node.outputs["Color"], bsdf.inputs[bsdf_socket])

        y_pos -= 300

    return mat


def get_uv_island_ids(context) -> List[str]:
    """
    Return list of UV island IDs for the active mesh.
    Uses stored scene data or generates from UV analysis.
    """
    # Check scene cache first
    scene = context.scene
    props = getattr(scene, "nano_banana", None)
    if props is None:
        return []

    # For now return a placeholder — real detection done via Rust
    obj = context.active_object
    if obj and obj.type == "MESH":
        return [f"uv_{obj.name}_{i:03d}" for i in range(1)]
    return []
