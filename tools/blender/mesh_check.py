"""Inspection and minimal repair of an imported character mesh.

inspect(obj) -> dict report (changes nothing)
repair(obj)  -> dict of what was fixed

Repairs are deliberately conservative: they never move a vertex or change
the silhouette, proportions or UVs.
  * exact duplicate vertices (closer than 0.01 mm) are merged — UVs live on
    face corners, so seams keep their UVs;
  * faces that exactly repeat another face (same vertices) are removed;
  * zero-area faces and edges are dissolved; loose vertices/edges removed;
  * face winding made consistent and pointing outward per connected part.
Open borders (non-manifold boundary edges) are normal for scanned/generated
garments and are only reported, never "closed".
"""
import bpy  # noqa: F401  (bmesh is only importable once bpy is loaded)
import bmesh
import numpy as np


def _bm(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    return bm


def inspect(obj, dup_dist=1e-5):
    me = obj.data
    bm = _bm(obj)
    r = {}
    r["verts"], r["faces"], r["tris"] = len(bm.verts), len(bm.faces), sum(len(f.verts) - 2 for f in bm.faces)
    r["transform"] = {"location": tuple(round(v, 4) for v in obj.location),
                      "rotation": tuple(round(v, 4) for v in obj.rotation_euler),
                      "scale": tuple(round(v, 4) for v in obj.scale)}
    co = np.array([v.co[:] for v in bm.verts])
    q = np.round(co / dup_dist).astype(np.int64)
    _, inv, counts = np.unique(q, axis=0, return_inverse=True, return_counts=True)
    r["duplicate_verts"] = int((counts[counts > 1] - 1).sum())
    keys = {}
    dup_faces = 0
    for f in bm.faces:
        k = tuple(sorted(int(inv[v.index]) for v in f.verts))
        dup_faces += k in keys
        keys[k] = 1
    r["overlapping_faces"] = dup_faces
    r["degenerate_faces"] = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
    r["loose_verts"] = sum(1 for v in bm.verts if not v.link_edges)
    r["loose_edges"] = sum(1 for e in bm.edges if not e.link_faces)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    r["nonmanifold_edges"] = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    r["boundary_edges"] = boundary
    # winding consistency: an edge shared by two faces must be walked in
    # opposite directions by them
    bad = 0
    for e in bm.edges:
        if len(e.link_faces) == 2:
            dirs = []
            for f in e.link_faces:
                vs = [v.index for v in f.verts]
                i = vs.index(e.verts[0].index)
                dirs.append(vs[(i + 1) % len(vs)] == e.verts[1].index)
            bad += dirs[0] == dirs[1]
    r["inconsistent_winding_edges"] = bad
    # outward check: for each connected part, normals should point away from
    # its centre on average
    inward = 0
    parts = _parts(bm)
    for part in parts:
        c = np.mean([bm.faces[i].calc_center_median()[:] for i in part], 0)
        s = sum(np.dot(np.array(bm.faces[i].normal[:]), np.array(bm.faces[i].calc_center_median()[:]) - c)
                * bm.faces[i].calc_area() for i in part)
        inward += s < 0
    r["parts"], r["parts_facing_inward"] = len(parts), int(inward)
    # interior faces (fully enclosed geometry)
    bmesh.ops.recalc_face_normals  # (noqa: keep import used)
    r["interior_faces"] = sum(1 for f in bm.faces if all(len(e.link_faces) > 2 for e in f.edges))
    # stretched triangles: edges far longer than typical (broken geometry)
    el = np.array([e.calc_length() for e in bm.edges])
    med = float(np.median(el)) if len(el) else 0
    r["long_edges_gt_20x_median"] = int((el > 20 * med).sum()) if med > 0 else 0
    # materials, UVs, textures
    r["materials"] = [m.name if m else None for m in me.materials]
    r["uv_layers"] = [uv.name for uv in me.uv_layers]
    if me.uv_layers:
        uv = np.zeros(len(me.loops) * 2)
        me.uv_layers.active.data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        r["uv_range"] = (tuple(np.round(uv.min(0), 3)), tuple(np.round(uv.max(0), 3)))
        r["uv_nan"] = int(np.isnan(uv).sum())
    tex = []
    for m in me.materials:
        if m and m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE":
                    img = n.image
                    linked = [l.to_socket.name for l in n.outputs["Color"].links] if n.outputs["Color"].links else []
                    tex.append({"image": img.name if img else None, "size": tuple(img.size) if img else None,
                                "colorspace": img.colorspace_settings.name if img else None, "feeds": linked})
    r["textures"] = tex
    bm.free()
    return r


def _parts(bm):
    seen = set()
    parts = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, part = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            part.append(g.index)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        parts.append(part)
    return parts


def repair(obj, dup_dist=1e-5):
    me = obj.data
    bm = _bm(obj)
    out = {}
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dup_dist)
    out["merged_duplicate_verts"] = n0 - len(bm.verts)
    bm.faces.ensure_lookup_table()
    keys, dup = {}, []
    for f in bm.faces:
        k = tuple(sorted(v.index for v in f.verts))
        if k in keys:
            dup.append(f)
        keys[k] = 1
    if dup:
        bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
    out["removed_overlapping_faces"] = len(dup)
    deg = bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges[:])
    out["dissolved_degenerate"] = bool(deg)
    loose_e = [e for e in bm.edges if not e.link_faces]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    loose_v = [v for v in bm.verts if not v.link_edges]
    if loose_v:
        bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    out["removed_loose"] = len(loose_e) + len(loose_v)
    # Recalculate outward only where the winding is actually wrong: on thin,
    # open garments the automatic recalculation can misjudge "outside" and
    # flip correct surfaces, so it is applied per connected part, and only to
    # parts that are inconsistent or face inward.
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    flipped = 0
    for part in _parts(bm):
        faces = [bm.faces[i] for i in part]
        fset = set(part)
        inconsistent = False
        for f in faces:
            for e in f.edges:
                lf = [g for g in e.link_faces if g.index in fset]
                if len(lf) == 2:
                    d = []
                    for g in lf:
                        vs = [v.index for v in g.verts]
                        i = vs.index(e.verts[0].index)
                        d.append(vs[(i + 1) % len(vs)] == e.verts[1].index)
                    inconsistent |= d[0] == d[1]
        c = np.mean([f.calc_center_median()[:] for f in faces], 0)
        outward = sum(np.dot(np.array(f.normal[:]), np.array(f.calc_center_median()[:]) - c) * f.calc_area()
                      for f in faces)
        if not inconsistent and outward >= 0:
            continue
        before = [f.normal.copy() for f in faces]
        bmesh.ops.recalc_face_normals(bm, faces=faces)
        flipped += sum(1 for f, n in zip(faces, before) if f.normal.dot(n) < 0)
    out["faces_flipped_outward"] = flipped
    bm.to_mesh(me)
    bm.free()
    me.update()
    return out


# --------------------------------------------------------------------------- CLI

def _main():
    """python tools/blender/mesh_check.py <mesh.glb|.gltf|.fbx|.obj> [--repair-preview]

    Prints the inspection report for every mesh object in the file (run on
    every owner-uploaded mesh before it is used — see CLAUDE.md). With
    --repair-preview it also reports what repair() would change, on a copy.
    The file itself is never modified.
    """
    import json
    import sys

    import bpy
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    path = argv[0]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = path.lower().rsplit(".", 1)[-1]
    if ext in ("glb", "gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == "fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == "obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise SystemExit(f"unsupported mesh format: {ext}")
    for o in [o for o in bpy.data.objects if o.type == "MESH"]:
        rep = inspect(o)
        dims = tuple(round(d, 3) for d in o.dimensions)
        print(f"== {o.name}  parent={o.parent.name if o.parent else None}  dimensions={dims}  "
              f"armature={'yes' if any(m.type == 'ARMATURE' for m in o.modifiers) else 'no'}  "
              f"groups={len(o.vertex_groups)}")
        print(json.dumps({k: v for k, v in rep.items() if k != 'textures'}, default=str))
        for t in rep["textures"]:
            print("   texture", t)
        if "--repair-preview" in argv:
            tmp = o.copy()
            tmp.data = o.data.copy()
            bpy.context.scene.collection.objects.link(tmp)
            print("   repair would do:", repair(tmp))
            print("   after:", {k: v for k, v in inspect(tmp).items()
                                 if k in ("verts", "parts", "duplicate_verts", "nonmanifold_edges",
                                          "boundary_edges", "inconsistent_winding_edges")})


if __name__ == "__main__":
    _main()
