# Changelog

## [0.0.5-m4] — 2026-11-18
### Added
- Multi-touch controls: floating stick + Light/Heavy/Kick/Block cluster, touch-down, per-finger tracking, left-handed toggle (pause menu).
- 6-tick input buffer (frozen during hitstop) in the simulation; `CombatTuning` data.
- Cancel routes via move `tags` / `cancel_tags`, cancel window and same-move repeat limit; Kairo L→L, L→K.
- Combo counter and damage scaling (100/100/80/70/60/50/40 %); HUD "N HITS".
- Training mode (main menu → Training): ∞ timer, no KO, health refill, Reset, combo/frame-data panel, input history.
- 16 new tests incl. exhaustive infinite-combo search and two-finger touch tests; mutation-checked.
### Changed
- Temporary DEBUG on-screen buttons removed (replaced by real touch controls).
- M2 hitstop press latch replaced by the input buffer.

## [0.0.4-m3] — 2026-11-18
### Added
- Best-of-three match loop: `MatchRules` data + deterministic `MatchDirector` (intro, fight, round end, match end).
- 90 s round timer, KO / time-out / draw / double-KO results, round cap guaranteeing termination.
- Match HUD: health bars with damage trail, timer, round label, round-win pips, announcer, pause button.
- Pause menu (Resume / Restart match / Quit), auto-pause on app background, Android back toggles pause.
- Results screen (winner or DRAW, score, per-round reason) with Rematch / Main menu.
- 13 new tests incl. per-tick invariants over 12 seeded random matches; mutation-checked.
### Changed
- Debug R/F5 restarts the match; on-screen Reset/Menu debug buttons removed; 3D name labels hidden (HUD shows names).

## [0.0.3-m2] — 2026-11-18
### Added
- Attack data model `MoveData` (all spec §4.3 fields) and `FighterDefinition`; Kairo light/heavy/kick data.
- Fighter state machine: idle, walk, block, attack (startup/active/recovery), hitstun, blockstun, KO.
- `HitboxSystem` (per-tick rect overlap) and `HitResolver` (hit/block, damage, chip, stun, pushback, corner transfer, trades, KO).
- Global hitstop with press latching; tick-stamped `CombatLog`.
- Placeholder hit reactions (lean, flash, hitstop shake), block shield, fist extension, hit/block sparks, camera shake.
- Hitbox debug view (F4), training reset (R/F5), dummy modes STAND/BLOCK/JAB (T/F6), temporary DEBUG attack/block touch buttons.
- 15 new tests incl. frame-advantage-vs-data, punish, trade, determinism of 1,200-tick combat logs; autoload guard test.
### Changed
- Combat scene uses `FighterDefinition` resources; heavy punch pushback 0.2 m.
### Fixed
- Removed a screenshot-capture helper accidentally committed in M1 (auto-pressed menu buttons; failed M1 CI).

## [0.0.2-m1] — 2026-11-18
### Added
- Fixed 60 Hz combat tick (`CombatClock`) with render interpolation and a catch-up cap.
- Deterministic `CombatSimulation`: walking (forward/back speeds), facing, pushboxes, arena walls, max separation.
- Typed data resources: `ArenaConfig` (`data/arenas/greybox_arena.tres`), `FighterMovementProfile` (`data/fighters/*.tres`).
- Greybox arena, placeholder capsule fighters, side-on camera rig with visibility guarantee.
- Debug overlay (F3), temporary debug touch buttons, Menu/back to main menu.
- 16 new tests (simulation, clock/frame-rate independence, scene integration with camera frustum checks).
### Changed
- Main menu "Fight" now opens the greybox scene.
- Test runner now runs on the first frame; CI fails on any script error in logs and smoke-runs the combat scene.

## [0.0.1-m0] — 2026-11-17
### Added
- Godot 4.7.2 project: Mobile renderer, sensor-landscape orientation, 2400×1080 reference viewport.
- Boot screen and placeholder main menu with safe-area margins; `SceneRouter` autoload.
- Input map (12 logical actions) with keyboard/gamepad debug bindings.
- Android export preset (no signing data).
- Headless test runner with project-configuration tests; GitHub Actions CI.
- `CLAUDE.md`, README, decision log, milestone checklist, known issues, doc stubs.
