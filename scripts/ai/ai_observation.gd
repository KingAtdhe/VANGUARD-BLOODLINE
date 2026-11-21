class_name AIObservation
extends RefCounted
## What a human player can see on screen at one tick (spec §5: "react only to
## information available to a human player").
##
## Deliberately EXCLUDED: held buttons, input buffers, pending presses, exact
## stun counters, cancel chains and anything about inputs not yet acted on.
## The AI only ever receives these snapshots (delayed by its reaction time
## for the opponent) — it never holds a reference to the simulation or to
## the other player's input.

## Visible state of one fighter.
class Seen:
	var x: float
	var facing: int
	var action: int            # FighterState.Action (visible pose)
	var move_id: StringName    # visible animation
	var move_frame: int        # how far into it the animation is
	var move_connected: bool   # hit spark / block flash visible
	var health: int            # health bar
	var combo_hits: int        # on-screen combo counter
	var meter: int             # Origin meter bar
	var in_surge: bool         # SURGE indicator / aura

## A projectile in flight (plainly visible on screen).
class SeenProjectile:
	var id: int
	var owner: int
	var x: float
	var direction: int
	var speed: float           # metres per tick
	var move_id: StringName

var tick: int = 0
var in_hitstop: bool = false
var fighters: Array[Seen] = []
var projectiles: Array[SeenProjectile] = []


static func from_sim(sim: CombatSimulation) -> AIObservation:
	var o := AIObservation.new()
	o.tick = sim.tick
	o.in_hitstop = sim.hitstop_remaining > 0
	for f: FighterState in sim.fighters:
		var s := Seen.new()
		s.x = f.position_x
		s.facing = f.facing
		s.action = f.action
		s.move_id = f.move.id if f.move != null else &""
		s.move_frame = f.move_frame
		s.move_connected = f.move_connected
		s.health = f.health
		s.combo_hits = f.combo_hits
		s.meter = f.meter
		s.in_surge = f.in_surge()
		o.fighters.append(s)
	for p: ProjectileState in sim.projectiles:
		var sp := SeenProjectile.new()
		sp.id = p.id
		sp.owner = p.owner
		sp.x = p.position_x
		sp.direction = p.direction
		sp.speed = p.move.projectile_speed * CombatConstants.TICK_DELTA
		sp.move_id = p.move.id
		o.projectiles.append(sp)
	return o
