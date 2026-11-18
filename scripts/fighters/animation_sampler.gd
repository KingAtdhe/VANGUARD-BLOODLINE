class_name AnimationSampler
extends RefCounted
## Applies an Animation to a Skeleton3D at an exact time, without an
## AnimationPlayer. Used by tests/tools to measure poses deterministically
## (e.g. "is the fist inside the hitbox on the active frame?").


static func apply(anim: Animation, skeleton: Skeleton3D, time: float) -> void:
	for t: int in anim.get_track_count():
		var path: NodePath = anim.track_get_path(t)
		if path.get_subname_count() == 0:
			continue
		var bone: int = skeleton.find_bone(path.get_concatenated_subnames())
		if bone < 0:
			continue
		match anim.track_get_type(t):
			Animation.TYPE_POSITION_3D:
				skeleton.set_bone_pose_position(bone, anim.position_track_interpolate(t, time))
			Animation.TYPE_ROTATION_3D:
				skeleton.set_bone_pose_rotation(bone, anim.rotation_track_interpolate(t, time))
			Animation.TYPE_SCALE_3D:
				skeleton.set_bone_pose_scale(bone, anim.scale_track_interpolate(t, time))
	skeleton.force_update_all_bone_transforms()


## Time (seconds) of 1-based move frame [param frame] (frame 1 == time 0).
static func time_of_frame(frame: int) -> float:
	return (frame - 1) / float(CombatConstants.TICK_RATE)


## Skeleton-space transform of [param bone], composed from local bone poses
## (does not rely on the skeleton's cached global poses, which are only
## refreshed on frame processing).
static func bone_global(skeleton: Skeleton3D, bone: int) -> Transform3D:
	var t: Transform3D = skeleton.get_bone_pose(bone)
	var parent: int = skeleton.get_bone_parent(bone)
	while parent >= 0:
		t = skeleton.get_bone_pose(parent) * t
		parent = skeleton.get_bone_parent(parent)
	return t
