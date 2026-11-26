# Checks: what to run, what passes, what each one cannot see

Every command here was run on 2026-11-25 against Kairo at D-122. Run from
the repository root. `S=.claude/skills/fighter-move-animation/scripts`.

Contents: Machine · Frame numbers · The order · Each check (motion report,
flags diff, body angles, hitbox sheet, frame strip, reference comparison, foot slide,
stretched edges, pose checker, arena view, tests) · Known flags on Kairo ·
What no check sees.

## Machine

The cloud workspace starts empty each session. Setting it up takes about
fifteen minutes, almost all of it the first asset import.

```bash
# Godot 4.7.2 (pinned)
curl -sSL -o /tmp/godot.zip https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip
unzip -q -o /tmp/godot.zip -d /tmp && mv /tmp/Godot_v4.7.2-stable_linux.x86_64 /usr/local/bin/godot && chmod +x /usr/local/bin/godot
# Blender as a Python module (5.3), numpy, Pillow
pip install --break-system-packages bpy numpy pillow
# motion-capture clips (not in the repo)
bash tools/mocap/fetch_clips.sh /root/tools/cmu_mocap
# first import of the project's assets: 6-12 minutes on 2 cores; run it in the background
mkdir -p /root/work && godot --headless --path . --import > /root/work/import.log 2>&1
```

`xvfb-run` and `ffmpeg` are needed for renders and videos (present on the
cloud machine). The two "Draco / MeshOptimizer is not available" lines in a
build log are harmless. A build is deterministic: rebuilding without changes
left `git status` clean here (a useful sanity check).

APK export needs more (Android SDK path, signer); pushes build the APK on
GitHub instead, see `docs/HANDOFF.md`.

Is this machine already set up? `command -v godot && python3 -c "import bpy"
&& ls .godot/imported | head -1 && ls /root/work/build_kairo.log`. If the
last one is missing, run `build_fighter.sh kairo` once for the baseline.

## Frame numbers

| Counts from 1 (contact = startup number) | Counts from 0 |
|---|---|
| frame data, `motion_report.py`, `frame_strip.py`, `compare_reference.py`, `body_angles.gd`, `move_shot.gd`, GLITCH lines, pose checker | keys in `mocap_actions.py` (`a0`, `a1`); `knee_angles.gd` (and half a frame late) |

`motion_report.py` positions are relative to the fighter's own body (model
space): in a move with travel a foot can move there while standing still on
the floor, and the reverse.

## The order

1. `build_fighter.sh` — build, install, flags diff.
2. `motion_report.py` — the move's frame table and flags.
3. `body_angles.gd` — knees, hips, chest and lean on the game model.
4. `move_shot.gd` — the strike is in the hitbox.
5. `frame_strip.py`, then `compare_reference.py` — look.
6. `stretch_check.py`, `foot_slide.gd` (if feet or walking changed).
7. Arena view if the change is about readability at game distance.
8. Full tests.

Cheap checks first: a pop found in step 2 saves rendering a strip of a
broken move.

## Each check

### Motion report

```bash
python3 $S/motion_report.py /root/work/build_kairo.log KICK_LOW_01
python3 $S/motion_report.py /root/work/build_kairo.log          # one-line flags for every keyed clip
```

Per frame: centimetres each wrist and ankle moved, head height, arm and leg
extension, phase. Then:

| Line | Meaning | Pass |
|---|---|---|
| `POP` | GLITCH_SCAN: a joint moved > 6 cm (toes 3.5 cm) and > 2.6× its neighbours on one frame | none new; on the frame the strike fires it is usually the strike itself |
| `arrival` | the striking limb's last two frames into the contact | information: late and fast is right |
| `FAST` | > 30 cm (ankle) or > 25 cm (wrist) in one frame away from the strike, or a strike that happens entirely in one frame | look at it in the strip; spread it unless the motion calls for it |
| `DWELL` | a raised ankle (above 0.45 m) keeping its height within 5 cm for 6+ frames before the strike | none: a leg waiting in the air |
| `FOLD` | a leg below 0.33 of its length | look at that frame from the front; run `stretch_check.py` |
| `FROZEN` | 4+ frames with no wrist, ankle or head movement (under 0.25 cm; the log rounds to 1 cm) inside a move | none, unless it is a deliberate pose (a counter stance) |
| `hold` | the same just after the last active frame | fine up to ~5 frames |
| `CONTACT` | limb extension (with the bend it implies) and where ankles and wrists are on the first active frame, next to the hitbox centre | no fixed mark: compare with the move before and with the brief. Today: jab 0.99, cross 0.98, counter strike 0.90, uppercut 0.97, Low Kick leg 1.00, Front Kick leg 0.96 (a 34° knee) |

Cannot see: pelvis, chest, head turn; anything after the spring pass and the
stance blends; whether the shape is right. Positions are rounded to 1 cm.
Slow near-stillness that is not exactly still (a foot creeping 1–5 cm a
frame after the hit) is not flagged: read the table's columns for it.
Reference: the approved Low Kick shows `arrival f8-9 right ankle 26 cm then
56 cm` and one toe `POP` on f9.

### Flags diff

`build_fighter.sh` prints it; by hand:

```bash
python3 $S/motion_report.py /root/work/build_kairo.log --diff /root/work/build_kairo.prev.log
```

Pass: no `+` line you cannot explain. The previous log is whatever was built
last on this machine, so on a fresh machine build once **before** editing to
get the baseline.

### Body angles (the game model)

```bash
godot --headless --path . --script res://tools/godot/body_angles.gd -- kairo KICK_LOW_01
```

One line per frame (1-based, phase marked): knee bend left and right (0° =
straight), pelvis and chest turn (absolute, and the change from frame 1),
the twist between them, trunk lean forward/back and to the side, each
ankle's forward distance and height, head height. This fills the brief's
"now" column and proves the result.

Pass: the brief's numbers. For a leg the brief calls fully straight, ≤ 5° on
the frames it names (Rift Break and the Flying Side Kick read 4°; the Low
Kick 4° at contact). Twist under ~45°. This is the measurement that counts:
the build log said 1.00 while the game showed 11° (D-114).

Signs: pelvis and chest `+` = his left side toward the opponent; lean `fwd`
`−` = back, `side` `+` = to his left (away from the camera when he is P1).
Cannot see: arms, head turn, the foot's angle, the standing foot's pivot
(look at the strip and `move_shot.gd`'s front view).

`knee_angles.gd` (older) prints knees only, on one line, and lets playback
run between samples: it reads about half a frame late, so on fast frames its
numbers are far from these (Low Kick frame 8: 40° there, 94° here). Use
`body_angles.gd`.

### Rig inspection

```bash
godot --headless --path . --script res://tools/godot/rig_inspect.gd -- kairo
```

Bones with parents, rest positions and directions; an axis test (each bone
turned 20° about each of its own axes, and where the joint below it went); the
flexion axes that follow from it; pose tests. Kairo: 48 bones, no control or
IK bones; Y runs along each bone (twist), X is flexion (hip −X = thigh
forward, knee +X = heel back), Z is sideways; the rest pose is not symmetric
(right leg 0.20 out, left 0.08), which is why bones are not animated by
turning them about their axes here.

### Leg report (kicks)

```bash
python3 $S/leg_report.py kairo SPECIAL_RIFT_BREAK Right --plot /root/work/rift_path.png
```

Runs `tools/godot/leg_check.gd` and marks, OK or CHECK: the knee never bends
the wrong way and its non-flexion rotation never jumps (a rolled thigh); how
high the foot goes against the head; how near vertical the leg gets; the
foot's sideways spread; how steep the strike falls and whether it speeds up;
toes pulled back at the contact; the supporting foot's movement on the floor
in the world; no foot under the floor; the largest one-frame moves; first and
last frame alike. `--plot` draws the hip, knee and ankle paths from the side
and the front. The steepness and above-the-head marks are for a downward kick;
read them as information for other kicks. Rift Break at D-129: 15 of 15.

### Hitbox sheet

```bash
xvfb-run -a godot --path . --rendering-driver opengl3 --script res://tools/godot/move_shot.gd \
    -- kairo /root/work/shots 320 kairo_low_kick            # move id filter; add e.g. 7,9,12 for chosen frames
```

Writes `<out_dir>/<move_id>.png` (`<move_id>_frames.png` when frames are
given). Three views (side, three-quarter, front) with the hitbox drawn in red. Pass:
the striking foot or fist is inside the box on the active frames, and the
front view shows no limb through the body. `tests/integration/test_kairo_model.gd`
also checks which limb is in the box: change the limb, change the test.

### Frame strip (every frame, side view)

```bash
python3 $S/frame_strip.py kairo KICK_LOW_01 /root/work/now_kick.png
python3 $S/frame_strip.py kairo SPECIAL_RIFT_BREAK /root/work/now_rift.png --from 1 --to 26 --cell 330
```

Long moves: read in two parts so the cells stay large. Frames are kept in
`<out>_frames/`. Read it twice: once for the contact pose against the brief,
once left to right for the motion (wind-up present? body leads the limb?
contact held? anything still or jumping? does the return fill the recovery?).

Clip suffixes: `KICK_LOW_01`, `ATTACK_LIGHT_01`, `ATTACK_HEAVY_01`,
`ATTACK_BODY_HOOK_01` (Front Kick), `ATTACK_RISING_UPPERCUT_01`,
`KICK_SWEEP_01`, `ATTACK_STRING_CROSS_01`, `ATTACK_COUNTER_HOOK_01`,
`SPECIAL_ORIGIN_PALM`, `SPECIAL_RIFT_BREAK`, `SPECIAL_SLIP_COUNTER`,
`SPECIAL_FIREBALL`, `THROW_KNEE_01`, `ULTIMATE_ORIGIN_BREAK`, `JUMP`,
`JUMP_ATTACK`, `IDLE_A`, `WALK_FORWARD`, `WALK_BACKWARD`, `CROUCH`.

### Reference comparison

```bash
python3 $S/compare_reference.py --ref <owner picture> --now /root/work/now_kick_frames --frame 9 \
    --before /root/work/before_kick_frames --frames 5,9,13 --out /root/work/compare_kick.png
```

`--frame` is 1-based; the contact is the move's startup number. `--ref-flip`
if the pictured fighter faces left. Pass: every line of the brief's contact
table matches on the top row, and before and now are plainly different on
the phone-size row.

### Foot slide

```bash
xvfb-run -a godot --path . --rendering-driver opengl3 --fixed-fps 60 --script res://tools/godot/foot_slide.gd -- kairo move_right
```

Mean slide per planted frame against the body's speed. Measured here at
D-122: 0.5 cm mean (body 3.0 cm per frame); the log entries quote 0.3. Pass:
no worse than before your change. "Sliding on ice" was 3.6 cm.

### Stretched edges (skin)

```bash
python3 tools/blender/stretch_check.py assets/characters/kairo/kairo.glb KICK_LOW SPECIAL ATTACK
```

Pass: no worse than the move was before your change, and ideally near the
idle's level (idle 8; Low Kick 12; Rift Break carries 38 and the ultimate
shipped at 37; 41 was pulled back in D-098). High numbers mean a joint folded
too far or twisted: look at that frame from the front.

### Pose checker

`build_fighter.sh` prints it; by hand:
`python3 tools/blender/pose_check.py /root/work/out/kairo/pose_report.json`.
It lists biomechanical faults at the
first, middle and last frame of every action (centre of gravity outside the
feet, a twisted spine, a hand inside the torso, a floating foot). Pass: no
new line. Some faults are the move (a kicker's centre of gravity is outside
his standing foot); decide by looking, and say which were left.

### Arena view (game distance)

```bash
xvfb-run -a godot --path . --rendering-driver opengl3 --resolution 1280x576 --fixed-fps 60 \
    --write-movie /root/work/arena/f.png --script res://tools/godot/scene_video.gd -- "wait:30,attack_kick:4,wait:60" kairo
```

The real training scene with camera, arena and effects; the step list uses
the input action names from `scripts/input/input_actions.gd` (`attack_light`,
`attack_heavy`, `attack_kick`, `special`, `move_right` …), joined with `+`
for a combined input (`move_right+special:4` is Rift Break). It writes one
PNG per frame and an `f.wav` beside them. Use it when the
question is "does it show in play". `fight_shot.gd` gives a single
screenshot of a versus fight.

### Tests

```bash
godot --headless --path . --script res://tests/run_tests.gd            # 10-17 minutes; exit code 0 = all passed
godot --headless --path . --script res://tests/run_tests.gd -- kairo   # only files matching
```

Wait for the full run to end before committing. Report the real count.

## Known flags on Kairo at D-129 (the baseline)

So you can tell your own flags from the ones already there. Update this list
when a build changes it.

Pops: Low Kick f9 right toe (the strike); ultimate f18 and f37 right toe;
jump f43 both toes (landing); Rising Uppercut f5 left toe.

Motion report: Rift Break clean since D-129 (D-128 had FAST f11, swinging through
under the hip; before D-125 it had FAST f7, f9, f10 and
DWELL f11–18, the example of a leg that snaps up and waits); Leg Sweep FAST f3–4 (left wrist to the floor); Fireball FROZEN f20–24;
Knee Throw FAST f17 (right ankle 38 cm); ultimate several FAST (its later
hits are strikes the report does not know about); Flying Side Kick FOLD 0.28
(the kicking leg's chamber, f3); Knee Throw FOLD 0.31 (f15).

Body angles at contact:

| Move | Kicking knee | Pelvis from stance | Chest from stance | Twist | Lean back / side |
|---|---|---|---|---|---|
| Low Kick (approved) | 4° | 93° | 76° | 15° | 29° / 30° |
| Front Kick | **34°** | 43° | 21° | 21° | 20° / 0° |
| Flying Side Kick | 4° | 86° | 39° | 46° | 13° / 11° |
| Rift Break | 8° at contact, 10° at the peak (not locked) | 25° | 17° | 7° | 10° back at the peak, level at contact, 12° forward by frame 25 |

Stretched edges, worst frame: idle 8; Low Kick 12; Front Kick 10; Flying
Side Kick 19; **Rift Break 32 (frame 16, the hip at full flexion with a bent knee)**.

Pose checker (9 of 99 frames): Front Kick, Low Kick and ultimate with the
centre of gravity outside the feet; counter hook and string cross with the
spine twisted 51°; defeat wrist; Leg Sweep (right knee 43° off its foot, a
foot floating, and the **right hand inside the torso on f25**); surge foot.

Foot slide walking forward: 0.5 cm mean per planted frame.

The owner's reference pictures for the Low Kick, Flying Side Kick and Rift
Break (D-120) were sent in an earlier chat and are not in the repository.
Rift Break's current target is her written sequence,
`docs/images/references/kairo_rift_break_axe_kick.md`. New ones go into
`docs/images/references/`.

## What no check sees

Speed and weight as felt, the blend between clips in play, the look on a
real phone, and whether the move is the one the owner has in mind. Say so in
the report ("checked frame by frame, not watched"; "not verified on a
phone"). The owner's eye is the last check, which is why everything before
it has to be done properly: each thing she has to catch costs her a round.
