# Handoff — continue from here in a new session

Branch: `arena-severed-line`. Last task done: Nox's move set (D-065).
**Exact next task: Vexa's move set** (projectile + parry), then Ryuen
(counters), from `docs/FIGHTER_COMBAT_DESIGN.md` and the owner's design doc
linked there. One fighter per task; stop and report after each (CLAUDE.md).

## State

- Own move sets built: Kairo (D-062), Drakon (D-063), Seraphina (D-064),
  Nox (D-065). Vexa and Ryuen still use the shared `kairo_*` set.
- Engine mechanics in place: low block and hit levels, direction + button
  inputs (D-061), counter stances (D-062), throws, armour, per-fighter chip
  (D-063), launch/juggle, invulnerable frames, backward moves (D-064),
  pass-through moves (D-065). Still missing: **projectile, parry** (a parry
  can reuse the counter stance; Ryuen's counters too).
- Tests: 146 passing at commit `91a4352`.
- Unverified by anyone: everything on a real phone (look, feel, frame rate
  with 48-bone skeletons) and balance. The owner had not yet given feedback
  on Kairo, Drakon, Seraphina or Nox when this was written.

## How a fighter gets its own set (pattern to follow)

1. `data/moves/<id>_*.tres`, `data/fighters/<id>_movement.tres`, edit
   `data/fighters/<id>.tres` (keep `kairo_origin_surge.tres`).
2. `tools/blender/mocap_actions.py`: add `<id>_set(c)` to `OWN_SETS`
   (see `drakon_set`, `seraphina_set`, `nox_set`; helpers `track`, `sink`,
   `turn`, `hump`, `strike(aim=, lift=)`), hand shapes in `HANDS_BY_ACTION`.
3. Export timings and rebuild that fighter:
   `godot --headless --path . --script res://tools/blender/export_move_timing.gd -- /tmp/moves_<id>.json <id>`
   `python tools/blender/import_rigged.py --src assets/characters/_source/<id>/<id>.fbx --fighter <id> --moves /tmp/moves_<id>.json --out <dir> --mocap-dir <clips>`
   then copy `<dir>/<id>/<id>.glb` over `assets/characters/<id>/<id>.glb`.
4. Render the moves from at least two angles and look at them; measure
   stretched edges.
5. `tests/unit/test_<id>_moves.gd` (copy `test_nox_moves.gd`), then
   `godot --headless --path . --import` and the full suite.
6. DECISION_LOG entry, CHANGELOG, KNOWN_ISSUES KI-049, this file.

## Tools a fresh machine needs (none of this is in the repo)

- Godot **4.7.2-stable** Linux binary and its export templates
  (`~/.local/share/godot/export_templates/4.7.2.stable`).
- Python with `bpy` 5.3 (Blender as a module), `numpy`, `pillow`.
- Motion capture: `tools/mocap/fetch_clips.sh <dir>`.
- Android export: an Android SDK path in Godot's editor settings with
  `apksigner` (the previous session used the uber-apk-signer jar behind an
  `apksigner` wrapper) and a keystore passed through
  `GODOT_ANDROID_KEYSTORE_RELEASE_PATH/USER/PASSWORD`. **The test keystore is
  never committed.** A new machine signs with a new key, so the owner must
  uninstall the old test app before installing a new build.
- Full test run takes about 17 minutes; an asset import about 6.
