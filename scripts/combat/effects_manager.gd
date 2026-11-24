class_name EffectsManager
extends Node3D
## Placeholder impact effects (spec §4.7): a short spark at the contact point.
## Hits: warm, bigger for more damage. Blocks: cool and small.
## Presentation only — never affects the simulation.

const LIFETIME: float = 0.18
const HIT_COLOR := Color(1.0, 0.75, 0.3)
const BLOCK_COLOR := Color(0.45, 0.75, 1.0)
const COUNTER_COLOR := Color(1.0, 0.3, 0.2)

var _sparks: Array[Dictionary] = []
## Projectile id -> its placeholder mesh (D-066).
var _shots: Dictionary = {}


## Draws the simulation's projectiles (a labelled placeholder: a glowing
## ball in the move's projectile_color), interpolated like the fighters.
func sync_projectiles(projectiles: Array[ProjectileState], alpha: float) -> void:
	var alive: Dictionary = {}
	for p: ProjectileState in projectiles:
		alive[p.id] = true
		var node: Node3D = _shots.get(p.id)
		if node == null:
			node = _make_shot(p)
			_shots[p.id] = node
			add_child(node)
			node.position = Vector3(p.position_x, p.move.hitbox_center.y, 0.0)
			for c: Node in node.get_children():
				if c is CPUParticles3D:
					(c as CPUParticles3D).emitting = true      # a fireball's trail (only in the tree)
		node.position = Vector3(lerpf(p.previous_x, p.position_x, alpha), p.move.hitbox_center.y, 0.0)
	for id: int in _shots.keys():
		if not alive.has(id):
			_retire_shot(_shots[id] as Node3D)
			_shots.erase(id)
	# the fireball's flames flicker and pulse (D-101)
	for id: int in _shots.keys():
		var core: Node3D = (_shots[id] as Node3D).get_node_or_null("Fireball")
		if core != null:
			var k: float = 1.0 + 0.07 * sin(Time.get_ticks_msec() * 0.031) + 0.04 * sin(Time.get_ticks_msec() * 0.077)
			core.scale = Vector3(core.scale.x / absf(core.scale.x) * k, k, 1.0)


## A gone projectile: a fireball's trail and sparks are left to burn out
## where they are instead of vanishing with it.
func _retire_shot(node: Node3D) -> void:
	var lingering: bool = false
	for c: Node in node.get_children():
		if c is CPUParticles3D:
			(c as CPUParticles3D).emitting = false
			lingering = true
		elif c is Node3D:
			(c as Node3D).visible = false
	if lingering and is_inside_tree():
		get_tree().create_timer(0.8).timeout.connect(node.queue_free)
	else:
		node.queue_free()


func _make_shot(p: ProjectileState) -> Node3D:
	if p.move.tags.has("fire"):
		return _make_fireball(p)
	var root := Node3D.new()
	root.name = "ProjectilePlaceholder%d" % p.id
	var size: Vector2 = p.move.hitbox_size
	# bright core + soft halo, stretched along the direction of travel
	for layer: Array in [[0.8, 1.0], [1.35, 0.3]]:
		var mi := MeshInstance3D.new()
		var mesh := SphereMesh.new()
		mesh.radius = 0.5
		mesh.height = 1.0
		mesh.radial_segments = 12
		mesh.rings = 6
		mi.mesh = mesh
		var mat := StandardMaterial3D.new()
		var c: Color = p.move.projectile_color.lerp(Color.WHITE, 0.3 if layer[1] == 1.0 else 0.0)
		c.a = layer[1]
		mat.albedo_color = c
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mi.material_override = mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.scale = Vector3(size.x, size.y, size.y) * layer[0]
		root.add_child(mi)
	return root


func spawn_for(event: CombatEvent) -> void:
	var is_hit: bool = event.type == CombatEvent.Type.HIT
	var strong: bool = is_hit and (event.counter_hit or event.damage >= 60)
	# Capped so even an ultimate never hides the fighters (spec §4.7).
	var size: float = minf(0.55, 0.25 + event.damage / 250.0) if is_hit else 0.22
	if is_hit and event.counter_hit:
		size = minf(0.65, size * 1.25)
	var color: Color = (COUNTER_COLOR if event.counter_hit else HIT_COLOR) if is_hit else BLOCK_COLOR
	var at := Vector3(event.point.x, event.point.y, 0.3)
	# bright core
	var core := SphereMesh.new()
	core.radius = 0.5
	core.height = 1.0
	core.radial_segments = 12
	core.rings = 6
	_add_part(core, color.lerp(Color.WHITE, 0.35), at, Vector3.ONE * size, 0.0, 0.4, 1.0, LIFETIME)
	if not is_hit:
		return
	# streaks flying out from the contact point (their angles come from the
	# event's tick, so the same fight always looks the same)
	var rng := RandomNumberGenerator.new()
	rng.seed = event.tick * 7919 + event.damage
	var streak := BoxMesh.new()
	streak.size = Vector3(1.0, 0.07, 0.07)
	for k: int in (7 if strong else 4):
		var angle: float = TAU * (k + rng.randf() * 0.7) / (7.0 if strong else 4.0)
		var reach: float = size * (1.5 + rng.randf() * 0.8)
		_add_part(streak, color.lerp(Color.WHITE, 0.2), at, Vector3(reach * 0.45, 1.0, 1.0), angle, 0.5, 1.6, LIFETIME * 1.2)
	# heavy hits and counter-hits: a ring that opens around the impact
	if strong:
		var ring := TorusMesh.new()
		ring.inner_radius = 0.42
		ring.outer_radius = 0.5
		ring.rings = 20
		ring.ring_segments = 6
		_add_part(ring, color, at, Vector3.ONE * size, 0.0, 0.5, 2.4, LIFETIME * 1.6, true)


## One short-lived unshaded mesh: grows from [param grow_from] to [param grow_to]
## times its scale while fading out. Streaks also travel outward as they grow.
func _add_part(mesh: Mesh, color: Color, at: Vector3, scale: Vector3, angle: float, grow_from: float,
		grow_to: float, life: float, face_camera: bool = false) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.no_depth_test = true
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = at
	mi.rotation.z = angle
	if face_camera:
		mi.rotation.x = PI * 0.5          # a torus lies flat by default: stand it up toward the side camera
	mi.scale = scale * grow_from
	add_child(mi)
	_sparks.append({"node": mi, "mat": mat, "age": 0.0, "life": life, "scale": scale, "from": grow_from, "to": grow_to,
		"origin": at, "dir": Vector3(cos(angle), sin(angle), 0.0) if mesh is BoxMesh else Vector3.ZERO})


func _process(delta: float) -> void:
	for i: int in range(_sparks.size() - 1, -1, -1):
		var s: Dictionary = _sparks[i]
		s.age += delta
		var t: float = s.age / float(s.life)
		if t >= 1.0:
			(s.node as Node).queue_free()
			_sparks.remove_at(i)
			continue
		var grow: float = lerpf(s.from, s.to, 1.0 - (1.0 - t) * (1.0 - t))
		var node := s.node as Node3D
		node.scale = (s.scale as Vector3) * grow
		node.position = (s.origin as Vector3) + (s.dir as Vector3) * (s.scale as Vector3).x * grow * 0.5
		var c: Color = (s.mat as StandardMaterial3D).albedo_color
		c.a = 1.0 - t
		(s.mat as StandardMaterial3D).albedo_color = c


# --- fire (D-101): sprites and flames from the owner's flame sheet --------------

## The fireball: the drawn fireball (head toward the direction of travel), a
## trail of real flames and sparks left behind it, and a red glow on the
## fighters and floor as it passes.
func _make_fireball(p: ProjectileState) -> Node3D:
	var root := Node3D.new()
	root.name = "Fireball%d" % p.id
	var size: Vector2 = p.move.hitbox_size
	var ball: MeshInstance3D = FireFX.sprite(FireFX.FIREBALL, Vector2(size.x * 2.2, size.x * 2.2))
	ball.name = "Fireball"
	ball.position = Vector3(-p.direction * size.x * 0.45, 0.0, 0.05)   # the sprite's head is on its right
	ball.scale = Vector3(float(p.direction), 1.0, 1.0)
	root.add_child(ball)
	var trail: CPUParticles3D = FireFX.flames(size.y * 1.1, 26, 0.32, size.y * 0.3, 0.6)
	root.add_child(trail)
	var sparks: CPUParticles3D = FireFX.embers(14, 0.5, size.y * 0.3, 1.0)
	root.add_child(sparks)
	var glow := OmniLight3D.new()
	glow.light_color = Color(1.0, 0.22, 0.08)
	glow.light_energy = 1.6
	glow.omni_range = 2.6
	glow.shadow_enabled = false
	root.add_child(glow)
	return root


## Fire bursting out of a hit by a fire move: the drawn burst, a puff of
## flames and sparks. [param size] in metres.
func spawn_fire_burst(at: Vector3, size: float) -> void:
	var b: MeshInstance3D = FireFX.sprite(FireFX.BURST, Vector2(size, size))
	b.position = at
	add_child(b)
	_sparks.append({"node": b, "mat": b.material_override, "age": 0.0, "life": 0.22, "scale": Vector3.ONE,
		"from": 0.5, "to": 1.5, "origin": at, "dir": Vector3.ZERO, "tex": true})
	var puff: CPUParticles3D = FireFX.flames(size * 0.7, 18, 0.45, size * 0.2, 1.4)
	puff.one_shot = true
	puff.explosiveness = 0.85
	puff.position = at
	add_child(puff)
	puff.emitting = true
	var sp: CPUParticles3D = FireFX.embers(18, 0.6, size * 0.15, 2.4)
	sp.one_shot = true
	sp.explosiveness = 0.9
	sp.spread = 180.0
	sp.position = at
	add_child(sp)
	sp.emitting = true
	if is_inside_tree():
		get_tree().create_timer(1.0).timeout.connect(puff.queue_free)
		get_tree().create_timer(1.0).timeout.connect(sp.queue_free)
