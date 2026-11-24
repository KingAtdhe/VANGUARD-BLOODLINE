extends RefCounted
## Milestone 6 acceptance on the real imported model (kairo.glb, owner-supplied since D-054).

const MODEL: String = "res://assets/characters/kairo/kairo.glb"
## Godot SkeletonProfileHumanoid names used by the rig.
const HUMANOID_BONES: Array[String] = ["Hips", "Spine", "Chest", "Neck", "Head",
	"LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm", "RightHand",
	"LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot"]
## Striking limb per move and how far past the joint the contact point is.
## Since D-087 the Rift Break is an axe kick and the body move a front kick.
const STRIKER: Dictionary = {
	&"kairo_light_punch": ["LeftHand", 0.06], &"kairo_heavy_punch": ["RightHand", 0.06],
	&"kairo_low_kick": ["RightFoot", 0.08], &"kairo_origin_palm": ["LeftHand", 0.06],
	&"kairo_rift_break": ["RightFoot", 0.08], &"kairo_body_hook": ["RightFoot", 0.08],
}
## A multi-hit move: the limb that lands each hit, checked on the first two
## frames of that hit's window (the limb is on its way in or out otherwise).
const MULTI_STRIKER: Dictionary = {
	# D-100: straight, body hook, high roundhouse, rising uppercut
	&"kairo_origin_break": [["LeftHand", 0.06], ["LeftHand", 0.06], ["RightFoot", 0.08], ["RightHand", 0.06]],
}
const TOLERANCE: float = 0.06


func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


func _def() -> FighterDefinition:
	return load("res://data/fighters/kairo.tres")


func test_model_has_all_animations_and_humanoid_skeleton() -> Array[String]:
	var f: Array[String] = []
	var model: Node = (load(MODEL) as PackedScene).instantiate()
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var sk: Skeleton3D = model.find_children("*", "Skeleton3D", true, false)[0]
	for a: StringName in _def().required_animations():
		if not ap.has_animation(a):
			f.append("missing animation %s" % a)
	for b: String in HUMANOID_BONES:
		if sk.find_bone(b) < 0:
			f.append("missing humanoid bone %s" % b)
	# Finger bones kept from the source rig (D-060) so fists can close.
	for side: String in ["Left", "Right"]:
		for finger: String in ["Thumb", "Index", "Middle", "Ring", "Pinky"]:
			if sk.find_bone("%sHand%s1" % [side, finger]) < 0:
				f.append("missing finger bone %sHand%s1" % [side, finger])
	# Animation length must equal the move's frame count (frame N == tick N).
	for m: MoveData in _def().moves:
		if ap.has_animation(m.animation):
			var frames: float = ap.get_animation(m.animation).length * CombatConstants.TICK_RATE + 1.0
			if absf(frames - m.total_frames()) > 0.01:
				f.append("%s lasts %.1f frames, move has %d" % [m.animation, frames, m.total_frames()])
	model.free()
	return f


func test_skinning_and_budgets() -> Array[String]:
	# Smooth skinning (M7 quality pass): every vertex is fully weighted
	# (weights sum to 1, at most 4 bones), and rigid parts of the head stay
	# on one bone so the face can't smear. Plus §8.6 budgets.
	var f: Array[String] = []
	var model: Node = (load(MODEL) as PackedScene).instantiate()
	var tris: int = 0
	var materials: int = 0
	var blended: int = 0
	var total: int = 0
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (n as MeshInstance3D).mesh
		materials += mesh.get_surface_count()
		for s: int in mesh.get_surface_count():
			var arrays: Array = mesh.surface_get_arrays(s)
			var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			tris += idx.size() / 3
			var w: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
			var count: int = (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
			var per_vertex: int = w.size() / count
			if per_vertex > 4:
				f.append("surface %d uses %d bone influences (max 4)" % [s, per_vertex])
			for v: int in count:
				var sum: float = 0.0
				for k: int in per_vertex:
					sum += w[v * per_vertex + k]
				if absf(sum - 1.0) > 0.01:
					f.append("surface %d vertex %d weights sum to %.3f" % [s, v, sum])
					break
				total += 1
				if w[v * per_vertex] < 0.999:
					blended += 1
	if blended == 0:
		f.append("no blended vertices: joints would show seams")
	# Owner-supplied rigs (D-054) keep their own, softer skinning: ~72% of
	# vertices blend on Kairo. Above 80% the weights would be smeared.
	if blended > total * 0.8:
		f.append("%d of %d vertices are blended: weights are smeared" % [blended, total])
	if tris > 45000:
		f.append("%d triangles exceeds the 45k fighter budget" % tris)
	if materials > 6:
		f.append("%d material slots exceeds the 3–6 target" % materials)
	model.free()
	return f


func test_hitboxes_align_with_striking_limb() -> Array[String]:
	# Uses the in-game transform chain (FighterView yaw → model → skeleton).
	var f: Array[String] = []
	var view: FighterView = (load("res://scenes/fighters/placeholder_fighter.tscn") as PackedScene).instantiate()
	_tree().root.add_child(view)
	view.setup(_def())
	var sk: Skeleton3D = view.skeleton
	var ap: AnimationPlayer = view.model.find_child("AnimationPlayer", true, false)
	for facing: int in [1, -1]:
		var state := FighterState.new()
		state.position_x = 0.0
		state.facing = facing
		view.position = Vector3.ZERO
		view.get_node("%ModelRoot").rotation.y = deg_to_rad(view.profile_yaw_degrees) * facing
		for m: MoveData in _def().moves:
			if not STRIKER.has(m.id) and not MULTI_STRIKER.has(m.id):
				continue
			state.action = FighterState.Action.ATTACK
			state.move = m
			var box_state := state.copy()
			for frame: int in range(m.startup_frames, m.startup_frames + m.active_frames):
				var limb: String
				var reach_past: float
				if MULTI_STRIKER.has(m.id):
					if (frame - m.startup_frames) % m.rehit_interval > 1:
						continue
					var per_hit: Array = MULTI_STRIKER[m.id][m.hit_window(frame)]
					limb = per_hit[0]
					reach_past = per_hit[1]
				else:
					limb = STRIKER[m.id][0]
					reach_past = STRIKER[m.id][1]
				AnimationSampler.apply(ap.get_animation(m.animation), sk, AnimationSampler.time_of_frame(frame))
				var bone: int = sk.find_bone(limb)
				var g: Transform3D = sk.global_transform * AnimationSampler.bone_global(sk, bone)
				# Contact point: a little past the joint along the limb's last bone.
				var tip: Vector3 = g.origin + g.basis.y.normalized() * reach_past
				box_state.move_frame = frame
				var hb: Rect2 = HitboxSystem.hitbox(box_state).grow(TOLERANCE)
				var p := Vector2(tip.x, tip.y)
				if not hb.has_point(p):
					f.append("facing %+d %s frame %d: %s at (%.2f, %.2f) outside hitbox %s" % [
						facing, m.id, frame, limb, p.x, p.y, HitboxSystem.hitbox(box_state)])
	view.free()
	return f


func test_animator_follows_simulation_state() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def()
	var model: Node = (load(MODEL) as PackedScene).instantiate()
	_tree().root.add_child(model)
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var anim := FighterAnimator.new(ap, def)
	var s := FighterState.new()
	anim.update(s, 0.0, false, 0.016)
	if anim.current != def.anim_idle:
		f.append("idle state shows %s" % anim.current)
	s.action = FighterState.Action.ATTACK
	s.move = def.move_for(&"KICK")
	s.move_frame = 9
	anim.update(s, 0.0, false, 0.016)
	if anim.current != s.move.animation or absf(ap.current_animation_position - 8.0 / 60.0) > 0.001:
		f.append("kick frame 9 shows %s at %.4f s (expected %s at %.4f)" % [
			anim.current, ap.current_animation_position, s.move.animation, 8.0 / 60.0])
	# Hitstop freezes the pose even with time passing.
	anim.update(s, 0.9, true, 0.5)
	if absf(ap.current_animation_position - 8.0 / 60.0) > 0.001:
		f.append("attack pose moved during hitstop")
	var expect: Dictionary = {
		FighterState.Action.HITSTUN: def.anim_hit_light, FighterState.Action.BLOCK: def.anim_block,
		FighterState.Action.KNOCKDOWN: def.anim_knockdown, FighterState.Action.WAKEUP: def.anim_getup,
		FighterState.Action.KO: def.anim_knockdown,
	}
	for action: int in expect:
		s.action = action as FighterState.Action
		s.move = null
		s.stun_remaining = 10
		anim.update(s, 0.0, false, 0.016)
		if anim.current != expect[action]:
			f.append("%s shows %s, expected %s" % [FighterState.Action.keys()[action], anim.current, expect[action]])
	anim.set_override(def.anim_victory)
	anim.update(s, 0.0, false, 0.016)
	if anim.current != def.anim_victory:
		f.append("victory override not shown")
	model.free()
	return f


func test_kairo_completes_full_match_in_real_scene() -> Array[String]:
	# Milestone 6 acceptance: "Kairo can complete a full match" — the real
	# versus scene (models, animator, HUD, audio, results), CPU vs CPU.
	var f: Array[String] = []
	var scene: Node = (load(ScenePaths.COMBAT_GREYBOX) as PackedScene).instantiate()
	_tree().root.add_child(scene)
	if not scene.is_node_ready() or scene.director == null:
		scene.free()
		return ["scene did not initialise"]
	scene.p1_ai = AIController.new(load("res://data/ai/expert.tres"), 0,
		scene.simulation.definitions[0], scene.simulation.definitions[1], 31)
	var d: MatchDirector = scene.director
	var frames: int = 0
	var anims_seen: Dictionary = {}
	var views: Array = [scene.get_node("%Fighter1"), scene.get_node("%Fighter2")]
	while not d.is_match_over() and frames < 30000:
		scene._process(1.0 / 60.0)
		frames += 1
		for v: FighterView in views:
			if v.animator != null:
				anims_seen[v.animator.current] = true
	if not d.is_match_over():
		f.append("match did not finish in %d frames (phase %s)" % [frames, d.phase_name()])
	else:
		var results: MatchResults = scene.get_node("%MatchResults")
		if not results.visible:
			f.append("results not shown")
		if d.match_winner >= 0:
			var winner_view: FighterView = views[d.match_winner]
			for _i: int in 5:
				scene._process(1.0 / 60.0)
			if winner_view.animator.current != scene.simulation.definitions[d.match_winner].anim_victory:
				f.append("winner shows %s, not the victory pose" % winner_view.animator.current)
	for needed: StringName in [&"KAIRO_IDLE_A", &"KAIRO_WALK_FORWARD", &"KAIRO_ATTACK_LIGHT_01", &"KAIRO_HIT_LIGHT"]:
		if not anims_seen.has(needed):
			f.append("animation %s never played during the match" % needed)
	var audio: CombatAudio = scene.get_node("%CombatAudio")
	if not audio.played.has(&"hit_light") and not audio.played.has(&"hit_heavy"):
		f.append("no hit sounds were triggered")
	scene.free()
	return f


func test_crouch_lingers_through_an_input_flicker() -> Array[String]:
	# D-094: one or two neutral or walking ticks in the middle of a crouch
	# must not start him standing up; a real release must.
	var f: Array[String] = []
	var def: FighterDefinition = _def()
	var model: Node = (load(MODEL) as PackedScene).instantiate()
	_tree().root.add_child(model)
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var anim := FighterAnimator.new(ap, def)
	var s := FighterState.new()
	s.action = FighterState.Action.CROUCH
	anim.update(s, 0.0, false, 0.016)
	if anim.current != def.anim_crouch:
		f.append("crouch state shows %s" % anim.current)
	for flicker: FighterState.Action in [FighterState.Action.IDLE, FighterState.Action.WALK]:
		s.action = flicker
		anim.update(s, 0.0, false, 0.016)
		anim.update(s, 0.0, false, 0.016)
		if anim.current != def.anim_crouch:
			f.append("two %s frames ended the crouch pose" % FighterState.Action.keys()[flicker])
		s.action = FighterState.Action.CROUCH
		anim.update(s, 0.0, false, 0.016)
	s.action = FighterState.Action.IDLE
	for _i: int in 12:
		anim.update(s, 0.0, false, 0.016)
	if anim.current != def.anim_idle:
		f.append("still crouching 0.2 s after release (%s)" % anim.current)
	# an attack out of a crouch is never delayed
	s.action = FighterState.Action.CROUCH
	anim.update(s, 0.0, false, 0.016)
	s.action = FighterState.Action.ATTACK
	s.move = def.move_for(&"KICK")
	s.move_frame = 2
	anim.update(s, 0.0, false, 0.016)
	if anim.current != s.move.animation:
		f.append("attack from a crouch shows %s" % anim.current)
	model.free()
	return f
