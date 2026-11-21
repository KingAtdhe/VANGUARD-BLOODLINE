class_name HitboxSystem
extends RefCounted
## Hitbox/hurtbox geometry and overlap detection on the fighting plane.
##
## Boxes are axis-aligned Rect2 in (x, height) metres. Detection samples the
## overlap once per combat tick after movement (decision D-017): at walking
## speeds (< 0.05 m/tick) and with every active window >= 1 tick on static,
## fighter-relative boxes, tunnelling cannot occur. Projectiles (D-066) move
## much faster, so their box is swept over the distance covered in the tick
## (ProjectileState.swept_box).


## Standing hurtbox. Empty (no area) when the fighter cannot be hit (KO).
static func hurtbox(def: FighterDefinition, s: FighterState) -> Rect2:
	if s.action == FighterState.Action.KO or s.is_downed():
		return Rect2()
	# Evasive moves, and a launched fighter that has taken its juggle limit.
	if s.action == FighterState.Action.ATTACK and s.move != null and s.move.is_invulnerable_on(s.move_frame):
		return Rect2()
	if s.action == FighterState.Action.LAUNCHED and s.juggle_exhausted:
		return Rect2()
	return Rect2(s.position_x - def.hurtbox_half_width, 0.0,
		def.hurtbox_half_width * 2.0, def.hurtbox_height)


## The attack's hitbox for the current frame, mirrored by facing. Returns an
## empty Rect2 outside active frames. Ignores whether it already connected —
## use [method can_hit] for that.
static func hitbox(s: FighterState) -> Rect2:
	if s.action != FighterState.Action.ATTACK or s.move == null:
		return Rect2()
	if s.move.activates_surge or s.move.is_counter() or s.move.no_hitbox or s.move.is_projectile() \
			or not s.move.is_active_frame(s.move_frame):
		return Rect2()
	var c := Vector2(s.position_x + s.facing * s.move.hitbox_center.x, s.move.hitbox_center.y)
	return Rect2(c - s.move.hitbox_size * 0.5, s.move.hitbox_size)


## True if the attacker's hitbox is live and has not connected yet (a
## multi-hit move: not yet in the current hit window).
static func can_hit(s: FighterState) -> bool:
	if not hitbox(s).has_area():
		return false
	if s.move.rehit_interval > 0:
		return s.last_hit_window < s.move.hit_window(s.move_frame)
	return not s.move_connected


## One detected contact.
class Contact:
	var attacker: int
	var defender: int
	var point: Vector2
	## The move that connected (the attacker's current move, or the move the
	## projectile was fired with — its owner may be doing something else by now).
	var move: MoveData
	## Set when a projectile connected instead of the attacker's own hitbox.
	var projectile: ProjectileState = null


## All attacker→defender contacts this tick, in fixed P1→P2 order.
## Detection is separate from resolution so simultaneous hits (trades) are
## judged against the same pre-resolution state.
## Projectile contacts follow the fighters' own.
static func find_contacts(defs: Array[FighterDefinition], states: Array[FighterState],
		projectiles: Array[ProjectileState] = []) -> Array[Contact]:
	var out: Array[Contact] = []
	for a: int in 2:
		var d: int = 1 - a
		if not can_hit(states[a]):
			continue
		var hit_rect: Rect2 = hitbox(states[a])
		var hurt_rect: Rect2 = hurtbox(defs[d], states[d])
		if not hurt_rect.has_area() or not hit_rect.intersects(hurt_rect):
			continue
		# Throws cannot grab a fighter who is reeling from a hit or a blocked
		# attack (no unblockable combos, no grabbing out of blockstun).
		if states[a].move.is_throw() and (states[d].action == FighterState.Action.HITSTUN
				or states[d].action == FighterState.Action.BLOCKSTUN
				or states[d].action == FighterState.Action.LAUNCHED):
			continue
		var c := Contact.new()
		c.attacker = a
		c.defender = d
		c.point = hit_rect.intersection(hurt_rect).get_center()
		c.move = states[a].move
		out.append(c)
	for p: ProjectileState in projectiles:
		if p.spent:
			continue
		var target: int = 1 - p.owner
		var box: Rect2 = p.swept_box()
		var hurt: Rect2 = hurtbox(defs[target], states[target])
		if not hurt.has_area() or not box.intersects(hurt):
			continue
		var pc := Contact.new()
		pc.attacker = p.owner
		pc.defender = target
		pc.point = box.intersection(hurt).get_center()
		pc.move = p.move
		pc.projectile = p
		out.append(pc)
	return out


## Opposing projectiles whose swept boxes overlap destroy each other.
## Returns the clash points (for the log and effects).
static func find_clashes(projectiles: Array[ProjectileState]) -> Array[Vector2]:
	var points: Array[Vector2] = []
	for i: int in projectiles.size():
		for j: int in range(i + 1, projectiles.size()):
			var a: ProjectileState = projectiles[i]
			var b: ProjectileState = projectiles[j]
			if a.spent or b.spent or a.owner == b.owner:
				continue
			var ra: Rect2 = a.swept_box()
			var rb: Rect2 = b.swept_box()
			if ra.intersects(rb):
				a.spent = true
				b.spent = true
				points.append(ra.intersection(rb).get_center())
	return points
