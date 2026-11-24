class_name EffectsManager
extends Node3D
## Impact effects (spec §4.7; D-102): flash, sparks, rings and swooshes at the
## contact point, a ground slam where a knocked-down body hits the floor, fire
## (D-101). Hits: warm, bigger for more damage. Blocks: cool and small.
## Presentation only — never affects the simulation.


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


func spawn_for(event: CombatEvent, dir: float = 0.0, move: MoveData = null) -> void:
	## D-102: a flash, a glow, sparks flying away from the attacker ([param dir]
	## = +1/-1 along X, 0 = both ways), a shockwave ring on strong hits and a
	## swoosh on kicks and heavy blows; a block throws cold sparks back at
	## the attacker. Sized by damage, capped so a hit never hides the fighters.
	var is_hit: bool = event.type == CombatEvent.Type.HIT
	var is_block: bool = event.type == CombatEvent.Type.BLOCK
	var strong: bool = is_hit and (event.counter_hit or event.damage >= 60)
	var size: float = minf(0.55, 0.25 + event.damage / 250.0) if is_hit else 0.24
	if is_hit and event.counter_hit:
		size = minf(0.65, size * 1.25)
	var tint: Color = (ImpactFX.COUNTER_TINT if event.counter_hit else ImpactFX.HIT_TINT) if is_hit else ImpactFX.BLOCK_TINT
	var at := Vector3(event.point.x, event.point.y, 0.35)
	var rng := RandomNumberGenerator.new()
	rng.seed = event.tick * 7919 + event.damage
	# white-hot flash with rays, and the coloured glow under it
	_add_sprite(ImpactFX.sprite(ImpactFX.STAR, Vector2.ONE * size * 2.2, Color(1, 1, 1).lerp(tint, 0.2)), at,
			0.13, 0.6, 1.2, rng.randf_range(-0.4, 0.4))
	_add_sprite(ImpactFX.sprite(ImpactFX.GLOW, Vector2.ONE * size * 1.5, Color(tint.r, tint.g, tint.b, 0.45)), at,
			0.12, 0.8, 1.3, 0.0)
	var spark_dir: float = -dir if is_block else dir
	var count: int = (34 if strong else 20) if is_hit else 12
	var sp: CPUParticles3D = ImpactFX.sparks(count, (7.5 if strong else 5.5) if is_hit else 4.0,
			spark_dir, tint, 180.0 if is_zero_approx(spark_dir) else (60.0 if is_hit else 45.0))
	_burst(sp, at, 0.8)
	if strong:
		_add_sprite(ImpactFX.sprite(ImpactFX.RING, Vector2.ONE * size * 1.2, tint), at, 0.24, 0.35, 1.7, 0.0)
	if is_block:
		_add_sprite(ImpactFX.sprite(ImpactFX.RING, Vector2.ONE * 0.4, ImpactFX.BLOCK_TINT), at, 0.2, 0.6, 1.6, 0.0)
	# a swoosh trailing into the blow: kicks and heavy hits
	if is_hit and move != null and not is_zero_approx(dir) \
			and (String(move.animation).contains("KICK") or event.damage >= 60) and not move.is_projectile():
		var sl: MeshInstance3D = ImpactFX.sprite(ImpactFX.SLASH, Vector2(size * 2.3, size * 1.3), Color(tint.r, tint.g, tint.b, 0.55))
		sl.scale = Vector3(-dir, 1.0, 1.0)            # the arc's bright head on the far side of the target
		_add_sprite(sl, at - Vector3(dir * size * 0.35, 0.0, 0.0), 0.14, 0.85, 1.1, rng.randf_range(-0.35, 0.35), true)


## A fighter's body slamming into the floor (knockdown, D-102): a shockwave
## ring along the floor, dust rolling out, grit and chunks thrown up.
## [param strength] 1 = a knockdown, more for a KO.
func spawn_ground_slam(x: float, z: float, strength: float = 1.0) -> void:
	var at := Vector3(x, 0.04, z)
	var ring: MeshInstance3D = ImpactFX.floor_sprite(ImpactFX.RING, 1.0, Color(1.0, 0.9, 0.75, 0.7))
	_add_sprite(ring, at, 0.45, 0.4, 2.6 * strength, 0.0, true)
	_burst(ImpactFX.dust(int(18 * strength), 0.8 * strength, 2.4 * strength), at + Vector3(0, 0.12, 0), 1.6)
	_burst(ImpactFX.debris(int(14 * strength), 3.2 * sqrt(strength)), at + Vector3(0, 0.05, 0), 1.2)
	_add_sprite(ImpactFX.sprite(ImpactFX.GLOW, Vector2(1.6, 0.5) * strength, Color(1.0, 0.85, 0.6, 0.35)), at + Vector3(0, 0.15, 0.2),
			0.25, 0.8, 1.6, 0.0)


## A fading, growing sprite (animated in _process with the other parts).
## [param keep_scale]: the sprite already carries a scale (a mirrored swoosh).
func _add_sprite(mi: MeshInstance3D, at: Vector3, life: float, grow_from: float, grow_to: float, angle: float,
		keep_scale: bool = false) -> void:
	mi.position = at
	if not is_zero_approx(angle):
		mi.rotation.z = angle
	var base: Vector3 = mi.scale if keep_scale else Vector3.ONE
	mi.scale = base * grow_from
	add_child(mi)
	_sparks.append({"node": mi, "mat": mi.material_override, "age": 0.0, "life": life, "scale": base,
		"from": grow_from, "to": grow_to, "origin": at, "dir": Vector3.ZERO})


## Starts a one-shot particle burst at [param at]; it frees itself.
func _burst(p: CPUParticles3D, at: Vector3, free_after: float) -> void:
	p.position = at
	add_child(p)
	p.emitting = true
	if is_inside_tree():
		get_tree().create_timer(free_after).timeout.connect(p.queue_free)


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
		if not s.has("a0"):
			s["a0"] = c.a                       # the sprite's own opacity (a soft glow starts below 1)
		c.a = float(s.a0) * (1.0 - t) * (1.0 - t * 0.35)
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
