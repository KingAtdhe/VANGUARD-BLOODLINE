# Technical Architecture

Canonical source: `PRODUCTION_PACKAGE.md` §9. This file records what is
actually implemented. Updated: Milestone 6.

## Combat loop (per render frame)

```
CombatScene._process(delta)
 ├─ ticks = CombatClock.advance(delta)        # 0..5 fixed 60 Hz ticks
 ├─ (nothing if SceneTree.paused)
 ├─ repeat ticks:
 │    previous = simulation.snapshot()
 │    P2 input = AI (observe AIObservation → next_input) or dummy
 │    director.step(simulation, [P1 input, P2 input])
 │        INTRO/ROUND_END/MATCH_END → simulation.step(neutral inputs)
 │        FIGHT → simulation.step(inputs), timer −1, check KO / time-out
 ├─ new CombatLog events → EffectsManager sparks, view flash, camera shake
 └─ render: views lerp(previous, current, clock.alpha())
            HitboxDebugView (exact sim boxes), CameraRig, MatchHUD, DebugOverlay
Director signals → HUD announcer (round_started, fight_started, round_ended),
MatchResults (match_ended).
```

## Simulation step phases (`CombatSimulation.step`)

0. Hitstop — if active: count down, buffer new presses (no aging), freeze all.
1. State/input — buffer new presses; advance attack frame / stun timers
   (recovering from stun ends the combo on that fighter); an attacking
   fighter may cancel into the newest legal buffered move; a neutral fighter
   starts the newest buffered attack, holds block, or walks; age the buffer.
2. Integrate — walking (forward/back speed relative to facing) and pushback.
3. Spacing — corner pushback transfer, max separation, pushbox resolve, walls.
4. Facing — only neutral fighters turn toward the opponent.
5. Hits — `HitboxSystem.find_contacts` on post-movement boxes, then
   `HitResolver.resolve` judges all contacts on the pre-resolution state
   (trades), applies damage/chip, stun, pushback, hitstop, KO, and logs events.

P1 is always processed before P2 inside each phase.

## Fighter states

`IDLE`, `WALK`, `BLOCK` (neutral, can act) · `ATTACK` (move + 1-based frame) ·
`HITSTUN`, `BLOCKSTUN` (stun countdown) · `KO`.

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
| FighterDefinition / MoveData | `scripts/fighters/fighter_definition.gd`, `scripts/combat/move_data.gd` | Fighter + attack data (D-020) |
| HitboxSystem | `scripts/combat/hitbox_system.gd` | Box geometry, contact detection |
| HitResolver | `scripts/combat/hit_resolver.gd` | Hit/block/damage/stun/pushback/hitstop/KO |
| CombatLog / CombatEvent | `scripts/combat/combat_log.gd`, `combat_event.gd` | Tick-stamped event history (300 max) |
| TrainingDummyController | `scripts/combat/training_dummy_controller.gd` | P2 STAND/BLOCK/JAB |
| HitboxDebugView | `scripts/combat/hitbox_debug_view.gd` | Draws sim boxes (F4) |
| EffectsManager | `scripts/combat/effects_manager.gd` | Placeholder sparks |
| MatchRules | `scripts/combat/match_rules.gd` | Rounds, time, intro/outro, draw rules (data) |
| MatchDirector | `scripts/combat/match_director.gd` | Phases, timer, round results, match winner, rematch |
| MatchHUD / PauseMenu / MatchResults | `scripts/ui/` | Presentation; read state, emit button signals |
| CombatTuning | `scripts/combat/combat_tuning.gd` | Buffer window, cancel grace/repeat limit, combo scaling (data) |
| TouchControls | `scripts/ui/touch_controls.gd` | Multi-touch stick + buttons → logical actions |
| InputHistory | `scripts/input/input_history.gd` | Compressed P1 input log for training |
| TrainingPanel | `scripts/ui/training_panel.gd` | Combo/frame data/input history readout |
| AIController | `scripts/ai/ai_controller.gd` | FSM opponent; delayed perception; FighterInputFrame out |
| AIObservation | `scripts/ai/ai_observation.gd` | Human-visible snapshot (no inputs/buffers/stun counters) |
| AIProfile / AIDecisionLog | `scripts/ai/ai_profile.gd`, `ai_decision_log.gd` | Difficulty data, decision log |
| SessionSettings | `scripts/app/session_settings.gd` | Session-only choices (AI difficulty) |
| OriginMeter | `scripts/combat/origin_meter.gd` | Meter costs/gains, Surge start/drain, ultimate rules |
| FighterAnimator | `scripts/fighters/fighter_animator.gd` | Sim-driven animation choice and seeking |
| AnimationSampler | `scripts/fighters/animation_sampler.gd` | Exact-time pose sampling for tests/tools |
| CombatAudio | `scripts/combat/combat_audio.gd` | Event-driven SFX (8 voices) |
| Blockout build | `tools/blender/build_kairo_blockout.py` | Scripted Blender source asset → GLB |
