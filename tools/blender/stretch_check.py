"""Counts stretched edges in a fighter's animations (skinning check).

For every frame of every action whose name contains one of the given words,
the skinned mesh is evaluated and each edge compared with its rest length.
An edge more than LIMIT times its rest length (and at least 1 cm long at
rest) counts as stretched: a sign of vertices torn between two bones. The
idle is always measured too, as the baseline the fighter already has.

  python tools/blender/stretch_check.py <fighter.glb> [word ...]
"""
import sys

import bpy
import numpy as np

LIMIT = 2.0


def main():
    path, words = sys.argv[1], [w.upper() for w in sys.argv[2:]]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 60          # the game's tick rate: one scene frame per animation frame
    bpy.ops.import_scene.gltf(filepath=path)
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = max((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: len(o.data.vertices))
    edges = np.zeros(len(body.data.edges) * 2, int)
    body.data.edges.foreach_get("vertices", edges)
    edges = edges.reshape(-1, 2)

    def coords():
        ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        co = np.zeros(len(ev.data.vertices) * 3)
        ev.data.vertices.foreach_get("co", co)
        return co.reshape(-1, 3)

    def lengths(co):
        return np.linalg.norm(co[edges[:, 0]] - co[edges[:, 1]], axis=1)

    rig.animation_data_create()
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()
    rest = lengths(coords())
    ok = rest > 0.01
    print(f"{path}: {len(edges)} edges, limit x{LIMIT}")
    for act in sorted(bpy.data.actions, key=lambda a: a.name):
        if "IDLE" not in act.name and words and not any(w in act.name for w in words):
            continue
        rig.animation_data.action = act
        if hasattr(rig.animation_data, "action_slot") and act.slots:
            rig.animation_data.action_slot = act.slots[0]
        f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
        worst, worst_f, worst_ratio, total = 0, f0, 0.0, 0
        for f in range(f0, f1 + 1):
            bpy.context.scene.frame_set(f)
            ratio = lengths(coords())[ok] / rest[ok]
            n = int((ratio > LIMIT).sum())
            total += n
            if n > worst:
                worst, worst_f = n, f
            worst_ratio = max(worst_ratio, float(ratio.max()))
        print(f"  {act.name:36s} frames {f1 - f0 + 1:3d}  worst frame {worst_f - f0 + 1:3d}: {worst:4d} stretched edges"
              f"  mean/frame {total / (f1 - f0 + 1):6.1f}  longest x{worst_ratio:.1f}")


if __name__ == "__main__":
    main()
