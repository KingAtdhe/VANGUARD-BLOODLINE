# Handoff — continue from here in a new session

Branch: `arena-severed-line`, last commit of the session of 2026-11-22/23:
D-094. Read `CLAUDE.md` first (it now has a standing rule: every animation
change goes to the owner with a real-speed review video).

## Where things stand (2026-11-23)

The whole session was about **Kairo looking and moving like a fighter**. In
order: D-086 every-frame checks, D-087 jump and crouch for all fighters +
Kairo rebuilt as a karate-kickboxing fighter + four-hit Origin Break, D-088
and D-089 fixes from the owner's phone recording (camera follows jumps,
strikes hold), D-090 smoother keys and a living stance, D-091 fists and
review videos, D-092 kick pops, shuffle walk, crouch, D-093 springs
(`follow_through`), D-094 crouch linger.

**Two things the owner still reports, both open:**
1. **"He still shakes when crouching."** Not reproduced: the installed
   clip is steady to half a millimetre (`tools/godot/clip_trace.gd`) and so
   is the running fight scene with down held (`tools/godot/hold_trace.gd`).
   D-094 keeps the crouch on screen 0.1 s after the state ends in case the
   phone's input flickers. **Asked the owner for a screen recording of the
   shake in training mode with the input list visible.** Do not guess
   again: look at that recording first (cut it into frames with ffmpeg, as
   in D-089).
2. **"He still looks robotic."** Told the owner plainly that hand-set poses
   have reached their limit. **Proposed next task, awaiting the owner's
   yes:** a trial on recorded karate. CMU subject 135 (a karateka; free for
   all uses) is downloaded to `~/tools/cmu_mocap` on the build machine as
   135_01 to 135_11 (not in the repo; `tools/mocap/fetch_clips.sh` has the
   source and should get those clip numbers added when they are used).
   Titles in the CMU index: kata (01-03, 06), front kick (04, already used
   for Seraphina), gedan barai, mawashi geri, oi-zuki, shuto uke, yoko
   geri. Only 135_08 has been looked at and it is one held pose, unusable.
   The trial: find the usable strikes, build two of Kairo's moves from them
   next to the keyed versions, send ONE video with both, let the owner
   choose. Earlier (before D-084) recorded boxing did not look right on
   him, so it is a trial.

## Kairo as built

- Stance and style: `STYLES["kairo"]` in `tools/blender/mocap_actions.py`
  (blueprint in `docs/POSE_BLUEPRINTS.md`); moves in `kairo_keys()`;
  crouch / jump / jumping attack in the generic block of `build()`.
- Inputs and frame data of his normals are unchanged since D-062; what the
  moves ARE changed in D-087 (see `docs/FIGHTER_COMBAT_DESIGN.md`).
- Only Kairo has: strike holds, overlap, springs, the living stance, his own
  block, the shuffle walk tuning as inspected, the tighter fists as
  inspected. The other five get the shared parts (fists, jump arms, walk,
  kick knee fix) at their next build and must be looked at then.
- Drakon and Ryuen are still on unfitted stances (rough jump and crouch).

## How to work on a fighter (build machine)

- Build: `python3 tools/blender/import_rigged.py --src assets/characters/_source/<id>/<id>.fbx --fighter <id> --moves /root/work/moves_<id>.json --out /root/work/out --mocap-dir /root/tools/cmu_mocap`
  (about 4 minutes; export the moves json first with
  `godot --headless --path . --script res://tools/blender/export_move_timing.gd -- /root/work/moves_<id>.json <id>`),
  copy `out/<id>/<id>.glb` to `assets/characters/<id>/`, then
  `godot --headless --path . --import`.
- Env switches on a build: `STANCE_ONLY=1` (idle only, fast),
  `KEYED_DEBUG=1` (wrists, feet, head per frame of keyed clips),
  `GLITCH_SCAN=1` (joints that pop on one frame).
- Look: `tools/godot/move_shot.gd` (every frame of a move with its hit box),
  `anim_shot.gd`, `pose_views.gd`, `hand_shot.gd` (a hand close up),
  `jump_shot.gd` (a jump in the real scene), `clip_trace.gd`,
  `hold_trace.gd`.
- Video for the owner: `python3 tools/review_video.py <fighter> out.mp4`
  (needs xvfb-run, ffmpeg, Pillow). Say it was sampled, not watched.
- Tests: `godot --headless --path . --script res://tests/run_tests.gd`
  (205 passing at D-094).
- APK: every push builds a release `apk-0.0.8-m7-<shortsha>`; give the
  owner the direct download link and remind them to uninstall the previous
  test app.

## Not verified by anyone but the owner

Everything on a phone.

---

# Earlier handoff (before 2026-11-22), kept for reference

Branch: `arena-severed-line`. Last task done: Ryuen's move set (D-068) —
all six fighters now have their own sets.
Hit feel (D-069: counter-hits, reactions by height, effects, KO slow
motion) is built on top of that.
Dashes (D-071) followed.
**Next task: the owner chooses.** Remaining from the Tekken / Street Fighter
comparison of 2026-11-21, in the order offered: a throw and throw escape
for every fighter; multi-hit ultimates. Do not start one without the owner's choice.

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
- Tests: 196 passing with D-071 (189 after hit feel, 183 after Ryuen) (146 before Vexa, 168 before
  Ryuen). A full run takes about 10 minutes on 2 cores, a first asset
  import about 12.
- D-067 (owner feedback): raised stages are lowered to the fighters' feet
  (`ArenaConfig.stage_height`), Kairo and Vexa have reshaped stances
  (`STYLES` + `shape_stance()`; preview a stance on the real skeleton before
  a 5-minute rebuild by measuring knee angles and foot spacing). The
  other four followed in D-070; all six stances now match the design doc
  except for the idle motion described there.
- D-074: the owner approved a reference per fighter (Steve Fox, Zangief,
  Hwoarang, Raven, Sagat, Leroy Smith) and all six stances were re-posed
  after them (`pose` in `STYLES`, new keys `shoulders`, `knees`, `*_toe`).
  Posed from the names only; the owner has not yet said whether they are
  good enough. If not, ask for screenshots of the exact stance wanted.
- D-075 (owner's pose quality brief): the rest-shape and proportion bugs
  behind the bad poses are fixed in the pipeline, there is a pose checker
  (`tools/blender/pose_check.py`, `pose_report.json` per build) and a
  five-view render (`tools/godot/pose_views.gd`). **Kairo, Vexa, Seraphina and Nox
  are done (D-075 to D-079); Drakon and Ryuen are not** (`docs/POSE_BLUEPRINTS.md` says how to do the next one,
  KI-050 lists their faults). One fighter per task, then stop for the owner.
  A full reimport after replacing all six models takes about seven minutes.
- D-080 to D-083 (owner's phone tests): arms are tested against each mesh's
  real width and depth, backs are straightened, the idle loops, the walk is
  a real step cycle, feet pivot on the boot's contact points, captured
  strikes are retimed. **Read `docs/ANIMATION_RESEARCH.md` first**: the
  owner still finds the fighting unnatural, and the next real gain is better
  source motion (the owner must download a fight pack), then eased timing
  for the script-keyed moves, then Ryuen and Drakon.
- D-084: Kairo's nine attacks are hand-keyed on his stance blueprint
  (`kairo_keys()`, `curve()`), as a trial the owner will judge on the phone.
  If approved, write the same kind of function per fighter, in that
  fighter's own style; if not, the owner needs to supply fight clips.
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
