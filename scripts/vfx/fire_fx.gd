class_name FireFX
extends RefCounted
## Fire effects built from the owner's red flame sheet (assets/vfx/fire, cut
## from the sheet by tools/art/cut_fire_sheet.py; D-101). Presentation only.
##
## Real flames rather than tinted shapes: every flame is a particle carrying
## one of the six hand-drawn flame frames (a flipbook), drawn additively so
## the black of the sheet is transparent. Each flame is born small, swells,
## rises, flickers through the frames, shrinks and fades; the emitter leaves
## its flames behind in the world (local_coords off), so a moving fist or
## foot drags a trail of fire. CPU particles: they run on every Mobile-
## renderer device and in the headless review renders.

const FLIPBOOK: Texture2D = preload("res://assets/vfx/fire/flame_flipbook.png")
const FIREBALL: Texture2D = preload("res://assets/vfx/fire/fireball.png")
const BURST: Texture2D = preload("res://assets/vfx/fire/burst.png")
const EMBER: Texture2D = preload("res://assets/vfx/fire/ember.png")
const FLIP_FRAMES: int = 6

const FLAME_SHADER: Shader = preload("res://assets/vfx/fire/flame_particles.gdshader")
const NOISE: Texture2D = preload("res://assets/vfx/fire/noise.png")

static var _flame_mat: ShaderMaterial = null
static var _ember_mat: StandardMaterial3D = null


## Additive, unshaded, never casts or receives shadows.
static func additive(tex: Texture2D, particles: bool, frames: int = 1) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.albedo_texture = tex
	m.disable_receive_shadows = true
	m.vertex_color_use_as_albedo = true
	if particles:
		m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		m.billboard_keep_scale = true
		m.particles_anim_h_frames = frames
		m.particles_anim_v_frames = 1
		m.particles_anim_loop = true
	return m


## The flame look (D-107): the fire shader (frame cross-fades, heat shimmer,
## core-to-edge fire colours) on the owner's flipbook.
static func flame_material() -> ShaderMaterial:
	if _flame_mat == null:
		_flame_mat = ShaderMaterial.new()
		_flame_mat.shader = FLAME_SHADER
		_flame_mat.set_shader_parameter("flipbook", FLIPBOOK)
		_flame_mat.set_shader_parameter("noise_tex", NOISE)
		_flame_mat.set_shader_parameter("frames", FLIP_FRAMES)
	return _flame_mat


static func ember_material() -> StandardMaterial3D:
	if _ember_mat == null:
		_ember_mat = additive(EMBER, true, 1)
	return _ember_mat


## A source of rising flames. [param size]: one flame's height in metres;
## [param amount]: flames alive at once; [param radius]: how widely they are
## born around the emitter. Starts switched off.
static func flames(size: float, amount: int, lifetime: float = 0.42, radius: float = 0.05,
		rise: float = 1.1) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.name = "Flames"
	var q := QuadMesh.new()
	q.size = Vector2(size * 0.8, size)
	q.center_offset = Vector3(0.0, size * 0.32, 0.0)   # the sprite's flame sits at its bottom: grow up from the point
	q.material = flame_material()
	p.mesh = q
	p.amount = amount
	p.lifetime = lifetime
	p.local_coords = false
	p.emitting = false
	p.randomness = 0.6
	p.lifetime_randomness = 0.35
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = radius
	p.direction = Vector3.UP
	p.spread = 22.0
	p.initial_velocity_min = rise * 0.35
	p.initial_velocity_max = rise * 0.8
	p.gravity = Vector3(0.0, rise * 1.6, 0.0)        # hot air: flames speed up as they rise
	p.damping_min = 0.5
	p.damping_max = 1.5
	p.angle_min = -18.0
	p.angle_max = 18.0
	p.scale_amount_min = 0.65
	p.scale_amount_max = 1.15
	var sc := Curve.new()
	sc.add_point(Vector2(0.0, 0.35))
	sc.add_point(Vector2(0.25, 1.0))
	sc.add_point(Vector2(0.7, 0.75))
	sc.add_point(Vector2(1.0, 0.15))
	p.scale_amount_curve = sc
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 1.0, 1.0, 1.0))
	g.set_color(1, Color(0.35, 0.0, 0.0, 0.0))
	g.add_point(0.55, Color(1.0, 0.75, 0.7, 0.85))
	p.color_ramp = g
	p.anim_speed_min = 1.0                            # one pass through the six frames per life (~14 fps)
	p.anim_speed_max = 1.6
	p.anim_offset_min = 0.0
	p.anim_offset_max = 1.0
	return p


## Sparks thrown up out of a fire. Starts switched off.
static func embers(amount: int, lifetime: float = 0.7, radius: float = 0.06, speed: float = 1.2) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.name = "Embers"
	var q := QuadMesh.new()
	q.size = Vector2(0.035, 0.035)
	q.material = ember_material()
	p.mesh = q
	p.amount = amount
	p.lifetime = lifetime
	p.local_coords = false
	p.emitting = false
	p.randomness = 1.0
	p.lifetime_randomness = 0.5
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = radius
	p.direction = Vector3.UP
	p.spread = 55.0
	p.initial_velocity_min = speed * 0.4
	p.initial_velocity_max = speed
	p.gravity = Vector3(0.0, 0.8, 0.0)
	p.scale_amount_min = 0.5
	p.scale_amount_max = 1.4
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 0.9, 0.7, 1.0))
	g.set_color(1, Color(0.6, 0.0, 0.0, 0.0))
	p.color_ramp = g
	return p


## A flame source (flames + embers) under [param parent]; returns the node
## holding both, switched off. Turn it on and off with [method set_burning].
## [param glow] > 0: a warm light that the fire throws on the body and floor
## (light energy), on while burning.
static func fire_source(size: float, amount: int, radius: float = 0.05, glow: float = 0.0) -> Node3D:
	var n := Node3D.new()
	n.name = "FireSource"
	# two layers: a bright, tight core and larger, slower outer flames
	n.add_child(flames(size * 0.5, maxi(3, amount / 3), 0.28, radius * 0.6, 1.4))
	n.add_child(flames(size, amount, 0.48, radius))
	n.add_child(embers(maxi(4, amount / 2), 0.7, radius))
	if glow > 0.0:
		var l := OmniLight3D.new()
		l.name = "Glow"
		l.light_color = Color(1.0, 0.42, 0.14)
		l.light_energy = glow
		l.omni_range = 1.1
		l.shadow_enabled = false
		l.visible = false
		n.add_child(l)
	return n


static func set_burning(source: Node, on: bool) -> void:
	if source == null:
		return
	for c: Node in source.get_children():
		if c is CPUParticles3D:
			(c as CPUParticles3D).emitting = on
		elif c is OmniLight3D:
			(c as OmniLight3D).visible = on


## A flat textured quad facing the side camera (a sprite on the fighting plane).
static func sprite(tex: Texture2D, size: Vector2) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = size
	mi.mesh = q
	var m := additive(tex, false)
	m.vertex_color_use_as_albedo = false
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi
