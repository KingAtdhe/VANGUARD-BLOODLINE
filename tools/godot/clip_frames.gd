extends SceneTree
## Every frame of some animations of a fighter as separate pictures, seen
## from the side as the game shows them (D-091). tools/review_video.py turns
## them into a real-speed video for the owner to judge motion, which a
## contact sheet cannot show.
##
##   xvfb-run -a godot --path . --rendering-driver opengl3 --script res://tools/godot/clip_frames.gd \
##         -- <fighter_id> <out_dir> <SUFFIX,SUFFIX,...> [size_px]
## Writes <out_dir>/<SUFFIX>/0001.png ... one per 60 Hz frame. The jump and
## the jumping attack are lifted along the fighter's own jump arc, as the
## game does. The fighter faces +X, as P1 does in a match. Needs a display.

const CAM_DISTANCE: float = 5.9
const CAM_HEIGHT: float = 1.5


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var fighter: String = a[0]
	var out_dir: String = a[1]
	var names: PackedStringArray = a[2].split(",")
	var size: int = int(a[3]) if a.size() > 3 else 520
	root.size = Vector2i(size, size)
	var def: FighterDefinition = load("res://data/fighters/%s.tres" % fighter)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.36, 0.38, 0.42)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(1, 1, 1)
	env.environment.ambient_light_energy = 0.75
	root.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, 35, 0)
	root.add_child(sun)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(8, 4)
	floor_mesh.mesh = plane
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.22, 0.23, 0.26)
	floor_mesh.material_override = floor_mat
	root.add_child(floor_mesh)
	var model: Node3D = def.model_scene.instantiate()
	ModelUtil.prepare(model)
	model.rotation.y = deg_to_rad(90.0)       # faces +X, like P1 in a match
	root.add_child(model)
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var cam := Camera3D.new()
	cam.fov = 30.0
	root.add_child(cam)
	cam.make_current()
	cam.position = Vector3(0.25, CAM_HEIGHT, CAM_DISTANCE)
	cam.look_at(Vector3(0.25, CAM_HEIGHT, 0.0), Vector3.UP)
	await process_frame
	var m: FighterMovementProfile = def.movement
	for suffix: String in names:
		if suffix == "CROUCH_TRANSITION":
			# stance -> crouch -> stance with the game's own blend time
			await _transition(ap, model, fighter.to_upper(), out_dir, size)
			continue
		var anim: StringName = StringName("%s_%s" % [fighter.to_upper(), suffix])
		if ap == null or not ap.has_animation(anim):
			push_error("MISSING %s" % anim)
			continue
		ap.play(anim)
		ap.pause()
		var frames: int = int(round(ap.get_animation(anim).length * 60.0)) + 1
		DirAccess.make_dir_recursive_absolute("%s/%s" % [out_dir, suffix])
		for i: int in frames:
			ap.seek(i / 60.0, true)
			# the game lifts a jumping fighter; the clip only poses the body
			var lift: float = 0.0
			if suffix == "JUMP":
				lift = _arc(m, float(i - FighterAnimator.JUMP_CLIP_PREJUMP) / FighterAnimator.JUMP_CLIP_AIR)
			elif suffix == "JUMP_ATTACK":
				lift = _arc(m, (14.0 + i) / m.jump_air_ticks)
			model.position.y = lift
			for _f: int in 2:
				await process_frame
			await RenderingServer.frame_post_draw
			var shot: Image = root.get_texture().get_image()
			var side: int = mini(shot.get_width(), shot.get_height())
			shot = shot.get_region(Rect2i((shot.get_width() - side) / 2, (shot.get_height() - side) / 2, side, side))
			shot.resize(size, size, Image.INTERPOLATE_LANCZOS)
			shot.save_png("%s/%s/%04d.png" % [out_dir, suffix, i + 1])
		print("frames ", suffix, " ", frames)
	quit()


func _transition(ap: AnimationPlayer, model: Node3D, token: String, out_dir: String, size: int) -> void:
	var idle: StringName = StringName(token + "_IDLE_A")
	var crouch: StringName = StringName(token + "_CROUCH")
	for n: StringName in [idle, crouch]:
		ap.get_animation(n).loop_mode = Animation.LOOP_LINEAR
	DirAccess.make_dir_recursive_absolute("%s/CROUCH_TRANSITION" % out_dir)
	model.position.y = 0.0
	ap.play(idle)
	var down: StringName = StringName(token + "_CROUCH_DOWN")
	var up: StringName = StringName(token + "_CROUCH_UP")
	var keyed: bool = ap.has_animation(down) and ap.has_animation(up)
	var down_n: int = int(round(ap.get_animation(down).length * 60.0)) if keyed else 0
	var up_n: int = int(round(ap.get_animation(up).length * 60.0)) if keyed else 0
	for i: int in 110:
		if keyed:                                  # as FighterAnimator plays it (D-131)
			if i == 20:
				ap.play(down, FighterAnimator.BLEND_ATTACK)
			elif i == 20 + down_n:
				ap.play(crouch, FighterAnimator.BLEND_ATTACK)
			elif i == 70:
				ap.play(up, FighterAnimator.BLEND_ATTACK)
			elif i == 70 + up_n:
				ap.play(idle, FighterAnimator.BLEND_ATTACK)
		elif i == 20:
			ap.play(crouch, FighterAnimator.BLEND_CROUCH)
		elif i == 70:
			ap.play(idle, FighterAnimator.BLEND_CROUCH)
		ap.advance(1.0 / 60.0)
		for _f: int in 2:
			await process_frame
		await RenderingServer.frame_post_draw
		var shot: Image = root.get_texture().get_image()
		var side: int = mini(shot.get_width(), shot.get_height())
		shot = shot.get_region(Rect2i((shot.get_width() - side) / 2, (shot.get_height() - side) / 2, side, side))
		shot.resize(size, size, Image.INTERPOLATE_LANCZOS)
		shot.save_png("%s/CROUCH_TRANSITION/%04d.png" % [out_dir, i + 1])
	ap.pause()
	print("frames CROUCH_TRANSITION 110")


static func _arc(m: FighterMovementProfile, u: float) -> float:
	if u <= 0.0 or u >= 1.0:
		return 0.0
	return 4.0 * m.jump_height * u * (1.0 - u)
