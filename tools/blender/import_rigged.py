"""Puts an owner-supplied, already rigged character (Tripo / Mixamo-style
skeleton, one textured material) into the game without changing its look.

    python tools/blender/import_rigged.py --src <model.glb> --fighter ryuen \
        --moves /tmp/kairo_moves.json --out assets/characters

What happens to the model:

1. The pose the file displays is baked in as the rest shape. (Tripo stores
   some bind poses rotated; the shape you see in a viewer is the posed one.)
2. A display pedestal, if the export has one, is removed (cut away around
   the shoes; see remove_pedestal). Nothing else of the mesh is touched — no decimation,
   its UVs and its base-colour / roughness-metal / normal maps are kept
   (only re-encoded as plain JPEG/PNG so Godot can read them).
3. Scaled to the fighter's height, feet on the ground, centred on the hips,
   facing -Y like every other fighter.
4. Bound to the shared 18-bone fighter skeleton (the bone order and names the
   game, its animations and its hitbox tests rely on):
   - if the supplied rig is sound, its joints place the bones and its skin
     weights are kept, folded onto the game bones (fingers -> Hand,
     toes -> Foot, Spine1 -> Spine, Spine2/clavicles -> Chest);
   - if the supplied rig is broken (auto-rig fitted upside down or with the
     spine collapsed — checked below), joints are measured on the body and
     the mesh is re-skinned with import_hero.skin_weights instead.
   At most 4 bones per vertex, weights normalised.
5. Given every game animation from character_builder (timing from the real
   move data), named <FIGHTER>_<ACTION>.
"""
import argparse
import json
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import character_builder as cb  # noqa: E402
import import_hero as ih  # noqa: E402

GAME_BONES = list(cb.skeleton(cb.FIGHTERS["kairo"]).keys())


def game_bone(mixamo):
    """Game bone a Mixamo bone's skin weights fold onto (None: dropped)."""
    n = mixamo.split(":")[-1]
    for side in ("Left", "Right"):
        if n.startswith(side):
            rest = n[len(side):]
            if rest.startswith("Hand"):
                return f"{side}Hand"
            if rest in ("Foot", "ToeBase", "Toe_End"):
                return f"{side}Foot"
            if rest == "UpLeg":
                return f"{side}UpperLeg"
            if rest == "Leg":
                return f"{side}LowerLeg"
            if rest == "ForeArm":
                return f"{side}LowerArm"
            if rest == "Arm":
                return f"{side}UpperArm"
            if rest == "Shoulder":
                return "Chest"
            return None
    return {"Hips": "Hips", "Spine": "Spine", "Spine1": "Spine", "Spine2": "Chest",
            "Neck": "Neck", "Head": "Head", "HeadTop_End": "Head"}.get(n)


def rig_is_sound(P):
    """The supplied skeleton is usable only if it stands upright inside the body."""
    try:
        chain = [P["LeftFoot"].z, P["LeftLeg"].z, P["Hips"].z, P["Spine2"].z, P["Neck"].z, P["Head"].z]
    except KeyError:
        return False
    upright = all(a < b for a, b in zip(chain, chain[1:]))
    cx = P["Hips"].x
    sides = P["LeftArm"].x > cx > P["RightArm"].x and P["LeftUpLeg"].x > cx > P["RightUpLeg"].x
    return upright and sides


def remove_pedestal(obj):
    """Deletes a display base under the feet. Tripo bases are fused to the
    soles, so the cut is geometric: the base's top is found from the wide,
    low geometry outside the body; everything at or below it is removed
    except under the shoes (the footprint of the geometry just above)."""
    me = obj.data
    n = len(me.vertices)
    co = np.zeros(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    zmin, zmax = co[:, 2].min(), co[:, 2].max()
    h = zmax - zmin
    upper = co[co[:, 2] > zmin + 0.5 * h]
    c = np.median(upper[:, :2], axis=0)
    r = np.linalg.norm(co[:, :2] - c, axis=1)
    wide_low = (r > 0.2 * h) & (co[:, 2] < zmin + 0.15 * h)
    if wide_low.sum() < 30:
        return 0
    # a base surrounds the feet: its wide low geometry covers most directions
    ang = np.arctan2(co[wide_low, 1] - c[1], co[wide_low, 0] - c[0])
    sectors = np.unique(((ang + np.pi) / (2 * np.pi) * 12).astype(int) % 12)
    if len(sectors) < 9:
        return 0
    top = np.percentile(co[wide_low, 2], 97) + 0.004 * h
    # shoe footprint: occupied 1.5 cm cells (in a 1.8 m figure) just above the base, grown by one cell
    cell = 0.0085 * h
    band = co[(co[:, 2] > top + 0.01 * h) & (co[:, 2] < top + 0.07 * h) & (r < 0.2 * h)]
    occ = set()
    for x, y in np.floor(band[:, :2] / cell).astype(int):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                occ.add((x + dx, y + dy))
    cells = np.floor(co[:, :2] / cell).astype(int)
    under_shoe = np.array([(int(a), int(b)) in occ for a, b in cells])
    drop = (co[:, 2] <= top) & ~under_shoe
    # base parts deeper than the soles (thick plinths) go even under the shoes
    drop |= co[:, 2] < top - 0.02 * h
    if not drop.any():
        return 0
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(drop)[0]], context="VERTS")
    # crumbs: small loose islands left low down
    bm.verts.ensure_lookup_table()
    seen, crumbs = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, island = [v], []
        seen.add(v.index)
        while stack:
            u = stack.pop()
            island.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
        if len(island) < 200 and max(u.co.z for u in island) < top + 0.05 * h:
            crumbs.extend(island)
    if crumbs:
        bmesh.ops.delete(bm, geom=crumbs, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return int(drop.sum()) + len(crumbs)


def clean_image(img, path, max_size=2048):
    """Writes a packed texture as a plain file Godot's decoders accept."""
    from PIL import Image
    tmp = path + ".src"
    if img.packed_file is not None:
        open(tmp, "wb").write(img.packed_file.data)
    else:
        img.filepath_raw = tmp
        img.save()
    im = Image.open(tmp)
    im = im.convert("RGB")
    if max(im.size) > max_size:
        im = im.resize((max_size, max_size), Image.LANCZOS)
    if path.endswith(".jpg"):
        im.save(path, quality=92)
    else:
        im.save(path, optimize=True)
    os.remove(tmp)
    return bpy.data.images.load(path, check_existing=False)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--fighter", required=True)
    ap.add_argument("--moves", required=True)
    ap.add_argument("--out", default="assets/characters")
    ap.add_argument("--force-reskin", action="store_true")
    ap.add_argument("--joint", action="append", default=[],
                    help="override a measured left-side joint, metres on the final model: elbow=0.30,0,1.02 "
                         "(the middle value, depth, is taken from the mesh) "
                         "(shoulder, elbow, wrist, hand_tip, hip, knee, ankle, toe)")
    ap.add_argument("--mocap-dir", default="",
                    help="folder with the CMU BVH clips (tools/mocap/fetch_clips.sh); empty = old key poses")
    ap.add_argument("--hand-reach", type=float, default=0.12,
                    help="metres (for a 1.8 m figure): cloth this close to a hand follows it; raise for long sleeves")
    a = ap.parse_args(argv)
    fid = a.fighter
    F = fid.upper()
    H = cb.FIGHTERS[fid]["height"]
    out_dir = os.path.join(a.out, fid)
    os.makedirs(out_dir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = cb.FPS
    bpy.ops.import_scene.gltf(filepath=a.src)
    bpy.context.view_layer.update()
    src_arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
    body = [o for o in bpy.data.objects if o.type == "MESH" and o.vertex_groups][0]

    # Posed joint positions (what the viewer shows), world space.
    P = {pb.name.split(":")[-1]: src_arm.matrix_world @ pb.head for pb in src_arm.pose.bones}
    sound = rig_is_sound(P)                    # joints usable
    keep_weights = sound and not a.force_reskin

    # 1. bake the displayed pose into the mesh, then drop the source rig
    bpy.context.view_layer.objects.active = body
    for o in bpy.data.objects:
        o.select_set(o == body)
    for m in list(body.modifiers):
        if m.type == "ARMATURE":
            bpy.ops.object.modifier_apply(modifier=m.name)
    wm = body.matrix_world.copy()
    body.parent = None
    body.matrix_world = wm
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in [o for o in bpy.data.objects if o != body]:
        bpy.data.objects.remove(o)

    # 2. pedestal, then inspection + minimal repair (mesh_check: merges only
    # exact duplicates along texture seams, fixes winding; nothing moves)
    dropped = remove_pedestal(body)
    import mesh_check
    pre = mesh_check.inspect(body)
    fixed = mesh_check.repair(body)
    post = mesh_check.inspect(body)
    keys = ("verts", "parts", "duplicate_verts", "overlapping_faces", "degenerate_faces", "loose_verts",
            "nonmanifold_edges", "boundary_edges", "inconsistent_winding_edges", "long_edges_gt_20x_median")
    print("[check] before " + " ".join(f"{k}={pre[k]}" for k in keys))
    print("[check] fixed  " + " ".join(f"{k}={v}" for k, v in fixed.items()))
    print("[check] after  " + " ".join(f"{k}={post[k]}" for k in keys))
    print(f"[check] transform={pre['transform']} materials={pre['materials']} uv={pre['uv_layers']} "
          f"uv_range={pre.get('uv_range')} textures={[(t['image'], t['size'], t['colorspace']) for t in pre['textures']]}")

    # 3. height, ground, centre
    co = np.zeros(len(body.data.vertices) * 3)
    body.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    zmin, zmax = co[:, 2].min(), co[:, 2].max()
    s = H / (zmax - zmin)
    cx, cy = (P["Hips"].x, P["Hips"].y) if sound else (np.median(co[:, 0]), np.median(co[:, 1]))
    T = Matrix.Scale(s, 4) @ Matrix.Translation((-cx, -cy, -zmin))
    body.data.transform(T)
    body.data.update()
    P = {k: T @ v for k, v in P.items()}
    co = np.zeros(len(body.data.vertices) * 3)
    body.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    print(f"[rigged] {fid}: joints={'rig' if sound else 'measured'} weights={'kept' if keep_weights else 'reskinned'} pedestal_verts={dropped} "
          f"scale={s:.3f} tris={tris}")

    # 4. game skeleton
    k = H / 1.8
    if sound:
        def sym(name):
            l, r = P["Left" + name], P["Right" + name]
            return Vector(((l.x - r.x) / 2, (l.y + r.y) / 2, (l.z + r.z) / 2))
        J = {"shoulder": sym("Arm"), "elbow": sym("ForeArm"), "wrist": sym("Hand"),
             "hip": sym("UpLeg"), "knee": sym("Leg"), "ankle": sym("Foot")}
        J["hand_tip"] = J["wrist"] + (J["wrist"] - J["elbow"]).normalized() * 0.1 * k
        toe = sym("ToeBase") if "LeftToeBase" in P and "RightToeBase" in P else J["ankle"] + Vector((0, -0.14 * k, -0.06 * k))
        J["toe"] = Vector((toe.x, min(toe.y, J["ankle"].y - 0.08 * k), max(0.02 * k, toe.z)))
        spine = [Vector((0, P[n].y, P[n].z)) for n in ("Hips", "Spine", "Spine2", "Neck", "Head")]
        top = Vector((0, spine[-1].y, co[:, 2].max()))
    else:
        J = ih.joints_from_mesh(co, H)
        hips = Vector((0, -0.02, J["hip"].z + 0.02 * k))
        spine = [hips, Vector((0, -0.02, 1.12 * k)), Vector((0, -0.02, 1.28 * k)),
                 Vector((0, -0.03, 1.45 * k)), Vector((0, -0.04, 1.56 * k))]
        top = Vector((0, -0.04, co[:, 2].max()))

    for spec in a.joint:
        name, xyz = spec.split("=")
        J[name] = Vector(tuple(float(c) for c in xyz.split(",")))
        # depth from the mesh: centre of the geometry around that point (front view gives x, z only)
        near = (np.abs(co[:, 0] - J[name].x) < 0.05 * k) & (np.abs(co[:, 2] - J[name].z) < 0.03 * k)
        if near.sum() > 20:
            J[name].y = float(np.median(co[near, 1]))
        print(f"[rigged] joint override {name}={tuple(J[name])}")

    B = {
        "Root": ((0, 0, 0), (0, 0, 0.15 * k), None, False),
        "Hips": (tuple(spine[0]), tuple(spine[1]), "Root", False),
        "Spine": (tuple(spine[1]), tuple(spine[2]), "Hips", True),
        "Chest": (tuple(spine[2]), tuple(spine[3]), "Spine", True),
        "Neck": (tuple(spine[3]), tuple(spine[4]), "Chest", True),
        "Head": (tuple(spine[4]), tuple(top), "Neck", True),
    }
    for side, sg in (("Left", 1), ("Right", -1)):
        def m(v):
            return (v.x * sg, v.y, v.z)
        B[f"{side}UpperArm"] = (m(J["shoulder"]), m(J["elbow"]), "Chest", False)
        B[f"{side}LowerArm"] = (m(J["elbow"]), m(J["wrist"]), f"{side}UpperArm", True)
        B[f"{side}Hand"] = (m(J["wrist"]), m(J["hand_tip"]), f"{side}LowerArm", True)
        B[f"{side}UpperLeg"] = (m(J["hip"]), m(J["knee"]), "Hips", False)
        B[f"{side}LowerLeg"] = (m(J["knee"]), m(J["ankle"]), f"{side}UpperLeg", True)
        B[f"{side}Foot"] = (m(J["ankle"]), m(J["toe"]), f"{side}LowerLeg", True)
    B = {n: B[n] for n in GAME_BONES}

    arm_data = bpy.data.armatures.new(f"{F}_Skeleton")
    rig = bpy.data.objects.new(f"{F}_Rig", arm_data)
    sc.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent, connect) in B.items():
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail, eb.roll = head, tail, 0.0
        if parent:
            eb.parent = arm_data.edit_bones[parent]
            eb.use_connect = connect
    bpy.ops.object.mode_set(mode="OBJECT")

    body.name = f"{F}_Body"
    if keep_weights:
        # fold the supplied weights onto the game bones
        n = len(body.data.vertices)
        idx = {nm: i for i, nm in enumerate(GAME_BONES)}
        W = np.zeros((n, len(GAME_BONES)))
        gmap = {g.index: game_bone(g.name) for g in body.vertex_groups}
        for v in body.data.vertices:
            for ge in v.groups:
                tgt = gmap.get(ge.group)
                if tgt is not None:
                    W[v.index, idx[tgt]] += ge.weight
        for g in list(body.vertex_groups):
            body.vertex_groups.remove(g)
        orphan = W.sum(1) <= 1e-6
        W[orphan, idx["Hips"]] = 1.0
        # top 4, drop dust, normalise
        order = np.argsort(-W, axis=1)
        keep = np.zeros_like(W, bool)
        np.put_along_axis(keep, order[:, :4], True, axis=1)
        W = np.where(keep & (W > 0.01), W, 0.0)
        W /= W.sum(1, keepdims=True)
        groups = [body.vertex_groups.new(name=nm) for nm in GAME_BONES]
        for j, g in enumerate(groups):
            nz = np.nonzero(W[:, j])[0]
            for vi in nz:
                g.add([int(vi)], float(W[vi, j]), "REPLACE")
        body.parent = rig
        body.modifiers.new("Armature", "ARMATURE").object = rig
        print(f"[rigged] weights folded: orphans={int(orphan.sum())}")
    else:
        for g in list(body.vertex_groups):
            body.vertex_groups.remove(g)
        for o in bpy.data.objects:
            o.select_set(o in (body, rig))
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.parent_set(type="ARMATURE_NAME")
        un = ih.skin_weights(body, B, H, a.hand_reach)
        print(f"[rigged] re-skinned: unweighted={un}")

    # textures: plain files, one material named <F>_Body
    mat = body.data.materials[0]
    for node in mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image is not None:
            nm = node.image.name.lower()
            kind = "normal" if "normal" in nm else ("rm" if "_rm" in nm or "rough" in nm or "metal" in nm else "basecolor")
            cs = node.image.colorspace_settings.name
            ext = ".png" if kind == "rm" else ".jpg"
            # the colour map keeps its full 4K detail; roughness/metal and normal stay at their 2K
            node.image = clean_image(node.image, os.path.abspath(os.path.join(out_dir, f"{fid}_{kind}{ext}")),
                                     4096 if kind == "basecolor" else 2048)
            node.image.colorspace_settings.name = cs
    mat.name = f"{F}_Body"
    for p in body.data.polygons:
        p.use_smooth = True

    # 5. animations
    moves = json.loads(open(a.moves).read())
    rig.animation_data_create()
    if a.mocap_dir:
        # real motion capture (D-057)
        import mocap_actions
        actions = mocap_actions.build(rig, moves, fid, H, a.mocap_dir)
    else:
        targets = cb.setup_ik(rig)
        actions = cb.build_actions(moves, H / cb.REF_HEIGHT, fid)
        for name, keys in actions.items():
            cb.key_action(rig, targets, name, keys)
        for pb in rig.pose.bones:
            for c in list(pb.constraints):
                pb.constraints.remove(c)
        for empty, _c in targets.values():
            bpy.data.objects.remove(empty)
    rig.animation_data.action = bpy.data.actions[f"{F}_IDLE_A"]
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    out_path = os.path.join(out_dir, f"{fid}.glb")
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True,
                              export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_step=1,
                              export_skins=True, export_def_bones=False, export_yup=True, export_apply=False,
                              export_materials="EXPORT", export_image_format="AUTO")
    # only this script's own texture copies (now embedded in the GLB); Godot's
    # extracted textures next to the model (<fid>_<fid>_*.jpg) must stay
    for kind in ("basecolor.jpg", "rm.png", "normal.jpg"):
        f = os.path.join(out_dir, f"{fid}_{kind}")
        if os.path.exists(f):
            os.remove(f)
    print(f"[rigged] {fid}: tris={tris} actions={len(actions)} -> {out_path}")


if __name__ == "__main__":
    main()
