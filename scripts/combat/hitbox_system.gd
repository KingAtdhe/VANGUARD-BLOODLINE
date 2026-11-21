class_name HitboxSystem
extends RefCounted
## Hitbox/hurtbox geometry and overlap detection on the fighting plane.
##
## Boxes are axis-aligned Rect2 in (x, height) metres. Detection samples the
## overlap once per combat tick after movement (decision D-017): at walking
## speeds (< 0.05 m/tick) and with every active window >= 1 tick on static,
## fighter-relative boxes, tunnelling cannot occur. Swept tests will be added
## for fast projectiles when they exist.


## Standing hurtbox. Empty (no area) when the fighter cannot be hit (KO).
static func hurtbox(def: FighterDefinition, s: FighterState) -> Rect2:
	if s.action == FighterState.Action.KO or s.is_downed():
		return Rect2()
	return Rect2(s.position_x - def.hurtbox_half_width, 0.0,
		def.hurtbox_half_width * 2.0, def.hurtbox_height)


## The attack's hitbox for the current frame, mirrored by facing. Returns an
## empty Rect2 outside active frames. Ignores whether it already connected —
## use [method can_hit] for that.
static func hitbox(s: FighterState) -> Rect2:
	if s.action != FighterState.Action.ATTACK or s.move == null:
		return Rect2()
	if s.move.activates_surge or s.move.is_counter() or not s.move.is_active_frame(s.move_frame):
		return Rect2()
	var c := Vector2(s.position_x + s.facing * s.move.hitbox_center.x, s.move.hitbox_center.y)
	return Rect2(c - s.move.hitbox_size * 0.5, s.move.hitbox_size)


## True if the attacker's hitbox is live and has not connected yet.
static func can_hit(s: FighterState) -> bool:
	return not s.move_connected and hitbox(s).has_area()


## One detected contact.
class Contact:
	var attacker: int
	var defender: int
	var point: Vector2


## All attacker→defender contacts this tick, in fixed P1→P2 order.
## Detection is separate from resolution so simultaneous hits (trades) are
## judged against the same pre-resolution state.
static func find_contacts(defs: Array[FighterDefinition], states: Array[FighterState]) -> Array[Contact]:
	var out: Array[Contact] = []
	for a: int in 2:
		var d: int = 1 - a
		if not can_hit(states[a]):
			continue
		var hit_rect: Rect2 = hitbox(states[a])
		var hurt_rect: Rect2 = hurtbox(defs[d], states[d])
		if not hurt_rect.has_area() or not hit_rect.intersects(hurt_rect):
			continue
		var c := Contact.new()
		c.attacker = a
		c.defender = d
		c.point = hit_rect.intersection(hurt_rect).get_center()
		out.append(c)
	return out
