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
    before = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.faces.ensure_lookup_table()
    out["faces_flipped_outward"] = sum(1 for f, n in zip(bm.faces, before) if f.normal.dot(n) < 0)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return out
