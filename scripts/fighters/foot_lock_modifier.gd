class_name FootLockModifier3D
extends SkeletonModifier3D
## Planted-foot locking (D-145): a runtime two-bone IK on both legs that keeps
## a foot which is on the floor exactly where it touched down, in WORLD space.
##
## Why: the clips are keyed with planted feet, but in play the pose is also
## blended (walk -> stance, stance -> attack), seeked from the simulation and
## carried by the game's own movement. The gameplay audit (tools/godot/
## gameplay_audit.gd) measured feet sliding 4-5 cm a frame for several frames
## whenever a walk started or stopped, and on the frame each step lands.
## No keyframe fix removes slides that come from blending; this does.
##
## How: runs as a SkeletonModifier3D after the AnimationPlayer has posed the
## skeleton. For each leg it finds the ball of the foot; when the ball is on
## the floor (below FLOOR_Y) it remembers that world spot; while it stays down,
## the leg is re-solved (thigh and shin turned in the knee's own plane, the
## foot keeps its animated orientation) so the ball stays on the spot. When
## the animation lifts the foot, or the locked spot falls too far behind
## (MAX_OFFSET, e.g. a dash), the correction is faded out over RELEASE_TIME so
## nothing snaps. Presentation only: the simulation never reads it.

const FLOOR_Y: float = 0.03           # ball of the foot this close to the floor = planted
const LIFT_Y: float = 0.042          # and released above this (hysteresis): a keyed step lifts 4-5 cm
## A lock further than this from the animated foot lets go with a STEP: the
## foot is lifted (STEP_LIFT, a sine arc) while it catches up with the clip,
## so the body re-plants it the way a fighter would, instead of dragging it
## along the floor (a slide) or letting it snap (19 cm in one frame, audit).
const MAX_OFFSET: float = 0.08
const STEP_LIFT: float = 0.045
const RELEASE_TIME: float = 0.09
const ENGAGE_TIME: float = 0.012      # a foot that touches down stops at once (contact), it does not ease in
## The animated ball moving faster than this along the floor (world space,
## after the game's own movement) is a foot the clip means to move: a step
## that skims the floor, a pivot. It is not locked, and a lock lets go of it.
## Blend slides (walk <-> stance) run 1-3.5 m/s and must stay locked; a step or pivot is faster.
const STEP_SPEED: float = 3.6

## Set by FighterView every frame: false in the air, lying down or when a
## clip moves the whole body on purpose.
var lock_enabled: bool = true
## The floor height in world space (the arena floor).
var floor_y: float = 0.0

var _legs: Array[Dictionary] = []
var _debug: bool = OS.get_environment("DEBUG_FOOT_LOCK") != ""


func _ready() -> void:
	_setup()


func _setup() -> void:
	_legs.clear()
	var sk: Skeleton3D = get_skeleton()
	if sk == null:
		return
	for side: String in ["Left", "Right"]:
		var up: int = sk.find_bone(side + "UpperLeg")
		var low: int = sk.find_bone(side + "LowerLeg")
		var foot: int = sk.find_bone(side + "Foot")
		if up < 0 or low < 0 or foot < 0:
			continue
		var rest_foot: Transform3D = sk.get_bone_global_rest(foot)
		# the ball of the foot at rest: down to the sole, forward toward the toes
		# (model space: forward +Z). Kept in the foot bone's own frame.
		var ball_model := Vector3(rest_foot.origin.x, 0.0, rest_foot.origin.z + 0.12)
		_legs.append({
			"up": up, "low": low, "foot": foot,
			"ball_local": rest_foot.affine_inverse() * ball_model,
			"l1": (sk.get_bone_global_rest(low).origin - sk.get_bone_global_rest(up).origin).length(),
			"l2": (rest_foot.origin - sk.get_bone_global_rest(low).origin).length(),
			"locked": false, "spot": Vector3.ZERO, "w": 0.0,
		})


func _process_modification_with_delta(delta: float) -> void:
	var sk: Skeleton3D = get_skeleton()
	if sk == null:
		return
	if _legs.is_empty():
		_setup()
	var to_world: Transform3D = sk.global_transform
	var to_skel: Transform3D = to_world.affine_inverse()
	for leg: Dictionary in _legs:
		var g_up: Transform3D = sk.get_bone_global_pose(leg["up"])
		var g_low: Transform3D = sk.get_bone_global_pose(leg["low"])
		var g_foot: Transform3D = sk.get_bone_global_pose(leg["foot"])
		var ball_w: Vector3 = to_world * (g_foot * (leg["ball_local"] as Vector3))
		var h: float = ball_w.y - floor_y
		var prev: Vector3 = leg.get("prev", ball_w)
		leg["prev"] = ball_w
		var speed: float = Vector2(ball_w.x - prev.x, ball_w.z - prev.z).length() / maxf(delta, 0.001)
		var stepping: bool = speed > STEP_SPEED
		# planted / lifted, with hysteresis
		if lock_enabled and not leg["locked"] and h < FLOOR_Y and not stepping and not leg.get("step", false):
			leg["locked"] = true
			leg["spot"] = ball_w
		elif leg["locked"] and (not lock_enabled or h > LIFT_Y or stepping):
			leg["locked"] = false
			leg["step"] = false
		var want: Vector3 = Vector3.ZERO
		if leg["locked"]:
			var spot: Vector3 = leg["spot"]
			want = Vector3(spot.x - ball_w.x, 0.0, spot.z - ball_w.z)
			if want.length() > MAX_OFFSET:
				leg["locked"] = false
				leg["step"] = true          # catch up in the air, not along the floor
				want = want.normalized() * MAX_OFFSET
			leg["last"] = want
		if _debug:
			print("FL %d %s h=%.3f v=%.2f lock=%s w=%.2f off=%.3f" % [Engine.get_physics_frames(), sk.get_bone_name(leg["foot"]), h, speed, leg["locked"], leg["w"], want.length()])
		var target_w: float = 1.0 if leg["locked"] else 0.0
		var rate: float = delta / (ENGAGE_TIME if target_w > leg["w"] else RELEASE_TIME)
		leg["w"] = move_toward(leg["w"], target_w, rate)
		if leg["w"] <= 0.001:
			leg["step"] = false             # the catch-up step is over: it may plant again
			continue
		var off: Vector3 = (want if leg["locked"] else leg.get("last", Vector3.ZERO)) * float(leg["w"])
		if not leg["locked"] and leg.get("step", false):
			# 0 -> lift -> 0 over the catch-up: w runs 1 -> 0
			off.y += STEP_LIFT * sin(PI * (1.0 - float(leg["w"])))
		if off.length_squared() < 1e-8:
			continue
		# the ankle moves with the ball (the foot keeps its animated orientation)
		var hip: Vector3 = g_up.origin
		var knee: Vector3 = g_low.origin
		var ankle: Vector3 = g_foot.origin
		var target: Vector3 = ankle + to_skel.basis * off
		_solve(sk, leg, hip, knee, ankle, target, g_up, g_low, g_foot)


## Two-bone IK in the knee's own plane: the knee stays on the side it bends to
## in the animation; lengths are the bones' own.
func _solve(sk: Skeleton3D, leg: Dictionary, hip: Vector3, knee: Vector3, ankle: Vector3, target: Vector3,
		g_up: Transform3D, g_low: Transform3D, g_foot: Transform3D) -> void:
	var l1: float = leg["l1"]
	var l2: float = leg["l2"]
	var to_t: Vector3 = target - hip
	var d: float = clampf(to_t.length(), absf(l1 - l2) + 0.001, l1 + l2 - 0.001)
	var dir: Vector3 = to_t.normalized()
	# the bend direction: the animated knee's offset from the hip-ankle line
	var bend: Vector3 = (knee - hip) - dir * (knee - hip).dot(dir)
	if bend.length_squared() < 1e-8:
		bend = Vector3(0, 0, 1) - dir * dir.z
	bend = bend.normalized()
	var a: float = (l1 * l1 - l2 * l2 + d * d) / (2.0 * d)
	var hgt: float = sqrt(maxf(0.0, l1 * l1 - a * a))
	var new_knee: Vector3 = hip + dir * a + bend * hgt
	var new_ankle: Vector3 = hip + dir * d
	# turn the thigh from its animated direction onto the new one, then the shin
	var r1: Quaternion = Quaternion((knee - hip).normalized(), (new_knee - hip).normalized())
	var up_t := Transform3D(Basis(r1) * g_up.basis, hip)
	sk.set_bone_global_pose(leg["up"], up_t)
	var shin_old: Vector3 = (Basis(r1) * (ankle - knee)).normalized()
	var r2: Quaternion = Quaternion(shin_old, (new_ankle - new_knee).normalized())
	var low_t := Transform3D(Basis(r2) * Basis(r1) * g_low.basis, new_knee)
	sk.set_bone_global_pose(leg["low"], low_t)
	# the foot keeps its animated orientation in the world: flat stays flat
	sk.set_bone_global_pose(leg["foot"], Transform3D(g_foot.basis, new_ankle))
