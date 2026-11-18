# Changelog

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
