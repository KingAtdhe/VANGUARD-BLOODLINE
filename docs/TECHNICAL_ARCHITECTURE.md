# Technical Architecture

Canonical source: `PRODUCTION_PACKAGE.md` §9. This file records what is
actually implemented. Updated: Milestone 1.

## Combat loop (per render frame)

```
CombatScene._process(delta)
 ├─ ticks = CombatClock.advance(delta)        # 0..5 fixed 60 Hz ticks
 ├─ repeat ticks:
 │    previous = simulation.snapshot()
 │    simulation.step([P1 input, P2 input])   # deterministic
 └─ render: views lerp(previous, current, clock.alpha())
            CameraRig.follow(rendered positions)
            DebugOverlay text
```

## Simulation step phases (`CombatSimulation.step`)

1. Intent — store `move_x` (−1/0/+1, world space) per fighter.
2. Integrate — forward speed if moving toward the facing side, else backward.
3. Max separation — pull back only the fighter(s) that moved away.
4. Pushbox resolve — split overlap 50/50; a wall-blocked fighter pushes the
   other one fully.
5. Wall clamp — pushbox edge stays inside `[left_bound, right_bound]`.
6. Facing — both fighters face each other (unchanged if centres coincide).

P1 is always processed before P2. Later milestones add phases (attacks, hit
resolution, hitstop, match rules) — insert them here and document the order.

## Responsibilities

| Piece | File | Owns |
|---|---|---|
| CombatClock | `scripts/combat/combat_clock.gd` | Fixed tick accumulator, catch-up cap, alpha |
| CombatSimulation | `scripts/combat/combat_simulation.gd` | Authoritative fighter state & rules |
| FighterState | `scripts/fighters/fighter_state.gd` | Plain per-tick data |
| FighterInputFrame | `scripts/input/fighter_input_frame.gd` | One tick of logical input (player, dummy, later AI) |
| LocalInputReader | `scripts/input/local_input_reader.gd` | Input actions → FighterInputFrame |
| FighterView | `scripts/fighters/fighter_view.gd` | Visual only |
| CameraRig | `scripts/camera/camera_rig.gd` | Framing; presentation only |
| CombatScene | `scripts/combat/combat_scene.gd` | Wires clock, sim, input, views |
| ArenaConfig / FighterMovementProfile | `scripts/combat/arena_config.gd`, `scripts/fighters/fighter_movement_profile.gd` | Typed data (D-010) |
