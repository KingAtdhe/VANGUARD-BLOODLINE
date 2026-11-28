extends SkeletonModifier3D
## Last modifier on a skeleton: records the bones' global poses as they are
## after every other modifier (what the player sees). Modifier results are not
## visible to get_bone_global_pose() outside the modifier stack (D-145).

var joints: PackedStringArray = []
var poses: Dictionary = {}           # name -> Transform3D (skeleton space)


func _process_modification_with_delta(_delta: float) -> void:
	var sk: Skeleton3D = get_skeleton()
	if sk == null:
		return
	for j: String in joints:
		var i: int = sk.find_bone(j)
		if i >= 0:
			poses[j] = sk.get_bone_global_pose(i)
