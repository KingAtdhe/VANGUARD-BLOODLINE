# Handoff — continue from here in a new session

Branch: `arena-severed-line`. Last task done: Ryuen's move set (D-068) —
all six fighters now have their own sets.
Hit feel (D-069: counter-hits, reactions by height, effects, KO slow
motion) is built on top of that.
**Next task: the owner chooses.** Remaining from the Tekken / Street Fighter
comparison of 2026-11-21, in the order offered: forward and back dashes
(already in the spec); a throw and throw escape for every fighter;
multi-hit ultimates. Do not start one without the owner's choice.

## State

- Own move sets built: Kairo (D-062), Drakon (D-063), Seraphina (D-064),
  Nox (D-065), Vexa (D-066), Ryuen (D-068).
- Engine mechanics in place: low block and hit levels, direction + button
  inputs (D-061), counter stances (D-062), throws, armour, per-fighter chip
  (D-063), launch/juggle, invulnerable frames, backward moves (D-064),
  pass-through moves (D-065), projectiles and parries (D-066: a parry is a
  counter stance without a follow-up; projectiles are never countered, so
  "projectiles beat Returning Wave" already holds), multi-hit moves,
  side-switching counters, a counter-stance ultimate and a deflecting block
  (D-068). New keyed moves should use the `Kit` class in `mocap_actions.py`
  (`ryuen_set` is the example; check which side the fighter leads with).
- Tests: 189 passing with D-069 (183 after Ryuen) (146 before Vexa, 168 before
  Ryuen). A full run takes about 10 minutes on 2 cores, a first asset
  import about 12.
- D-067 (owner feedback): raised stages are lowered to the fighters' feet
  (`ArenaConfig.stage_height`), Kairo and Vexa have reshaped stances
  (`STYLES` + `shape_stance()`; preview a stance on the real skeleton before
  a 5-minute rebuild by measuring knee angles and foot spacing). The
  other four followed in D-070; all six stances now match the design doc
  except for the idle motion described there.
- Unverified by anyone: everything on a real phone (look, feel, frame rate
  with 48-bone skeletons) and balance. The owner had not yet given feedback
  on Kairo, Drakon, Seraphina or Nox when this was written.

## Test builds go to GitHub (owner's request, 2026-11-21)

The owner wants every test APK from GitHub, not as a file in the chat.
`.github/workflows/android.yml` builds on every push to this branch and
publishes a release named `Test build <version> (<short sha>, <branch>)`
with the APK attached: https://github.com/KingAtdhe/vanguard-bloodline/releases
After pushing, wait for that run, check it is green, and send the owner the
release link. Each run signs with a fresh debug key, so the owner must
uninstall the previous test app every time; a fixed key would need the owner
to add a keystore as a repository secret.

## How a fighter gets its own set (pattern to follow)

1. `data/moves/<id>_*.tres`, `data/fighters/<id>_movement.tres`, edit
   `data/fighters/<id>.tres` (keep `kairo_origin_surge.tres`).
2. `tools/blender/mocap_actions.py`: add `<id>_set(c)` to `OWN_SETS`
   (see `drakon_set`, `seraphina_set`, `nox_set`; helpers `track`, `sink`,
   `turn`, `hump`, `strike(aim=, lift=)`), hand shapes in `HANDS_BY_ACTION`.
   `vexa_set` is the most accurate model to copy for keyed moves: it aims
   wrists, elbows and knees in model space through `ctx["joints"]`
   (`wrist_src`, `elbow_src`, `knee_src`, `bend_to`, `point_hand`), and
   `mirrored(clip)` turns a right-sided capture into a left-sided one.
3. Export timings and rebuild that fighter:
   `godot --headless --path . --script res://tools/blender/export_move_timing.gd -- /tmp/moves_<id>.json <id>`
   `python tools/blender/import_rigged.py --src assets/characters/_source/<id>/<id>.fbx --fighter <id> --moves /tmp/moves_<id>.json --out <dir> --mocap-dir <clips>`
   then copy `<dir>/<id>/<id>.glb` over `assets/characters/<id>/<id>.glb`.
4. Render the moves from at least two angles and look at them; measure
   stretched edges:
   `xvfb-run -a godot --path . --rendering-driver opengl3 --script res://tools/godot/move_shot.gd -- <id> <out_dir> 320`
   (add `<move> 7,9,15,...` for chosen frames of one move) and
   `python tools/blender/stretch_check.py assets/characters/<id>/<id>.glb ATTACK SPECIAL ULTIMATE`.
   Reactions, idles and walks: `tools/godot/anim_shot.gd -- <id> <out.png> HIT_BODY,HIT_LOW 6`.
   Reference for "normal" on these models: Vexa's idle has 9 stretched
   edges at worst, her worst new move 25 (of 21,217).
5. `tests/unit/test_<id>_moves.gd` (copy `test_vexa_moves.gd`), then
   `godot --headless --path . --import` and the full suite. While working,
   `... --script res://tests/run_tests.gd -- <id>` runs only that file.
6. DECISION_LOG entry, CHANGELOG, KNOWN_ISSUES KI-049, this file.

## Tools a fresh machine needs (none of this is in the repo)

- Godot **4.7.2-stable** Linux binary and its export templates
  (`~/.local/share/godot/export_templates/4.7.2.stable`).
- Python with `bpy` 5.3 (Blender as a module), `numpy`, `pillow`.
- Motion capture: `tools/mocap/fetch_clips.sh <dir>` (falls back to a
  second mirror; the first returned 404 on 2026-11-21).
- For renders: `xvfb-run` with Mesa (software OpenGL is enough).
- Android export: an Android SDK path in Godot's editor settings
  (`export/android/android_sdk_path`, plus `java_sdk_path`) containing
  `build-tools/<version>/apksigner` and `platform-tools/adb`. Google's SDK
  download was not reachable from the last two machines, so `apksigner` was
  a small shell wrapper around the uber-apk-signer jar (GitHub release) that
  maps `sign --ks --ks-pass pass:… --ks-key-alias … <apk>` and `verify <apk>`
  onto it; export with `--export-release "Android" <apk>` and a keystore passed through
  `GODOT_ANDROID_KEYSTORE_RELEASE_PATH/USER/PASSWORD`. **The test keystore is
  never committed.** A new machine signs with a new key, so the owner must
  uninstall the old test app before installing a new build.
- Full test run takes 10 to 17 minutes; a first asset import 6 to 12.
