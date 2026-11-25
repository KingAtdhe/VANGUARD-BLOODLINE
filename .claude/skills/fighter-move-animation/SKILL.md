---
name: fighter-move-animation
description: >-
  How to make or fix a fighter's animation in VANGUARD: BLOODLINE so it reads
  like a real fighting-game move the first time: kicks, punches, specials,
  throws, jumps, walks, stances, hit reactions. Use this whenever the owner
  comments on how a move looks ("the kick looks robotic / wrong / unnatural",
  "wrong leg", "leg not straight", "he doesn't lean", "hands swing wrong",
  "too fast", "sliding"), sends a reference picture of a move, asks for a new
  move or a new fighter's move set, or whenever you are about to edit
  `tools/blender/mocap_actions.py` (`kairo_keys`, `STYLES`, `*_set`, `walk`,
  the jump attack), rebuild a fighter `.glb`, or make a review video. Also use
  it before answering "does it look good?" about any animation. It holds the
  reference-reading method, the martial-arts form of each technique, the
  keying channels, the measured checks with their pass marks, and the case
  history of every correction the owner has made.
---

# Fighter move animation

## Why this skill exists

Three kicks (Low Kick, Flying Side Kick, Rift Break) took fifteen decision-log
entries between them (D-108 … D-122). Each round cost the owner a build, a
video and an install, and most ended with "still wrong". Looking back, almost none of those rounds failed on
skill at keying. They failed earlier:

- **No target.** Moves were reworked from a name ("axe kick") instead of from a
  picture. As soon as the owner sent a picture, the move was right in one or
  two rounds (Low Kick: picture in D-110, approved after D-111).
- **The picture was misread.** Wrong leg twice, trunk kept upright when it
  leans, the arm thrown back when it reaches forward.
- **The change was too small to see.** Careful, small changes were correct
  on paper and invisible at game distance (D-115, as D-116 found).
- **It was checked on the wrong thing.** The build log said the leg was
  straight (1.00); on the game skeleton the knee was bent 11° (D-114).

So the order of work below is the point of this skill. Keying comes fourth.
Everything before it is about being sure what the move should look like and
what it looks like now.

The owner's standing rules still apply. She gives them at the start of each
chat; the picture rule is also in `docs/HANDOFF.md`, the review-video rule in
`CLAUDE.md`. They are: do requested work without asking permission; **ask for a reference picture before reworking a
move**; deliver test APKs as GitHub release links; never ask her for
recordings or device tests; send a real-speed review video after any
animation change and say it was checked frame by frame, not watched.

## Kairo's moves at a glance

Names differ between the game, the data, the keys and the clips. Use this
table instead of searching.

| Move (input) | Data `data/moves/` | Slot in `kairo_keys` | Clip suffix | Frames s/a/r | Owner |
|---|---|---|---|---|---|
| Light Punch (L) | `kairo_light_punch` | `LIGHT` | `ATTACK_LIGHT_01` | 5/3/10 | — |
| One-Two Cross (L, L) | `kairo_string_cross` | `string_cross` | `ATTACK_STRING_CROSS_01` | 8/3/17 | — |
| Heavy Punch (H) | `kairo_heavy_punch` | `HEAVY` | `ATTACK_HEAVY_01` | 12/3/19 | — |
| **Low Kick** (K) | `kairo_low_kick` | `KICK` | `KICK_LOW_01` | 9/4/15 | **approved** (the D-111 version) |
| **Front Kick** (down + H) | `kairo_body_hook` | `DOWN_HEAVY` | `ATTACK_BODY_HOOK_01` | 9/3/15 | reworked D-096/097 |
| Rising Uppercut (down + L) | `kairo_rising_uppercut` | `DOWN_LIGHT` | `ATTACK_RISING_UPPERCUT_01` | 5/5/24 | — |
| Leg Sweep (down + K) | `kairo_leg_sweep` | `DOWN_KICK` | `KICK_SWEEP_01` | 8/3/20 | — |
| Origin Palm (S) | `kairo_origin_palm` | `SPECIAL` | `SPECIAL_ORIGIN_PALM` | 14/5/24 | — |
| Fireball (down + S) | `kairo_fireball` | `DOWN_SPECIAL` | `SPECIAL_FIREBALL` | 14/1/16 | — |
| **Rift Break** axe kick (forward + S) | `kairo_rift_break` | `FORWARD_SPECIAL` | `SPECIAL_RIFT_BREAK` | 22/4/26, travels 0.7 m (one step in) | awaiting her OK (D-127; target: her written sequence) |
| Rift Guard (back + S) / Counter Strike | `kairo_slip_counter` / `kairo_counter_hook` | counter stance / `FOLLOWUP` | `SPECIAL_SLIP_COUNTER` / `ATTACK_COUNTER_HOOK_01` | 4/13/14, 5/3/16 | — |
| Knee Throw (L + K) | `kairo_knee_throw` | throw | `THROW_KNEE_01` | 5/2/26 | — |
| **Flying Side Kick** (any attack in the air) | `kairo_jump_attack` | in `build()`, not `kairo_keys` | `JUMP_ATTACK` | 6/12/6 | awaiting her OK (D-119) |
| Origin Break (ultimate) | `kairo_origin_break` | ultimate | `ULTIMATE_ORIGIN_BREAK` | 7/31/18 | — |

`kairo_kick.tres` ("Kick", mid height) is **not** Kairo's move: it is the old
shared kick of Warden, Sentinel and the dummy, and Kairo's model has no clip
for it. Kairo has no standing body-height kick on the Kick button.
`move_shot.gd` filters by the data id (`kairo_low_kick`).

Frame numbers: frame data, `motion_report.py`, `frame_strip.py` and
`body_angles.gd` count from 1 (contact = the startup number). The keys in
`mocap_actions.py` count from 0 (key frame k = frame k + 1).

## The loop

Work one move at a time. Finish it (or stop on a question) before the next.

### 1. Decide: a fix or a rework

| The owner says | It is | Do |
|---|---|---|
| A named, local fault: "leg isn't fully extended", "arm goes into his body", "foot like a ballerina", "sliding", "the leg flies up too fast and then waits" | a **fix** | Measure it (step 3), fix it, no picture needed |
| A shape judgement: "looks bad", "wrong", "stiff", "unnatural", "robotic", "not like a fighter", "do it like Street Fighter" | a **rework** | Get a reference picture first |
| A new move, or an existing one "but higher / different" | a **rework** | Get a reference picture first (or use the one she sent) |
| A shape judgement, and your measuring finds a plain fault (a bent leg, a frozen stretch) | still a **rework** | Ask for the picture, and say in the same message what you found; fix the plain fault with the rework, not instead of it |

"Too fast" can be either. Count the frames each phase gets
(`motion_report.py`, the strip): if the phases are badly shared (two frames
to raise a leg, nine waiting at the top), it is a fix by re-spacing keys. If
every phase is already tight, the move needs more frames, and that is the
owner's call (see "When the move's data has to change").

For a rework with no picture in hand, **ask first, then measure while you
wait, and build nothing**. A guess built "in the meantime" is another failed
round for her. The ask is one short message, for example:

> I'll redo Kairo's Front Kick (down + heavy). To get it right the first
> time, please send me one picture or screenshot of the exact kick pose you
> want, from any game. Please attach the image itself: I can't open
> share.google links.

A written step-by-step description from her counts as the reference (Rift
Break, D-126): save it beside the pictures and follow it step by step.

If she answers with only a game or character name, say what you will base it
on and build from `references/technique-form.md`, flagged as built without a
picture.

Questions worth one message to her, and no others: the reference picture; a
striking limb that is truly ambiguous in screen terms; and a request that
would overwrite a move she has approved or change what a button does. For
everything else, decide, do it and report.

`references/case-history.md` lists what each of her past phrases turned out to
mean. Read it before interpreting new feedback; she is consistent.

### 2. Read the reference and write the pose brief

Save her picture in the repository (`docs/images/references/<fighter>_<move>.png`;
the folder's README says which past pictures are missing)
so later sessions can compare against it. Then read
`references/reading-a-reference.md` and fill in
`assets/pose-brief-template.md`. The brief is short and written in **screen
terms** (nearer the camera / farther, toward the opponent / away), because
that is how the owner sees and describes the move, and because "left/right"
and "lead/rear" have each been read wrongly before.

The brief has to pin down, at the contact pose: which leg or arm strikes, how
far the hips have turned, where the trunk leans, the standing leg, both arms,
the head, the shape of the striking foot or hand, and the two or three things
that make the silhouette (the "must-reads"). Then the wind-up and the way
back.

A **fix** needs no full brief, only its one line: the fault, the number that
shows it, and the number it should be ("kicking knee 37° at contact; should
be under 5°").

Put the brief (or the fix line) into the DECISION_LOG entry for the change.

### 3. Measure what is there now

Before touching a key, look at the move as it is and fill the brief's "now"
column with numbers. This turns "make it better" into a list of differences,
and it leaves the before pictures and video for the owner.

```bash
S=.claude/skills/fighter-move-animation/scripts
# hips, chest, lean, knees, ankles on the game model, every frame
godot --headless --path . --script res://tools/godot/body_angles.gd -- kairo KICK_LOW_01
# wrists and ankles per frame, pops, snaps, dwells, frozen stretches, contact line
python3 $S/motion_report.py /root/work/build_kairo.log KICK_LOW_01
# every frame in the game's side view (long moves: two halves with --from/--to)
python3 $S/frame_strip.py kairo KICK_LOW_01 /root/work/before_kick.png
# the before video, while the old model is still installed
python3 tools/review_video.py kairo /root/work/before.mp4 --clips KICK_LOW_01
```

On a fresh machine (no `godot`, no `bpy`) set up first: `references/checks.md`
→ "Machine" (about fifteen minutes, mostly the first asset import; start it
before reading the reference). Then run `build_fighter.sh` once before
editing: it produces the baseline log that `motion_report.py` reads and that
later builds are compared with.

### 4. Key it

Read `references/keying.md` (the channels, eases, special keys, and the
patterns that solved past problems) and the technique's entry in
`references/technique-form.md` (what the body does in a real one, how its
frames are shared out, and what reads in a side view).

Three rules decide whether the result is seen at all:

- **Aim at the brief, and go all the way.** If the picture shows the hips
  turned over, turn them over (the approved Low Kick turns the pelvis 93° from
  the stance and leans the trunk 29° back). A change that is correct but timid
  does not show at game distance and counts as "nothing changed" to the owner.
- **Key the body, then the limb.** Feet, hips and trunk carry the move; the
  striking limb rides on them. A kick keyed as a leg moving on a still body is
  what "robotic" has meant every time.
- **The move's data is the game.** Animation follows the startup, active and
  recovery frames and the hitbox in `data/moves/*.tres`. Changing those is a
  gameplay change (see "When the move's data has to change").

### 5. Build and pass the gates

```bash
bash $S/build_fighter.sh kairo          # under a minute to a few; writes /root/work/build_kairo.log
python3 $S/motion_report.py /root/work/build_kairo.log KICK_LOW_01
godot --headless --path . --script res://tools/godot/body_angles.gd -- kairo KICK_LOW_01
```

`build_fighter.sh` exports the move timings, builds with the debug switches
on, installs the `.glb`, clears Godot's cached import of it (HANDOFF warns
that a stale cache can leave the old model in place), re-imports, and lists the flags
that are new against the previous build.

Then the gates, detailed in `references/checks.md` (which also lists the
flags Kairo already carries, so you know what is yours):

| Gate | Tool | Pass |
|---|---|---|
| No one-frame pops or snaps | `motion_report.py` (POP, FAST), flags diff | no new flag; the frame the strike lands is the only excuse |
| No waiting limb, no frozen body | `motion_report.py` (DWELL, FROZEN), strip | none inside a move, unless the pose is the point (a counter stance) |
| Limb as straight as the brief says | `body_angles.gd` knee column | ≤ 5° when "fully straight", on the frames the brief names (log `legext` 1.00 is not proof; 0.96 is already ~32°) |
| Hips, chest, lean as the brief says | `body_angles.gd` | the brief's numbers, within what the eye would notice (~10°); twist under ~45° |
| Strike lands in the hitbox | `move_shot.gd` (red box) | striking foot/fist inside the box on the active frames |
| Feet do not skate | `foot_slide.gd`, strip | no worse than before (walk: ~0.3–0.5 cm per planted frame); moves with travel: keying.md "Travel" |
| Skin holds | `stretch_check.py` | no worse than the move was before; aim near the idle's level (idle 8; most moves 10–20; Rift Break carries 38 today; 41 was pulled back in D-098) |
| Body can do it | pose checker (printed by the build; `/root/work/out/<id>/pose_report.json`) | no new line; no arm inside the trunk |
| Tests | `run_tests.gd` | all pass, and **wait for the run to finish before committing** |

A gate that fails is fixed, or it is named in the report with the reason it
was left. Do not quietly skip one.

### 6. Look at it — every frame, game view, next to the reference

Numbers catch broken joints. They do not catch a move that is clean and wrong.
So:

```bash
python3 $S/frame_strip.py kairo KICK_LOW_01 /root/work/now_kick.png
python3 $S/compare_reference.py --ref <her picture, saved in step 2> \
    --now /root/work/now_kick_frames --frame 9 \
    --before /root/work/before_kick_frames --out /root/work/compare_kick.png
```

Open the strip and the comparison with Read and go through the brief line by
line against the contact frame: leg, hips, trunk, standing leg, each arm,
head, foot. Then read the strip left to right for the motion: does a wind-up
exist, does the body lead the limb, is the contact held, does anything stand
still or jump. (For a fix: is the named fault gone, and did anything else
move.)

Three habits that each caught something the others missed:

- **The game's side view first.** A three-quarter view flatters; a side lean
  that looks strong from the front points at the camera in play and vanishes
  (D-109).
- **Every frame, not six.** Sampled frames hid invisible wind-ups, an
  eleven-frame standstill and a soft jab (D-085, D-086).
- **At game size, before against now.** `compare_reference.py` adds a row at
  the size the fighter has on a phone. If before and now look the same there,
  the owner will say nothing changed, and she will be right (D-116).

If the contact frame does not match the brief, go back to step 4. Do not send
it "to see what she thinks".

### 7. Ship and report

1. Full tests green (actually finished).
2. `docs/DECISION_LOG.md` entry: her words, the brief, what changed, what was
   checked and how, what is left. Update `docs/HANDOFF.md` ("Latest"),
   `docs/COMBAT_FRAME_DATA.md` if move data changed, the baseline list in
   `references/checks.md` if flags changed, and add her words to
   `references/case-history.md`.
3. Review video of the clips that changed:
   `python3 tools/review_video.py kairo /root/work/now.mp4 --clips KICK_LOW_01`,
   then before and now side by side, real speed then half speed:
   `bash $S/before_after_video.sh /root/work/before.mp4 /root/work/now.mp4 /root/work/review.mp4`.
4. Commit, push, wait for the APK workflow to go green, take the release link.
5. Message to the owner, short and in plain words:
   - what you changed, as she would see it ("he now leans back and the kicking
     leg is the one nearer the camera"), not key names or degrees;
   - the video, and the sentence that it was checked frame by frame, not
     watched;
   - the APK link, and the reminder to uninstall the previous test app;
   - "not verified on a phone";
   - anything a gate still flags, in one line.

Then stop. The owner confirms a move or sends the next correction; do not
start the next move's rework on your own.

## What makes motion read as a fighter

Short version of `docs/ANIMATION_RESEARCH.md` plus what the owner's feedback
added. `references/technique-form.md` applies these to each technique.

1. **Wind-up exists and is seen.** Even two frames. The body coils opposite to
   the strike, as one continuous move, not a pose reached early and frozen.
2. **Ground → hips → chest → limb.** The standing foot pivots and the hips
   turn first, the chest a frame or two later, the limb last. Chest and hips
   end turned the same way; more than ~45° of twist between them reads as "his
   body doesn't turn with the kick".
3. **The trunk answers the limb.** A leg going out sends the upper body the
   other way, along the fighting line (back, away from the opponent), so leg
   and trunk make one long line. Upright over a kick reads as a pole.
4. **Limbs travel on arcs and arrive late and fast.** A snap is spread over
   two frames with an in-between key; over one frame it is a pop.
5. **Every phase gets its share of the frames.** A leg that reaches the top in
   two frames and waits there for nine is "too fast" and "just stands there"
   at once. The rise takes most of the startup; the top is a moment.
6. **Contact is held, alive.** Two to five frames, creeping forward, never a
   freeze.
7. **Recovery fills its frames.** Hips and legs start home first, chest, arms
   and head after; a small overshoot and a dip as the weight settles. Nothing
   stands waiting for the clip to end.
8. **Feet belong to the floor.** A planted foot does not move against the
   ground. If the game carries the fighter forward during the move, the feet
   must step, skip or hop to cover it.
9. **Arms have jobs.** The same-side arm goes with the kicking leg (forward
   and down along it), the other hand guards the face. An arm flung sideways
   or up behind the head has been rejected each time.
10. **One level of exaggeration.** Past real life, the same amount across the
    set (`X = 1.22` for Kairo).

## When the move's data has to change

Animation cannot always meet the brief inside the move's numbers: Rift
Break's axe kick with a skip did not fit 16 startup frames (D-122); a "kick
to the body" needs the hitbox at body height, not shin height.

- Change `data/moves/<move>.tres`, never a number in the animator.
- Timing, hitbox position or size, hit level (low / mid / high), travel:
  each is a **balance change**. Say so in the report with before and after,
  the on-block number, and what it does to combos and to the tests that
  encode them (Rift Break stopped linking after the Low Kick; the Low Kick
  being LOW is checked in `test_kairo_moves.gd` and `test_jump_crouch.gd`).
- "Slower" from the owner is a request for this, once the phases are already
  well shared.
- If the request would replace a move she has approved, or change what a
  button does (the low kick becoming a body kick leaves him without a quick
  low attack), ask her which she wants before building: change it in place,
  or keep it and add a move.
- Update `docs/COMBAT_FRAME_DATA.md`. `tests/integration/test_kairo_model.gd`
  names the striking limb of each move: swap the leg, update the test in the
  same commit.

## Files

- `references/reading-a-reference.md` — turning a picture into a pose brief.
- `references/technique-form.md` — what each kick and punch does in the body,
  how its frames are shared, and what must read in the side view. Read the
  entry for the move in hand.
- `references/keying.md` — channels, eases, special keys, recipes, switches.
- `references/checks.md` — every check, its command, pass mark and blind spot;
  machine setup; the flags Kairo carries now.
- `references/case-history.md` — the owner's words, what they meant, the fix.
- `assets/pose-brief-template.md` — the brief to fill in at step 2.
- `scripts/` — `build_fighter.sh`, `motion_report.py`, `frame_strip.py`,
  `compare_reference.py`, `before_after_video.sh`. Project tool added with
  this skill: `tools/godot/body_angles.gd`.

Keep this skill current: when the owner approves a move or corrects one, add
the lesson to `case-history.md` (and to `technique-form.md` if it is about
form) in the same commit as the change. That file is the project's memory of
her eye.
