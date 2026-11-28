extends SceneTree
## Gameplay animation audit (D-145): runs the real training scene with a
## scripted input list for P1 (same steps as scene_video.gd) and, on every
## rendered frame, samples P1's skeleton in WORLD space - the pose the player
## actually sees, after blending, seeking, the game's travel and hit-stop.
##
##   godot --headless --path . --fixed-fps 60 --script res://tools/godot/gameplay_audit.gd -- <script> [fighter] [csv]
##
## Prints:
##   JUMP   a joint that moved more than JUMP_CM in one frame, with the state
##          change (if any) it happened on: pops at blends and cuts.
##   SLIDE  a foot that is on the floor (its lowest joint under FLOOR_CM) and
##          moved along the floor more than SLIDE_CM in one frame.
##   STATE  every change of action / clip, with the frame.
## and a per-state summary of the worst jump and slide. [csv] writes every
## frame (state, clip time, joints) for plots.

const JOINTS: Array[String] = ["Hips", "Chest", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"]
const JUMP_CM: float = 14.0
const FLOOR_CM: float = 4.0
const SLIDE_CM: float = 1.2

var _prev: Dictionary = {}
var _prev_state: String = ""
var _frame: int = 0
var _worst: Dictionary = {}          # state -> [jump_cm, slide_cm]
var _csv: FileAccess = null
var _probe: SkeletonModifier3D = null


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	SaveManager.ensure_loaded()
	var s := MatchSetup.new()
	s.p1_id = StringName(a[1]) if a.size() > 1 else &"kairo"
	s.p2_id = &"training_dummy"
	s.mode = MatchSetup.Mode.TRAINING
	s.rules_path = MatchSetup.RULES_TRAINING
	ModeFlow.setup = s
	if a.size() > 2:
		_csv = FileAccess.open(a[2], FileAccess.WRITE)
	var scene: Node = (load(ScenePaths.TRAINING_GREYBOX) as PackedScene).instantiate()
	root.add_child(scene)
	var sim: CombatSimulation = scene.get("simulation")
	await process_frame
	await process_frame
	var views: Array = scene.get("_fighter_views")
	var view: Node3D = views[0]
	var skel: Skeleton3D = view.get("skeleton")
	var anim: FighterAnimator = view.get("animator")
	# read the pose after every modifier (the foot lock), as it is drawn
	_probe = (load("res://tools/godot/pose_probe_modifier.gd") as GDScript).new()
	_probe.set("joints", PackedStringArray(JOINTS))
	skel.add_child(_probe)
	for step: String in (a[0] if a.size() > 0 else "wait:120").split(","):
		var parts: PackedStringArray = step.split(":")
		var n: int = int(parts[1]) if parts.size() > 1 else 1
		if parts[0] == "meter":
			sim.fighters[0].meter = sim.tuning.meter_max
			sim.fighters[0].surge_remaining = 900
			continue
		var acts: PackedStringArray = [] if parts[0] == "wait" else parts[0].split("+")
		for act: String in acts:
			Input.action_press(StringName(act))
		for i: int in n:
			await process_frame
			_sample(sim, skel, anim)
		for act: String in acts:
			Input.action_release(StringName(act))
	print("--- worst per state (cm): jump / slide")
	for k: String in _worst:
		print("  %-44s %6.1f %6.1f" % [k, _worst[k][0], _worst[k][1]])
	if _csv != null:
		_csv.close()
	quit()


func _sample(sim: CombatSimulation, skel: Skeleton3D, anim: FighterAnimator) -> void:
	_frame += 1
	if skel == null:
		return
	var f: FighterState = sim.fighters[0]
	var state: String = "%s %s" % [f.action_name(), String(anim.current) if anim != null else ""]
	var changed: bool = state != _prev_state
	if changed:
		print("STATE f%d tick %d  %s -> %s" % [_frame, sim.tick, _prev_state, state])
	var pos: Dictionary = {}
	for j: String in JOINTS:
		var seen: Dictionary = _probe.get("poses") if _probe != null else {}
		if seen.has(j):
			pos[j] = skel.global_transform * (seen[j] as Transform3D).origin
			if j.ends_with("Foot"):
				# the ball of the foot (as FootLockModifier3D finds it): the point that must not slide
				var rest: Transform3D = skel.get_bone_global_rest(skel.find_bone(j))
				var ball_local: Vector3 = rest.affine_inverse() * Vector3(rest.origin.x, 0.0, rest.origin.z + 0.12)
				pos[j.replace("Foot", "Ball")] = skel.global_transform * ((seen[j] as Transform3D) * ball_local)
		else:
			var idx: int = skel.find_bone(j)
			if idx < 0:
				continue
			pos[j] = skel.global_transform * skel.get_bone_global_pose(idx).origin
	if not _worst.has(state):
		_worst[state] = [0.0, 0.0]
	var frozen: bool = sim.hitstop_remaining > 0
	if not _prev.is_empty():
		for j: String in pos:
			if not _prev.has(j):
				continue
			var d: float = (pos[j] - _prev[j]).length() * 100.0
			_worst[state][0] = maxf(_worst[state][0], d)
			if d > JUMP_CM:
				print("JUMP  f%d %-12s %5.1f cm  %s%s" % [_frame, j, d, state, "  (state change)" if changed else ""])
		for side: String in ["Left", "Right"]:
			var foot: String = side + "Foot"
			var toe: String = side + "ToeBase"
			if not pos.has(foot) or not _prev.has(foot):
				continue
			var ball: String = side + "Ball"
			if not pos.has(ball) or not _prev.has(ball):
				continue
			if pos[ball].y * 100.0 > FLOOR_CM or _prev[ball].y * 100.0 > FLOOR_CM:
				continue                          # not on the floor
			var key: String = ball
			var dx: float = absf(pos[key].x - _prev[key].x) * 100.0
			_worst[state][1] = maxf(_worst[state][1], dx)
			if dx > SLIDE_CM and not frozen:
				print("SLIDE f%d %-12s %5.1f cm  %s" % [_frame, key, dx, state])
	if _csv != null:
		var row: PackedStringArray = [str(_frame), str(sim.tick), state.replace(",", ";"), str(f.move_frame)]
		for j: String in JOINTS:
			var p: Vector3 = pos.get(j, Vector3.ZERO)
			row.append("%.4f;%.4f;%.4f" % [p.x, p.y, p.z])
		_csv.store_line(",".join(row))
	_prev = pos
	_prev_state = state
