class_name HitReactModifier3D
extends SkeletonModifier3D
## Procedural impact recoil (D-145): when a hit lands, the struck part of the
## body snaps away from the blow on the impact frame and springs back, on top
## of whatever hit-reaction clip is playing.
##
## Why: the reaction clips need a frame or two to blend in, and during the
## global hit-stop the clip is frozen, so the victim showed the hit only a few
## frames late, as a pose, not as an impact. Real fighting games sell the
## contact frame itself: the head or chest is thrown back at once, it overshoots
## and settles. This runs as a SkeletonModifier3D after the AnimationPlayer
## (and keeps running through the hit-stop, so the impact reads during the
## freeze), and is presentation only: the simulation never reads it.
##
## How: one damped spring per strength (angle in radians), split over the
## spine chain by where the blow landed: a head hit throws Neck and Head, a
## body hit folds Spine and Chest. The kick is an impulse on the spring's
## velocity, so the snap is immediate and the return is a decaying oscillation
## (one small overshoot), never a pop.

## Spring stiffness (1/s^2) and damping (1/s): ~0.25 s to settle with one
## small overshoot (damping ratio ~0.45).
const STIFFNESS: float = 420.0
const DAMPING: float = 18.0
## The largest recoil angle (rad): a heavy counter hit, about 26 degrees.
const MAX_ANGLE: float = 0.45

## Height (m above the fighter's floor) above which a hit is a head hit.
const HEAD_HEIGHT: float = 1.35

var _bones: Dictionary = {}           # name -> index
var _angle: float = 0.0               # current recoil, radians (+ = away from the blow)
var _vel: float = 0.0
var _twist: float = 0.0               # a small turn away from the striking side
var _twist_vel: float = 0.0
var _head: float = 0.5                # 1 = all in the head and neck, 0 = all in the spine
var _side: float = 1.0                # which way the blow pushes, in skeleton space (+Z or -Z)


func _ready() -> void:
	_find()


func _find() -> void:
	_bones.clear()
	var sk: Skeleton3D = get_skeleton()
	if sk == null:
		return
	for n: String in ["Spine", "Chest", "Neck", "Head"]:
		var i: int = sk.find_bone(n)
		if i >= 0:
			_bones[n] = i


## A hit landed. [param strength] 0..1 (light jab ~0.25, heavy ~0.6, counter
## or ultimate 1); [param height] metres above the floor; [param from_front]
## true when the blow comes from the direction the fighter faces.
func impact(strength: float, height: float, from_front: bool = true) -> void:
	var s: float = clampf(strength, 0.0, 1.0)
	_head = clampf((height - 1.0) / (HEAD_HEIGHT - 1.0), 0.0, 1.0)
	_side = 1.0 if from_front else -1.0
	# an impulse on the velocity: the snap happens on the very next frame
	_vel += s * 14.0
	_twist_vel += s * 6.0 * (1.0 if randf() < 0.5 else -1.0)


func _process_modification_with_delta(delta: float) -> void:
	var sk: Skeleton3D = get_skeleton()
	if sk == null:
		return
	if _bones.is_empty():
		_find()
	# semi-implicit Euler, sub-stepped so a slow frame cannot blow it up
	var steps: int = maxi(1, ceili(delta / (1.0 / 120.0)))
	var h: float = delta / float(steps)
	for _i: int in steps:
		_vel += (-STIFFNESS * _angle - DAMPING * _vel) * h
		_angle = clampf(_angle + _vel * h, -MAX_ANGLE, MAX_ANGLE)
		_twist_vel += (-STIFFNESS * _twist - DAMPING * _twist_vel) * h
		_twist = clampf(_twist + _twist_vel * h, -MAX_ANGLE * 0.5, MAX_ANGLE * 0.5)
	if absf(_angle) < 0.0005 and absf(_vel) < 0.005 and absf(_twist) < 0.0005:
		_angle = 0.0
		_vel = 0.0
		_twist = 0.0
		return
	# share of the recoil per bone: the spine folds on body hits, the neck and
	# head snap on head hits; the total is the spring's angle
	var share: Dictionary = {
		"Spine": 0.35 * (1.0 - _head), "Chest": 0.65 * (1.0 - _head) + 0.25 * _head,
		"Neck": 0.30 * _head, "Head": 0.45 * _head,
	}
	for n: String in share:
		if not _bones.has(n):
			continue
		var i: int = _bones[n]
		var w: float = share[n]
		if w <= 0.0:
			continue
		var g: Transform3D = sk.get_bone_global_pose(i)
		# skeleton space: +Z is the way the model faces, +Y up; a blow from the
		# front tips the bone back about the side (X) axis
		var r := Basis(Vector3.RIGHT, -_angle * w * _side) * Basis(Vector3.UP, _twist * w)
		sk.set_bone_global_pose(i, Transform3D(r * g.basis, g.origin))
		# children follow through the skeleton's own pose propagation on the next bone
