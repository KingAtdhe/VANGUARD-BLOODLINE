class_name ImpactFX
extends RefCounted
## Hit, block and knockdown effects (D-102). Presentation only.
##
## White textures (tools/art/make_impact_textures.py) tinted per use, drawn
## additively (light: flashes, sparks, rings, slashes) or blended (smoke,
## debris). Every piece is short-lived and fire-and-forget: a sprite grows
## and fades (EffectsManager animates it), particles are one-shot bursts that
## free themselves.

const STAR: Texture2D = preload("res://assets/vfx/impact/impact_star.png")
const RING: Texture2D = preload("res://assets/vfx/impact/shock_ring.png")
const GLOW: Texture2D = preload("res://assets/vfx/impact/glow.png")
const SPARK: Texture2D = preload("res://assets/vfx/impact/spark.png")
const SMOKE: Texture2D = preload("res://assets/vfx/impact/smoke.png")
const DEBRIS: Texture2D = preload("res://assets/vfx/impact/debris.png")
const SLASH: Texture2D = preload("res://assets/vfx/impact/slash.png")

## Hit colours: a normal hit is white-gold, a counter-hit red-orange, a block
## cold blue.
const HIT_TINT := Color(1.0, 0.62, 0.22)
const COUNTER_TINT := Color(1.0, 0.32, 0.16)
const BLOCK_TINT := Color(0.45, 0.78, 1.0)
const DUST_TINT := Color(0.5, 0.44, 0.37, 0.95)


static func _mat(tex: Texture2D, additive: bool, billboard: bool, frames_h: int = 1, frames_v: int = 1) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD if additive else BaseMaterial3D.BLEND_MODE_MIX
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.albedo_texture = tex
	m.vertex_color_use_as_albedo = true
	m.disable_receive_shadows = true
	if billboard:
		m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		m.billboard_keep_scale = true
		if frames_h * frames_v > 1:
			m.particles_anim_h_frames = frames_h
			m.particles_anim_v_frames = frames_v
			m.particles_anim_loop = false
	return m


## A flat quad on the fighting plane (faces the side camera), tinted.
static func sprite(tex: Texture2D, size: Vector2, tint: Color, additive: bool = true) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = size
	mi.mesh = q
	var m := _mat(tex, additive, false)
	m.vertex_color_use_as_albedo = false
	m.albedo_color = tint
	m.no_depth_test = additive          # light effects are never hidden inside a body
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


## A flat quad lying on the floor (a ground ring).
static func floor_sprite(tex: Texture2D, size: float, tint: Color) -> MeshInstance3D:
	var mi := sprite(tex, Vector2(size, size), tint)
	(mi.material_override as StandardMaterial3D).no_depth_test = false
	mi.rotation.x = -PI * 0.5
	return mi


static func _gradient(c0: Color, c1: Color) -> Gradient:
	var g := Gradient.new()
	g.set_color(0, c0)
	g.set_color(1, c1)
	return g


## Streaking sparks thrown out of a hit, mostly away from the attacker
## ([param dir] = +1/-1 along X), falling as they fly. Aligned to their
## velocity so each reads as a short bright line.
static func sparks(count: int, speed: float, dir: float, tint: Color, spread: float = 55.0) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.name = "Sparks"
	var q := QuadMesh.new()
	q.size = Vector2(0.04, 0.34)
	var m := _mat(SPARK, true, false)
	q.material = m
	p.mesh = q
	p.amount = count
	p.lifetime = 0.32
	p.one_shot = true
	p.explosiveness = 1.0
	p.randomness = 0.8
	p.lifetime_randomness = 0.5
	p.local_coords = false
	p.particle_flag_align_y = true
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.direction = Vector3(dir, 0.25, 0.0)
	p.spread = spread
	p.flatness = 0.85                   # mostly in the fighting plane, where the camera sees them best
	p.initial_velocity_min = speed * 0.45
	p.initial_velocity_max = speed
	p.gravity = Vector3(0.0, -9.0, 0.0)
	p.damping_min = 2.0
	p.damping_max = 5.0
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.3
	var sc := Curve.new()
	sc.add_point(Vector2(0.0, 1.0))
	sc.add_point(Vector2(1.0, 0.2))
	p.scale_amount_curve = sc
	p.color_ramp = _gradient(Color(1.0, 0.95, 0.8, 1.0).lerp(tint, 0.15), Color(tint.r, tint.g * 0.45, tint.b * 0.3, 0.0))
	return p


## Dust rolling out along the floor from [param at] (a knockdown slam).
static func dust(count: int, size: float, reach: float) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.name = "Dust"
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	q.material = _mat(SMOKE, false, true)
	p.mesh = q
	p.amount = count
	p.lifetime = 0.9
	p.one_shot = true
	p.explosiveness = 0.95
	p.randomness = 0.7
	p.lifetime_randomness = 0.4
	p.local_coords = false
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = 0.12
	p.direction = Vector3(1.0, 0.18, 0.0)
	p.spread = 180.0
	p.flatness = 0.55
	p.initial_velocity_min = reach * 0.6
	p.initial_velocity_max = reach * 1.6
	p.damping_min = reach * 2.0
	p.damping_max = reach * 3.0
	p.gravity = Vector3(0.0, 0.35, 0.0)          # warm dust lifts slowly
	p.angle_min = -180.0
	p.angle_max = 180.0
	p.angular_velocity_min = -40.0
	p.angular_velocity_max = 40.0
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.2
	var sc := Curve.new()
	sc.add_point(Vector2(0.0, 0.4))
	sc.add_point(Vector2(0.3, 1.0))
	sc.add_point(Vector2(1.0, 1.5))
	p.scale_amount_curve = sc
	var g := Gradient.new()
	g.set_color(0, DUST_TINT)
	g.add_point(0.4, Color(DUST_TINT.r, DUST_TINT.g, DUST_TINT.b, 0.55))
	g.set_color(g.get_point_count() - 1, Color(DUST_TINT.r, DUST_TINT.g, DUST_TINT.b, 0.0))
	p.color_ramp = g
	return p


## Grit and chunks of floor thrown up by a knockdown slam.
static func debris(count: int, speed: float) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.name = "Debris"
	var q := QuadMesh.new()
	q.size = Vector2(0.05, 0.05)
	q.material = _mat(DEBRIS, false, true, 2, 2)
	p.mesh = q
	p.amount = count
	p.lifetime = 0.75
	p.one_shot = true
	p.explosiveness = 1.0
	p.randomness = 1.0
	p.lifetime_randomness = 0.3
	p.local_coords = false
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.direction = Vector3.UP
	p.spread = 50.0
	p.flatness = 0.4
	p.initial_velocity_min = speed * 0.5
	p.initial_velocity_max = speed
	p.gravity = Vector3(0.0, -9.8, 0.0)
	p.angle_min = -180.0
	p.angle_max = 180.0
	p.angular_velocity_min = -360.0
	p.angular_velocity_max = 360.0
	p.scale_amount_min = 0.5
	p.scale_amount_max = 1.6
	p.anim_offset_min = 0.0
	p.anim_offset_max = 1.0
	p.color = Color(0.26, 0.22, 0.19)
	return p
