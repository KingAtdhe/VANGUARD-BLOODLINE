extends SceneTree
## Rig inspection before animating (D-129, owner: "inspect the rig ... verify
## their rotation axes. Do not guess bone orientations. Test the leg movement
## with a small number of poses"). Prints, for the game model of a fighter:
##   1. the pelvis / spine / leg bones with parent, rest position and the
##      direction each bone points in (model space: forward +Z, his left +X,
##      up +Y);
##   2. an axis test: each leg and spine bone is turned 20 degrees about each
##      of its own three axes and the tool reports where the bone below it
##      moved, so the flexion axis and its sign are measured, not assumed;
##   3. pose tests: hip flexed 90 degrees, knee flexed 90 degrees, leg raised
##      to vertical, each built from the measured axes, with the ankle
##      position that results (a wrong axis would send it sideways).
##
##   godot --headless --path . --script res://tools/godot/rig_inspect.gd -- <fighter>
const CHAIN: Array = ["Root", "Hips", "Spine", "Chest", "Neck", "Head", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
	"RightUpperLeg", "RightLowerLeg", "RightFoot"]
const CHILD: Dictionary = {"Hips": "Spine", "Spine": "Chest", "Chest": "Neck", "Neck": "Head",
	"LeftUpperLeg": "LeftLowerLeg", "LeftLowerLeg": "LeftFoot", "RightUpperLeg": "RightLowerLeg", "RightLowerLeg": "RightFoot"}
var sk: Skeleton3D


func gpos(b: String) -> Vector3:
	return (sk.global_transform * sk.get_bone_global_pose(sk.find_bone(b))).origin


func name_dir(v: Vector3) -> String:
	var parts: Array[String] = []
	if absf(v.z) > 0.02:
		parts.append("%s %.2f" % ["forward" if v.z > 0 else "back", absf(v.z)])
	if absf(v.y) > 0.02:
		parts.append("%s %.2f" % ["up" if v.y > 0 else "down", absf(v.y)])
	if absf(v.x) > 0.02:
		parts.append("%s %.2f" % ["to his left" if v.x > 0 else "to his right", absf(v.x)])
	return ", ".join(parts) if parts.size() > 0 else "no movement"


func turn(b: String, axis: Vector3, deg: float) -> void:
	var i: int = sk.find_bone(b)
	sk.set_bone_pose_rotation(i, sk.get_bone_rest(i).basis.get_rotation_quaternion() * Quaternion(axis, deg_to_rad(deg)))
	sk.force_update_all_bone_transforms()


func reset() -> void:
	sk.reset_bone_poses()
	sk.force_update_all_bone_transforms()


func flex_axis(b: String, want: Vector3) -> Array:
	## the local axis (and sign) of bone b whose rotation moves its child most along `want`
	var best: Array = [Vector3.RIGHT, 1.0, -1.0]
	var child: String = CHILD[b]
	for ax: Vector3 in [Vector3.RIGHT, Vector3.UP, Vector3.BACK]:
		for sg: float in [1.0, -1.0]:
			reset()
			var p0: Vector3 = gpos(child)
			turn(b, ax, 20.0 * sg)
			var d: float = (gpos(child) - p0).dot(want)
			if d > best[2]:
				best = [ax, sg, d]
	reset()
	return best


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var fighter: String = a[0] if a.size() > 0 else "kairo"
	var def: FighterDefinition = load("res://data/fighters/%s.tres" % fighter)
	var model: Node3D = def.model_scene.instantiate()
	root.add_child(model)
	for n: Node in model.find_children("*", "Skeleton3D", true, false):
		sk = n as Skeleton3D
	await process_frame
	reset()
	print("RIG %s: %d bones, one deform skeleton, no control or IK bones (animation is baked per bone)" % [fighter, sk.get_bone_count()])
	print("\n1. Bones (rest pose; model space: forward +Z, his left +X, up +Y)")
	for b: String in CHAIN:
		var i: int = sk.find_bone(b)
		if i < 0:
			print("  MISSING %s" % b)
			continue
		var par: int = sk.get_bone_parent(i)
		var p: Vector3 = gpos(b)
		var line: String = "  %-14s parent %-14s at (x %.2f, up %.2f, fwd %.2f)" % [b, sk.get_bone_name(par) if par >= 0 else "-", p.x, p.y, p.z]
		if CHILD.has(b):
			var d: Vector3 = gpos(CHILD[b]) - p
			line += "  length %.3f  points %s" % [d.length(), name_dir(d.normalized())]
		print(line)
	print("\n2. Axis test: each bone turned +20 degrees about its own X, Y, Z; where the next joint down moved")
	var axes: Dictionary = {"X": Vector3.RIGHT, "Y": Vector3.UP, "Z": Vector3.BACK}
	for b: String in ["Hips", "Spine", "Chest", "RightUpperLeg", "RightLowerLeg", "LeftUpperLeg", "LeftLowerLeg"]:
		for k: String in axes:
			reset()
			var p0: Vector3 = gpos(CHILD[b])
			turn(b, axes[k], 20.0)
			print("  %-14s +%s: %-9s moves %s" % [b, k, CHILD[b], name_dir(gpos(CHILD[b]) - p0)])
	reset()
	print("\n3. Measured flexion axes (used by the pose tests; nothing assumed)")
	var hipf: Dictionary = {}
	var kneef: Dictionary = {}
	for side: String in ["Right", "Left"]:
		hipf[side] = flex_axis(side + "UpperLeg", Vector3(0, 0, 1))        # thigh forward
		kneef[side] = flex_axis(side + "LowerLeg", Vector3(0, 0, -1))      # shin back = knee flexion
		print("  %s hip flexion (thigh forward): local %s, sign %+d   |   %s knee flexion (heel back): local %s, sign %+d" % [
			side, hipf[side][0], int(hipf[side][1]), side, kneef[side][0], int(kneef[side][1])])
	print("\n4. Pose tests on the right leg (ankle relative to the hip joint)")
	var tests: Array = [["standing (rest)", 0.0, 0.0], ["hip flexed 90, knee straight (leg level in front)", 90.0, 0.0],
		["hip flexed 90, knee flexed 90 (chamber)", 90.0, 90.0], ["hip flexed 170, knee straight (leg up, axe-kick peak)", 170.0, 0.0],
		["hip flexed 45, knee flexed 30", 45.0, 30.0]]
	for t: Array in tests:
		reset()
		turn("RightUpperLeg", hipf["Right"][0], t[1] * hipf["Right"][1])
		turn("RightLowerLeg", kneef["Right"][0], t[2] * kneef["Right"][1])
		var rel: Vector3 = gpos("RightFoot") - gpos("RightUpperLeg")
		var thigh: Vector3 = gpos("RightLowerLeg") - gpos("RightUpperLeg")
		var shin: Vector3 = gpos("RightFoot") - gpos("RightLowerLeg")
		print("  %-52s ankle fwd %+.2f, up %+.2f, sideways %+.2f   knee bend %.0f" % [t[0], rel.z, rel.y, rel.x, rad_to_deg(thigh.angle_to(shin))])
	reset()
	quit()
