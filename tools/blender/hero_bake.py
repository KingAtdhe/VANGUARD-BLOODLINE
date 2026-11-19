"""High -> low texture baking for sculpted fighters (studio pipeline).

The SDF layers are polygonized twice: a dense HIGH sculpt (~1.5 mm) and the
decimated, skinned GAME mesh (hero_builder). The high sculpt gets material
detail too fine for geometry — fabric weave, leather grain, skin pores, metal
wear — and Cycles bakes everything onto the game mesh's UV atlas:

  * tangent-space NORMAL map (sculpt + micro detail)
  * base COLOUR (paint + material variation)
  * AMBIENT OCCLUSION (multiplied into the colour)

The game mesh then renders with PBR materials (albedo + normal map) on the
Mobile renderer. No base meshes, no external textures: all procedural.
"""

import math

import bpy
import numpy as np

# micro detail per layer: (kind, bump strength, bump scale)
DETAIL = {
    "Body": "skin", "Eyes": "eye", "Top": "knit", "Origin": "glow", "Trousers": "twill",
    "KneeGuards": "metal", "Boots": "leather", "Gloves": "leather", "Belt": "leather",
    "Sash": "linen", "Hair": "hair",
}


def _node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def high_material(name, kind):
    """Procedural surface used only as the bake source."""
    m = bpy.data.materials.new(f"HIGH_{name}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bs.outputs[0], out.inputs["Surface"])
    col = nt.nodes.new("ShaderNodeVertexColor")
    col.layer_name = "Col"
    coord = nt.nodes.new("ShaderNodeTexCoord")
    height = None
    tint = None
    if kind == "skin":
        pores = _node(nt, "ShaderNodeTexNoise", Scale=2600.0, Detail=2.0, Roughness=0.6)
        blot = _node(nt, "ShaderNodeTexNoise", Scale=60.0, Detail=4.0)
        nt.links.new(coord.outputs["Object"], pores.inputs["Vector"])
        nt.links.new(coord.outputs["Object"], blot.inputs["Vector"])
        height, hstr = pores.outputs["Fac"], 0.08
        tint = (blot.outputs["Fac"], (0.92, 0.86, 0.84), (1.04, 0.98, 0.95))
    elif kind == "knit":           # fine compression knit: ribs + noise
        wave = _node(nt, "ShaderNodeTexWave", Scale=950.0, Distortion=1.0, Detail=1.0)
        wave.wave_type, wave.bands_direction = "BANDS", "Z"
        nt.links.new(coord.outputs["Object"], wave.inputs["Vector"])
        height, hstr = wave.outputs["Fac"], 0.12
        blot = _node(nt, "ShaderNodeTexNoise", Scale=30.0, Detail=3.0)
        nt.links.new(coord.outputs["Object"], blot.inputs["Vector"])
        tint = (blot.outputs["Fac"], (0.85, 0.85, 0.88), (1.15, 1.15, 1.18))
    elif kind in ("twill", "linen"):
        a = _node(nt, "ShaderNodeTexWave", Scale=700.0 if kind == "twill" else 500.0, Distortion=0.5)
        a.wave_type, a.bands_direction = "BANDS", "DIAGONAL" if kind == "twill" else "X"
        b = _node(nt, "ShaderNodeTexWave", Scale=700.0 if kind == "twill" else 500.0, Distortion=0.5)
        b.wave_type, b.bands_direction = "BANDS", "Z"
        nt.links.new(coord.outputs["Object"], a.inputs["Vector"])
        nt.links.new(coord.outputs["Object"], b.inputs["Vector"])
        mix = _node(nt, "ShaderNodeMath")
        mix.operation = "MULTIPLY"
        nt.links.new(a.outputs["Fac"], mix.inputs[0])
        nt.links.new(b.outputs["Fac"], mix.inputs[1])
        height, hstr = mix.outputs[0], 0.15
        blot = _node(nt, "ShaderNodeTexNoise", Scale=12.0, Detail=5.0)     # wear / dust
        nt.links.new(coord.outputs["Object"], blot.inputs["Vector"])
        tint = (blot.outputs["Fac"], (0.8, 0.8, 0.82), (1.25, 1.22, 1.2))
    elif kind == "leather":
        vor = _node(nt, "ShaderNodeTexVoronoi", Scale=900.0)
        nt.links.new(coord.outputs["Object"], vor.inputs["Vector"])
        height, hstr = vor.outputs["Distance"], 0.1
        blot = _node(nt, "ShaderNodeTexNoise", Scale=25.0, Detail=4.0)
        nt.links.new(coord.outputs["Object"], blot.inputs["Vector"])
        tint = (blot.outputs["Fac"], (0.8, 0.8, 0.8), (1.35, 1.3, 1.28))
    elif kind == "metal":
        sc = _node(nt, "ShaderNodeTexNoise", Scale=400.0, Detail=8.0, Roughness=0.8)
        sc.noise_dimensions = "3D"
        nt.links.new(coord.outputs["Object"], sc.inputs["Vector"])
        height, hstr = sc.outputs["Fac"], 0.04
        tint = (sc.outputs["Fac"], (0.85, 0.85, 0.88), (1.15, 1.15, 1.15))
    elif kind == "hair":            # strand grooves along the clumps (approximate)
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0, 1.0, 0.08)
        nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
        st = _node(nt, "ShaderNodeTexNoise", Scale=1400.0, Detail=1.0)
        nt.links.new(mp.outputs[0], st.inputs["Vector"])
        height, hstr = st.outputs["Fac"], 0.2
        tint = (st.outputs["Fac"], (0.7, 0.7, 0.75), (1.6, 1.6, 1.7))
    color_out = col.outputs["Color"]
    if tint is not None:
        ramp_in, lo, hi = tint
        mixc = nt.nodes.new("ShaderNodeMix")
        mixc.data_type = "RGBA"
        nt.links.new(ramp_in, mixc.inputs["Factor"])
        mixc.inputs[6].default_value = (*lo, 1)
        mixc.inputs[7].default_value = (*hi, 1)
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(col.outputs["Color"], mul.inputs[6])
        nt.links.new(mixc.outputs[2], mul.inputs[7])
        color_out = mul.outputs[2]
    nt.links.new(color_out, bs.inputs["Base Color"])
    if height is not None:
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = hstr
        bump.inputs["Distance"].default_value = 0.0004
        nt.links.new(height, bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
    return m


def high_object(layer, voxel_scale=0.5, min_voxel=0.0012):
    V, F = layer.polygonize(max(layer.voxel * voxel_scale, min_voxel))
    C = layer.colors(V)
    me = bpy.data.meshes.new(f"HIGH_{layer.name}")
    me.from_pydata(V.tolist(), [], F.tolist())
    me.polygons.foreach_set("use_smooth", np.ones(len(F), bool))
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    rgba = np.ones((len(V), 4))
    rgba[:, :3] = C
    ca.data.foreach_set("color", rgba.ravel())
    me.materials.append(high_material(layer.name, DETAIL.get(layer.name, "none")))
    ob = bpy.data.objects.new(f"HIGH_{layer.name}", me)
    bpy.context.scene.collection.objects.link(ob)
    print(f"[bake] high {layer.name}: {len(F)} tris", flush=True)
    return ob


def bake_maps(low, highs, size=2048, samples=24, out_prefix="/tmp/kairo"):
    """UV-unwrap the game mesh and bake normal / colour / AO from the highs."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    bpy.context.view_layer.objects.active = low
    for o in bpy.context.view_layer.objects:
        o.select_set(o == low)
    low.data.uv_layers.new(name="UV")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003, area_weight=0.0)
    bpy.ops.uv.pack_islands(margin=0.002, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    # One game-mesh piece per layer, each baked ONLY from its own sculpt layer
    # (otherwise the shirt would pick up the skin 4 mm underneath it).
    lay = np.zeros(len(low.data.polygons), np.int32)
    low.data.attributes["layer"].data.foreach_get("value", lay)
    pieces = []
    for li, hi in enumerate(highs):
        if not (lay == li).any():
            continue
        piece = low.copy()
        piece.data = low.data.copy()
        piece.modifiers.clear()
        piece.parent = None
        piece.matrix_world = low.matrix_world.copy()
        bpy.context.scene.collection.objects.link(piece)
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(piece.data)
        la = bm.faces.layers.int.get("layer")
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[la] != li], context="FACES")
        bm.to_mesh(piece.data)
        bm.free()
        pieces.append((piece, hi))
    imgs = {}
    covered = None
    for kind in ("NORMAL", "DIFFUSE", "AO"):
        img = bpy.data.images.new(f"bake_{kind}", size, size, alpha=True, float_buffer=False)
        img.pixels[:] = np.zeros(size * size * 4)
        if kind == "NORMAL":
            img.colorspace_settings.name = "Non-Color"
        imgs[kind] = img
        for piece, hi in pieces:
            for m in piece.data.materials:
                nt = m.node_tree
                for n in [n for n in nt.nodes if n.name == "BAKE_TARGET"]:
                    nt.nodes.remove(n)
                t = nt.nodes.new("ShaderNodeTexImage")
                t.name = "BAKE_TARGET"
                t.image = img
                nt.nodes.active = t
            for o in bpy.context.view_layer.objects:
                o.select_set(o == hi or o == piece)
            bpy.context.view_layer.objects.active = piece
            bk = sc.render.bake
            bk.use_selected_to_active = True
            bk.use_cage = False
            bk.cage_extrusion = 0.006
            bk.max_ray_distance = 0.02
            bk.margin = 0
            bk.use_clear = False
            bk.target = "IMAGE_TEXTURES"
            if kind == "DIFFUSE":
                bk.use_pass_direct = bk.use_pass_indirect = False
                bk.use_pass_color = True
            sc.cycles.samples = 1 if kind != "AO" else samples
            bpy.ops.object.bake(type=kind)
        # fill the gaps between islands from the nearest baked texel (seam padding)
        from scipy import ndimage as ndi
        px = np.array(img.pixels[:]).reshape(size, size, 4)
        if covered is None:
            covered = px[..., 3] > 0.5
        _d, (iy, ix) = ndi.distance_transform_edt(~covered, return_indices=True)
        px = px[iy, ix]
        px[..., 3] = 1.0
        img.pixels[:] = px.ravel()
        img.filepath_raw = f"{out_prefix}_{kind.lower()}.png"
        img.file_format = "PNG"
        img.save()
        print(f"[bake] {kind} done", flush=True)
    for piece, _hi in pieces:
        bpy.data.objects.remove(piece)
    # albedo = colour x softened AO
    px = np.array(imgs["DIFFUSE"].pixels[:]).reshape(size, size, 4)
    ao = np.array(imgs["AO"].pixels[:]).reshape(size, size, 4)[..., :1]
    px[..., :3] *= 0.35 + 0.65 * ao
    alb = bpy.data.images.new("albedo", size, size, alpha=False)
    alb.pixels[:] = px.ravel()
    alb.filepath_raw = f"{out_prefix}_albedo.png"
    alb.file_format = "PNG"
    alb.save()
    return alb, imgs["NORMAL"]


PBR = {"Skin": (0.5, 0.0), "Cloth": (0.75, 0.0), "Cloth2": (0.85, 0.0), "Accent": (0.4, 0.0),
       "Hair": (0.45, 0.0), "Gear": (0.38, 0.75)}


def game_materials(low, albedo, normal, accent_rgb):
    """Rebuild the slot materials as textured PBR (albedo + normal map)."""
    for m in low.data.materials:
        slot = m.name.split("_")[-1]
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bs.outputs[0], out.inputs["Surface"])
        ta = nt.nodes.new("ShaderNodeTexImage")
        ta.image = albedo
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = normal
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(ta.outputs["Color"], bs.inputs["Base Color"])
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
        r, mt = PBR.get(slot, (0.6, 0.0))
        bs.inputs["Roughness"].default_value = r
        bs.inputs["Metallic"].default_value = mt
        if slot == "Accent":
            bs.inputs["Emission Color"].default_value = (*accent_rgb, 1)
            bs.inputs["Emission Strength"].default_value = 3.0
