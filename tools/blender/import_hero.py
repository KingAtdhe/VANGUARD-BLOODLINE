"""Puts an owner-supplied hero model into the game without changing its look.

    python tools/blender/import_hero.py --src <model.glb> --fighter kairo \
        --moves /tmp/kairo_moves.json --out assets/characters [--tris 40000] [--tex 2048]

The source (e.g. an image-to-3D export: millions of triangles, 4K PBR maps,
no skeleton) is kept as it is in assets/characters/<id>/source/. The game
version is made from it:

1. scaled to the fighter's height, feet on the ground, facing -Y;
2. reduced to a phone budget (decimate, UVs kept) — the shape stays;
3. its base colour and roughness/metal maps reused (downsized only), and a
   new normal map baked from the full-detail source onto the reduced mesh,
   so the surface detail of the original carries over;
4. the Origin-red parts (detected from the base colour) get a second
   material "<ID>_Accent" with the same textures, used only to tell P2
   apart in mirror matches;
5. bound to the shared fighter skeleton, with joints placed on this model
   (heat-map weights, max 4 bones per vertex) and given all game animations
   from character_builder (timing from the real move data).
"""
import argparse
import json
import math
import os
import sys

import bpy
import bmesh  # noqa: E402
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import character_builder as cb  # noqa: E402


def joints_from_mesh(co, height):
    """Joint positions measured on the model (left side; right is mirrored).
    Cross-sections give the centre of each limb at the joint heights."""
    def centre(z, xmin, xmax=9.0, tol=0.015):
        m = (np.abs(co[:, 2] - z) < tol) & (co[:, 0] > xmin) & (co[:, 0] < xmax)
        return co[m].mean(0) if m.sum() > 50 else None

    k = height / 1.8
    wrist = centre(0.93 * k, 0.31 * k)
    elbow = centre(1.12 * k, 0.27 * k)
    shoulder = centre(1.40 * k, 0.20 * k, 0.34 * k)
    knee = centre(0.53 * k, 0.12 * k)
    ankle = centre(0.10 * k, 0.12 * k)
    J = {}
    J["shoulder"] = Vector((shoulder[0] - 0.04 * k, shoulder[1] + 0.02, 1.40 * k)) if shoulder is not None \
        else Vector((0.235 * k, 0, 1.42 * k))
    J["elbow"] = Vector(elbow) if elbow is not None else Vector((0.27 * k, 0.04, 1.14 * k))
    J["wrist"] = Vector(wrist) if wrist is not None else Vector((0.285 * k, -0.02, 0.88 * k))
    J["hand_tip"] = J["wrist"] + (J["wrist"] - J["elbow"]).normalized() * 0.11 * k
    J["hip"] = Vector((0.11 * k, -0.02, 0.98 * k))
    J["knee"] = Vector(knee) if knee is not None else Vector((0.115 * k, -0.04, 0.54 * k))
    J["ankle"] = Vector(ankle) if ankle is not None else Vector((0.115 * k, 0, 0.09 * k))
    J["ankle"].z = 0.09 * k
    J["toe"] = Vector((J["ankle"].x + 0.01, J["ankle"].y - 0.17 * k, 0.03 * k))
    return J


def skeleton_for(J, height):
    k = height / 1.8
    B = {
        "Root": ((0, 0, 0), (0, 0, 0.15 * k), None, False),
        "Hips": ((0, -0.02, 1.0 * k), (0, -0.02, 1.12 * k), "Root", False),
        "Spine": ((0, -0.02, 1.12 * k), (0, -0.02, 1.28 * k), "Hips", True),
        "Chest": ((0, -0.02, 1.28 * k), (0, -0.02, 1.45 * k), "Spine", True),
        "Neck": ((0, -0.03, 1.45 * k), (0, -0.04, 1.56 * k), "Chest", True),
        "Head": ((0, -0.04, 1.56 * k), (0, -0.04, 1.8 * k), "Neck", True),
    }
    for side, s in (("Left", 1), ("Right", -1)):
        def m(v):
            return (v.x * s, v.y, v.z)
        B[f"{side}UpperArm"] = (m(J["shoulder"]), m(J["elbow"]), "Chest", False)
        B[f"{side}LowerArm"] = (m(J["elbow"]), m(J["wrist"]), f"{side}UpperArm", True)
        B[f"{side}Hand"] = (m(J["wrist"]), m(J["hand_tip"]), f"{side}LowerArm", True)
        B[f"{side}UpperLeg"] = (m(J["hip"]), m(J["knee"]), "Hips", False)
        B[f"{side}LowerLeg"] = (m(J["knee"]), m(J["ankle"]), f"{side}UpperLeg", True)
        B[f"{side}Foot"] = (m(J["ankle"]), m(J["toe"]), f"{side}LowerLeg", True)
    # keep the builder's bone order (animations and Godot bone indices)
    return {n: B[n] for n in cb.skeleton(cb.FIGHTERS["kairo"]).keys()}


def uv_islands(obj):
    """Texture piece (UV island) of every vertex: faces joined across edges
    whose two sides have the same UVs. None if the mesh has no UVs."""
    me = obj.data
    if not me.uv_layers:
        return None
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.active
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        def uvs(f):
            d = {}
            for l in f.loops:
                d[l.vert.index] = tuple(round(c, 5) for c in l[uv].uv)
            return d
        a_, b_ = uvs(f1), uvs(f2)
        if all(a_[v.index] == b_[v.index] for v in e.verts):
            ra, rb = find(f1.index), find(f2.index)
            if ra != rb:
                parent[ra] = rb
    isl = np.zeros(len(bm.verts), dtype=np.int64)
    for f in bm.faces:
        r = find(f.index)
        for v in f.verts:
            isl[v.index] = r
    bm.free()
    return isl


def skin_weights(obj, B, height, hand_reach=0.12, sleeve_reach=0.24, by_island=False):
    """Bone weights for a mesh that heat weighting can't solve (scanned or
    generated meshes are rarely watertight). Each vertex is weighted by its
    distance to every bone segment, restricted by body region (left/right,
    arms only outside the torso, legs only below the waist; cloth further than
    [param hand_reach] (x height/1.8 m) from the hand hangs from the hips — raise
    it for long sleeves that hang past the hands), then smoothed
    over the surface so joints bend softly. Max 4 bones per vertex."""
    k = height / 1.8
    names = list(B.keys())
    co = np.array([v.co for v in obj.data.vertices])
    n = len(co)
    W = np.zeros((n, len(names)))
    radius = {"Hips": 0.13, "Spine": 0.13, "Chest": 0.14, "Neck": 0.06, "Head": 0.1, "Root": 0.05}
    # distance to the body's centre line (hips -> neck), to tell arm from torso
    axis_d = np.full(n, 9.0)
    for nm in ("Hips", "Spine", "Chest", "Neck"):
        h, t = np.array(B[nm][0], float), np.array(B[nm][1], float)
        seg = t - h
        tt = np.clip(((co - h) @ seg) / max(1e-9, seg @ seg), 0, 1)
        axis_d = np.minimum(axis_d, np.linalg.norm(co - (h + tt[:, None] * seg), axis=1))
    # ... and to the legs (cloth hanging against a thigh is not arm)
    legs_d = np.full(n, 9.0)
    for nm in names:
        if "UpperLeg" in nm or "LowerLeg" in nm:
            h, t = np.array(B[nm][0], float), np.array(B[nm][1], float)
            seg = t - h
            tt = np.clip(((co - h) @ seg) / max(1e-9, seg @ seg), 0, 1)
            legs_d = np.minimum(legs_d, np.linalg.norm(co - (h + tt[:, None] * seg), axis=1))
    for j, nm in enumerate(names):
        h, t = np.array(B[nm][0], float), np.array(B[nm][1], float)
        seg = t - h
        tt = np.clip(((co - h) @ seg) / max(1e-9, seg @ seg), 0, 1)
        d = np.linalg.norm(co - (h + tt[:, None] * seg), axis=1)
        r = radius.get(nm, 0.05 if "Arm" in nm or "Hand" in nm else 0.07) * k
        w = 1.0 / np.maximum(d - r * 0.6, 0.01 * k) ** 4
        x, z = co[:, 0], co[:, 2]
        side = 1 if nm.startswith("Left") else (-1 if nm.startswith("Right") else 0)
        if side:
            w *= (x * side > -0.01 * k)
        if "Arm" in nm or "Hand" in nm:
            # A point is arm if it is closer to the arm bone than to the body's
            # centre line and to the legs (arms that hang close to the body
            # keep their inner side; a sash against the thigh stays put). Cloth hanging beside a fist (a sash) must not follow the
            # hand; wide sleeves around the middle of the arm do.
            if "Hand" in nm:
                reach = np.full(n, hand_reach * k)
            else:
                reach = np.where((tt > 0.04) & (tt < 0.97), sleeve_reach * k, min(0.12, sleeve_reach) * k)
            w *= (d < axis_d) & (d < legs_d) & (d < reach)
        if "Leg" in nm or "Foot" in nm:
            w *= (z < 1.05 * k) & (np.abs(x) < 0.5 * k)
        if nm == "Head":
            w *= (z > 1.5 * k)
        if nm == "Root":
            w *= 0.0
        if nm in ("Hips", "Spine", "Chest", "Neck"):
            arm_zone = (np.abs(x) > 0.24 * k) & (z > 0.75 * k) & (z < 1.3 * k)
            w *= ~arm_zone
        W[:, j] = w
    allowed = W > 0                             # which bones may move each vertex
    # Decide arm membership per texture piece (UV island), not per vertex:
    # a glove and a sash that touch at rest are separate pieces of the
    # texture layout, so each piece moves as one — with the arm only if most
    # of it lies in the arm region.
    isl = uv_islands(obj) if by_island else None
    if isl is not None:
        arm_cols_i = [j for j, nm in enumerate(names) if "Arm" in nm or "Hand" in nm]
        arm_any = allowed[:, arm_cols_i].any(1)
        for i in np.unique(isl):
            m = isl == i
            frac = arm_any[m].mean()
            if frac < 0.5:
                W[np.ix_(m, arm_cols_i)] = 0.0          # mostly not arm: the whole piece stays off the arm
                allowed[np.ix_(m, arm_cols_i)] = False
            elif frac < 1.0:
                # mostly arm: let the rest of the piece follow its arm bones too
                for j in arm_cols_i:
                    if allowed[m, j].any():
                        miss = m & ~allowed[:, j] & (W.sum(1) >= 0)
                        h, t = np.array(B[names[j]][0], float), np.array(B[names[j]][1], float)
                        seg = t - h
                        tt = np.clip(((co[miss] - h) @ seg) / max(1e-9, seg @ seg), 0, 1)
                        dd = np.linalg.norm(co[miss] - (h + tt[:, None] * seg), axis=1)
                        W[miss, j] = 1.0 / np.maximum(dd - 0.03 * k, 0.01 * k) ** 4
                        allowed[miss, j] = True
    orphan = W.sum(1) == 0                      # nothing allowed: hang it from the hips
    W[orphan, names.index("Hips")] = 1.0
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    # Loose cloth (the sash, coat tails) flares away from the legs: let it hang
    # from the hips instead of being dragged along by a kicking leg.
    hips = names.index("Hips")
    leg_d = np.full(n, 9.0)
    for nm in names:
        if "UpperLeg" in nm or "LowerLeg" in nm:
            h, t = np.array(B[nm][0], float), np.array(B[nm][1], float)
            seg = t - h
            tt = np.clip(((co - h) @ seg) / max(1e-9, seg @ seg), 0, 1)
            leg_d = np.minimum(leg_d, np.linalg.norm(co - (h + tt[:, None] * seg), axis=1))
    cloth = np.clip((leg_d - 0.11 * k) / (0.08 * k), 0, 1) * (co[:, 2] < 1.05 * k) * (co[:, 2] > 0.2 * k)
    cloth *= (np.abs(co[:, 0]) < 0.45 * k)
    arm_rows = np.array(["Arm" in nm or "Hand" in nm for nm in names])
    cloth *= W[:, arm_rows].sum(1) < 0.5
    hip_row = np.zeros(len(names))
    hip_row[hips] = 1.0
    W = W * (1 - 0.75 * cloth[:, None]) + hip_row[None, :] * (0.75 * cloth[:, None])
    # smooth over the surface (edge neighbours)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    e = np.array([(ed.verts[0].index, ed.verts[1].index) for ed in bm.edges])
    bm.free()
    deg = np.bincount(e.ravel(), minlength=n).astype(float)
    for _ in range(6):
        acc = np.zeros_like(W)
        np.add.at(acc, e[:, 0], W[e[:, 1]])
        np.add.at(acc, e[:, 1], W[e[:, 0]])
        W = 0.5 * W + 0.5 * acc / np.maximum(deg, 1)[:, None]
    # Smoothing softens joints but must not carry an arm onto cloth it may not
    # move (a sash joined to the glove after mesh repair would lift with it).
    arm_cols = np.array(["Arm" in nm or "Hand" in nm for nm in names])
    W[:, arm_cols] *= allowed[:, arm_cols]
    empty = W.sum(1) <= 1e-9
    W[empty, names.index("Hips")] = 1.0
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    # Forearm and hand belong to the arm or to the body, never half and half:
    # a glove smoothed together with the coat it touches would otherwise sit
    # half on the moving hand and half on the still hips and stretch into
    # strips. (Elbow and shoulder still blend: upper arm <-> chest is kept.)
    fore = np.array([("LowerArm" in nm or "Hand" in nm) for nm in names])
    upper = np.array([("UpperArm" in nm) for nm in names])
    touched = W[:, fore].sum(1) > 1e-6
    arm_share = W[:, fore | upper].sum(1)
    to_arm = touched & (arm_share >= 0.5)
    to_body = touched & ~to_arm
    W[np.ix_(to_arm, ~(fore | upper))] = 0.0
    W[np.ix_(to_body, fore)] = 0.0
    empty = W.sum(1) <= 1e-9
    W[empty, names.index("Hips")] = 1.0
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    top = np.argsort(-W, axis=1)[:, :4]
    keep = np.zeros_like(W, dtype=bool)
    np.put_along_axis(keep, top, True, axis=1)
    W = np.where(keep & (W > 0.02), W, 0.0)
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    # Rigid mid-limbs: a vertex almost wholly on one bone moves with that bone
    # only, so blending stays at the joints (no rubbery forearms or skull).
    dom = W.max(1) > 0.85
    W[dom] = (W[dom] == W[dom].max(1, keepdims=True)).astype(float)
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    for g in list(obj.vertex_groups):
        obj.vertex_groups.remove(g)
    groups = [obj.vertex_groups.new(name=nm) for nm in names]
    for j in range(len(names)):
        idx = np.nonzero(W[:, j])[0]
        for vi in idx:
            groups[j].add([int(vi)], float(W[vi, j]), "REPLACE")
    return int((W.sum(1) == 0).sum())


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--fighter", default="kairo")
    ap.add_argument("--moves", required=True)
    ap.add_argument("--out", default="assets/characters")
    ap.add_argument("--tris", type=int, default=40000)
    ap.add_argument("--tex", type=int, default=2048)
    ap.add_argument("--bake-samples", type=int, default=4)
    a = ap.parse_args(argv)
    fid = a.fighter
    cfg = cb.FIGHTERS[fid]
    H = cfg["height"]
    out_dir = os.path.join(a.out, fid)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = cb.FPS
    bpy.ops.import_scene.gltf(filepath=a.src)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    for o in bpy.data.objects:
        o.select_set(o in meshes)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    high = bpy.context.view_layer.objects.active
    for o in [o for o in bpy.data.objects if o.type != "MESH"]:
        bpy.data.objects.remove(o)
    high.parent = None
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    co = np.zeros(len(high.data.vertices) * 3)
    high.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    s = H / (co[:, 2].max() - co[:, 2].min())
    high.data.transform(Matrix.Translation((0, 0, -co[:, 2].min() * s)) @ Matrix.Scale(s, 4))
    high.data.update()
    co = co * s
    co[:, 2] -= co[:, 2].min()
    print(f"[import] source tris={sum(len(p.vertices) - 2 for p in high.data.polygons)} scale={s:.3f}")
    # inspection + minimal repair before anything else (CLAUDE.md, D-057)
    import mesh_check
    pre = mesh_check.inspect(high)
    print("[check] before", {k: pre[k] for k in ("verts", "parts", "duplicate_verts", "overlapping_faces",
                                                 "nonmanifold_edges", "inconsistent_winding_edges")})
    print("[check] fixed ", mesh_check.repair(high))

    # 2. reduced copy for the phone
    low = high.copy()
    low.data = high.data.copy()
    low.name = f"{fid.upper()}_Body"
    sc.collection.objects.link(low)
    src_tris = sum(len(p.vertices) - 2 for p in high.data.polygons)
    dec = low.modifiers.new("dec", "DECIMATE")
    dec.ratio = min(1.0, a.tris / src_tris)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.modifier_apply(modifier="dec")
    low_tris = sum(len(p.vertices) - 2 for p in low.data.polygons)
    print(f"[import] game tris={low_tris}")

    # 3. textures: reuse colour + roughness/metal (downsized), bake a new normal map
    src_mat = high.data.materials[0]
    imgs = {n.label or n.image.name: n.image for n in src_mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image}
    def find(key):
        for nm, im in imgs.items():
            if key in nm.lower():
                return im
        return None
    base_im, rm_im = find("basecolor") or find("color"), find("rm") or find("rough")
    os.makedirs(out_dir, exist_ok=True)
    def save_resized(im, name):
        im2 = im.copy()
        im2.scale(a.tex, a.tex)
        path = os.path.abspath(os.path.join(out_dir, name))
        im2.filepath_raw = path
        im2.file_format = "JPEG" if name.endswith(".jpg") else "PNG"
        im2.save()
        if name.endswith(".jpg"):
            # Blender can carry over the source's ICC profile, which Godot's
            # JPEG decoder rejects: re-encode as a plain baseline JPEG.
            from PIL import Image
            Image.open(path).convert("RGB").save(path, quality=92)
        return bpy.data.images.load(path, check_existing=False)
    base_small = save_resized(base_im, f"{fid}_basecolor.jpg")
    rm_small = save_resized(rm_im, f"{fid}_rm.jpg") if rm_im is not None else None

    nrm = bpy.data.images.new(f"{fid}_normal", a.tex, a.tex, alpha=False)
    nrm.colorspace_settings.name = "Non-Color"
    bake_mat = bpy.data.materials.new("bake_target")
    bake_mat.use_nodes = True
    tn = bake_mat.node_tree.nodes.new("ShaderNodeTexImage")
    tn.image = nrm
    bake_mat.node_tree.nodes.active = tn
    low.data.materials.clear()
    low.data.materials.append(bake_mat)
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = a.bake_samples
    for o in bpy.data.objects:
        o.select_set(False)
    high.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True, cage_extrusion=0.02 * H / 1.8,
                        max_ray_distance=0.06 * H / 1.8, margin=16)
    nrm_path = os.path.abspath(os.path.join(out_dir, f"{fid}_normal.png"))
    nrm.filepath_raw = nrm_path
    nrm.file_format = "PNG"
    nrm.save()
    print("[import] normal map baked")
    bpy.data.objects.remove(high)

    # game materials: body + accent (same maps; accent only recoloured for P2 in mirror matches)
    def game_mat(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = base_small
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        if rm_small is not None:
            r = nt.nodes.new("ShaderNodeTexImage")
            r.image = rm_small
            r.image.colorspace_settings.name = "Non-Color"
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(r.outputs["Color"], sep.inputs["Color"])
            nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
            nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
        nimg = nt.nodes.new("ShaderNodeTexImage")
        nimg.image = bpy.data.images.load(nrm_path, check_existing=True)
        nimg.image.colorspace_settings.name = "Non-Color"
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(nimg.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
        return m
    low.data.materials.clear()
    low.data.materials.append(game_mat(f"{fid.upper()}_Body"))
    low.data.materials.append(game_mat(f"{fid.upper()}_Accent"))
    # 4. Origin-red faces -> accent slot
    px = np.array(base_small.pixels[:], dtype=np.float32).reshape(a.tex, a.tex, 4)
    uvl = low.data.uv_layers.active.data
    n_acc = 0
    for p in low.data.polygons:
        u = sum(uvl[li].uv[0] for li in p.loop_indices) / p.loop_total
        v = sum(uvl[li].uv[1] for li in p.loop_indices) / p.loop_total
        c = px[min(a.tex - 1, max(0, int(v * a.tex))), min(a.tex - 1, max(0, int(u * a.tex)))]
        if c[0] > 0.25 and c[0] > 2.2 * c[1] and c[0] > 2.2 * c[2]:
            p.material_index = 1
            n_acc += 1
        else:
            p.material_index = 0
    print(f"[import] accent faces={n_acc}")
    for p in low.data.polygons:
        p.use_smooth = True

    # 5. skeleton fitted to this model, heat weights, animations
    J = joints_from_mesh(co, H)
    B = skeleton_for(J, H)
    arm_data = bpy.data.armatures.new(f"{fid.upper()}_Skeleton")
    arm_obj = bpy.data.objects.new(f"{fid.upper()}_Rig", arm_data)
    sc.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent, connect) in B.items():
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail, eb.roll = head, tail, 0.0
        if parent:
            eb.parent = arm_data.edit_bones[parent]
            eb.use_connect = connect
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in bpy.data.objects:
        o.select_set(False)
    low.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type="ARMATURE_NAME")
    unweighted = skin_weights(low, B, H)
    print(f"[import] skinned: unweighted verts={unweighted}")

    moves = json.loads(open(a.moves).read())
    arm_obj.animation_data_create()
    targets = cb.setup_ik(arm_obj)
    actions = cb.build_actions(moves, H / cb.REF_HEIGHT, fid)
    for name, keys in actions.items():
        cb.key_action(arm_obj, targets, name, keys)
    for pb in arm_obj.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    for empty, _c in targets.values():
        bpy.data.objects.remove(empty)
    arm_obj.animation_data.action = bpy.data.actions[f"{fid.upper()}_IDLE_A"]
    for pb in arm_obj.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    out_path = os.path.join(out_dir, f"{fid}.glb")
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True,
                              export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_step=1,
                              export_skins=True, export_def_bones=False, export_yup=True, export_apply=False,
                              export_materials="EXPORT", export_image_format="AUTO")
    print(f"[import] {fid}: tris={low_tris} actions={len(actions)} -> {out_path}")


if __name__ == "__main__":
    main()


def separate_fused(obj, min_jump=0.5):
    """Generated meshes sometimes fuse a hand to the coat beside it (faces
    joining glove and coat). Once weighted, those faces stretch into strips
    when the hand moves. Each face that straddles arm (forearm/hand weight
    >= min_jump) and body (no arm weight) gets its own copy of its vertices,
    weighted like the side most of the face belongs to. Nothing moves at
    rest; at most a hairline seam opens where the parts separate.
    Returns the number of faces separated."""
    me = obj.data
    names = {g.index: g.name for g in obj.vertex_groups}
    arm_idx = {i for i, nm in names.items() if "LowerArm" in nm or "Hand" in nm}
    bm = bmesh.new()
    bm.from_mesh(me)
    dl = bm.verts.layers.deform.active
    if dl is None:
        bm.free()
        return 0

    def arm_w(v):
        return sum(w for g, w in v[dl].items() if g in arm_idx)
    mixed = []
    for f in bm.faces:
        ws = [arm_w(v) for v in f.verts]
        if max(ws) >= min_jump and min(ws) < 1e-3:
            mixed.append((f, sum(w >= min_jump for w in ws) * 2 >= len(ws)))
    if not mixed:
        bm.free()
        return 0
    faces = [f for f, _ in mixed]
    side = {f: s for f, s in mixed}
    ret = bmesh.ops.split(bm, geom=faces, use_only_faces=True)
    new_faces = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)]
    # bmesh.ops.split keeps face order: pair new faces with the originals
    for f_old, f_new in zip(faces, new_faces):
        arm_side = side[f_old]
        donors = [v for v in f_new.verts if (arm_w(v) >= min_jump) == arm_side]
        if not donors:
            continue
        src = dict(donors[0][dl])
        for v in f_new.verts:
            if (arm_w(v) >= min_jump) != arm_side:
                d = v[dl]
                d.clear()
                for g, w in src.items():
                    d[g] = w
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(faces)
