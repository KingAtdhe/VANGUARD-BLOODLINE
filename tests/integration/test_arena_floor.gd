extends RefCounted
## Fighters stand on y = 0. Every arena's floor under the fighting line must
## be there too once the arena has been lowered by ArenaConfig.stage_height
## (legs buried in a raised stage: The Pit and the Origin Chamber, 2026-11-21).

const TOLERANCE: float = 0.03


## Highest solid surface of [param arena] below 0.6 m at (x, z = 0).
func _floor_at(arena: Node3D, x: float) -> float:
	var best: float = -99.0
	# the built model only: light shafts, haze and other ambience are not floor
	var solid: Node = arena.get_node_or_null("Geometry")
	for m: Node in (solid if solid != null else arena).find_children("*", "MeshInstance3D", true, false):
		var mi := m as MeshInstance3D
		if mi.mesh == null or not mi.is_visible_in_tree():
			continue
		var bb: AABB = mi.global_transform * mi.get_aabb()
		if x < bb.position.x or x > bb.end.x or bb.position.z > 0.0 or bb.end.z < 0.0:
			continue
		var inv: Transform3D = mi.global_transform.affine_inverse()
		var from: Vector3 = inv * Vector3(x, 0.6, 0.0)
		var dir: Vector3 = (inv.basis * Vector3.DOWN).normalized()
		var faces: PackedVector3Array = mi.mesh.get_faces()
		for i: int in range(0, faces.size(), 3):
			var hit: Variant = Geometry3D.ray_intersects_triangle(from, dir, faces[i], faces[i + 1], faces[i + 2])
			if hit != null:
				best = maxf(best, (mi.global_transform * (hit as Vector3)).y)
	return best


func test_fighters_stand_on_every_arena_floor() -> Array[String]:
	var f: Array[String] = []
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	for id: StringName in [&"ascendant", &"temple", &"neon", &"origin"]:
		var cfg: ArenaConfig = Catalog.arena(id)
		var arena: Node3D = (load(cfg.scene_path) as PackedScene).instantiate()
		tree.root.add_child(arena)
		# every half metre a fighter's feet can reach (walls minus the pushbox)
		var x: float = cfg.left_bound + 0.5
		while x <= cfg.right_bound - 0.5:
			# a foot spans the narrow joints between paving stones: take the
			# highest of three points 7 cm apart
			var top: float = maxf(_floor_at(arena, x), maxf(_floor_at(arena, x - 0.07), _floor_at(arena, x + 0.07)))
			var gap: float = top - cfg.stage_height
			if absf(gap) > TOLERANCE:
				f.append("%s: floor is %+.2f m from the fighters' feet at x = %.1f" % [id, gap, x])
			x += 0.5
		tree.root.remove_child(arena)
		arena.free()
	return f
