# Case history: the owner's words, what they meant, what fixed it

Read this before interpreting new feedback. The owner is consistent: the same
words have meant the same faults each time. Add a row whenever she corrects
or approves a move (in the same commit as the change).

Contents: How she gives feedback · Phrase book · Rounds per move · What
approval looked like · Process failures (ours).

## How she gives feedback

- Short, in screen terms, about what she sees on the phone or in the review
  video. "The other leg" means the other one on screen.
- She judges at game distance and at real speed. Subtle is the same as
  unchanged.
- "Wrong" without detail means the shape is not the move she has in mind:
  she has a specific picture. Ask for it.
- She notices arms and the upper body as much as the kicking leg.
- When it is right she says so plainly ("its good now, continue") and moves
  on.
- She has asked not to be asked for recordings or device tests, and not to
  be asked permission for requested work. A request for a reference picture
  is the one question she has asked for.

## Phrase book

| She said | It meant | What fixed it | Where |
|---|---|---|---|
| "they look unnatural and don't look like fighters" | generic captured motion, even timing, no wind-up, no hold | research (`docs/ANIMATION_RESEARCH.md`); retimed strikes; Kairo keyed pose to pose | D-083, D-084 |
| "keep improving" / "still not there yet" | faults that sampled frames hid | render **every** frame; measure wrists per frame: invisible wind-ups, 11-frame standstill, bent-arm jab | D-085, D-086, D-088 |
| "his ultimate does nothing, one hit and then nothing" | the sequence kept punching air after one hit | four real hits ten frames apart | D-087 |
| (phone recording) strikes are a twitch | fist out and gone in 50 ms | hold the last active pose 2–5 frames (moving hold) | D-089 |
| "still a bit robotic" | every part stops at every key and leaves on the same frame; frozen hold | keys passed through; recovery lag by body part; moving hold; living stance | D-090 |
| "he should move a bit while holding his stance" | idle too still (2 mm per frame) | breathing turns the chest, hands float, deeper sink | D-088, D-090 |
| "his fists don't seem fully closed" | finger curl too loose, thumb out | higher finger and thumb angles (`FIST`), checked close up | D-091 |
| "I saw some kick glitches" | one-frame pops: knee flipping, foot snapping at lift-off | `GLITCH_SCAN`; knee bends in the leg's plane; turn-out near the floor | D-092 |
| "walking and crouching look unnatural" | feet meeting under him, standing up out of the stance; crouch bowed forward | shuffle walk with the stance kept open; crouch sits on the rear heel | D-092 |
| "he needs to extend his leg more, also improve motion" | ankle stopped mid-hitbox with a bent leg and hips shoved forward | chamber, snap over two frames, leg 0.95–0.97, lean back | D-096 |
| "the foot is straight like a ballerina, not a kick" | pointed foot on a front kick | toes pulled back: `point` < 0 (ball of the foot) | D-097 |
| "the jump kick looks bad" | generic air attack: square to camera, legs hanging, arms frozen | his own flying side kick | D-098 |
| "his other leg gets deformed … leg needs to be fully extended" | non-kicking leg folded to 0.28 (mesh pinched); kicking leg bent | leg unfolded (keep folds above ~0.33); ankle target out of reach | D-099 |
| "walking looks like it's sliding on ice" | planted feet moving 0.7 m against the floor per step | planted travel = walk speed; loop length from step length; `foot_slide.gd` | D-106 |
| "arm inside the body" (stance) | rear forearm sunk in the armoured trunk | less side-on, rear fist to the cheek line; clearance measured | D-107 |
| "face slightly deformed sideways" | face vertices weighted to the neck, sheared by a 43° neck turn | head weights above the jaw; neck turn 28° | D-107 |
| "walks too fast" | walk speed (gameplay data) | 2.6 → 1.8 m/s in `kairo_movement.tres`; loop re-fitted | D-107 |
| "jump doesn't look like a fighter", "crouch squashed" | no crouch before take-off, legs hanging; legs folded flat | real take-off crouch, knees tucked, landing dip; shallower crouch | D-107 |
| "his body doesn't turn with the kick, also his arm goes sideways" | chest 27° behind the hips; arm 33 cm out to the side | chest turns over with the hips; arm to his own hip | D-108 |
| "his legs still move too fast" (walk) | each leg swung through in ~6 frames | foot planted 55 % of the loop: ~11-frame swing | D-108 |
| "he needs to lean with that kick, check how it's done in Street Fighter" | no counter-lean; the lean keyed was sideways, invisible from the side | lean **back** ~36° along the fighting line, head over the bent standing leg | D-109 |
| (picture) "like this" | hips fully turned over, hard lean away, leg reaching far, standing knee bent | pelvis −74, bolder everything; guard hand made head-relative | D-110 |
| "the hands swing totally wrong" | kicking-side arm thrown up and back behind the head | that arm reaches forward and down along the kick at chest height | D-111 |
| "its good now, continue" | **Low Kick approved** | — | D-112 |
| "his leg isn't fully extended" | 11° knee on the game skeleton though the log said 1.00 | solver `reach` 0.9995 for kicking feet; `knee_angles.gd` | D-114 |
| "they look bad, need big improvement, robotic and unnatural" (Rift Break, Flying Side Kick) | Rift Break glided 1.4 m on a planted foot; flying kick's other leg hung like a kneeling man | skip axe kick; leg tucked under | D-115 |
| "do they look good?" / "you did the other moves, why not now" | D-115's changes were correct and too small to see | bold shapes aimed like the Low Kick | D-116 |
| "nope still wrong, look at fighting games on web and learn" | still no picture: shape was a guess | tried recorded motion (D-117); it was the missing reference, not the method | D-117 |
| "no bro u got it wrong again" + Ryu art | the pose is specific: leg level, body compact | keyed to the picture | D-118 |
| "his upper body stays straight, that's wrong, also he is using the wrong leg" | picture read with trunk upright and the far leg | rear leg kicks; trunk leans back and away and curls | D-119 |
| (axe-kick sequence) "then he strikes with foot down" | the strike is the heel coming down, leg straight up first, body upright, compact guard | keyed to the sequence; wide arms and big lean removed | D-120 |
| "it needs to be with the other leg and the leg needs to be fully straight" | wrong leg; knee not locked through the swing | other leg; every target on an arc beyond the leg's length | D-121 |
| "he needs to use the other leg, also the movement is too fast and unnatural" → "the leg nearer the camera" | leg named in screen terms; phases had too few frames | asked which leg; rear leg; startup 16 → 22, recovery 22 → 26 (balance change) | D-122 |

| (an eight-step written axe-kick sequence) "lift the kicking leg straight upward ... keeping the knee relatively extended ... Do NOT ... chamber ... heel as the striking point ... retract the leg, lower it naturally" | no knee-up at all; straight leg up and down; heel first; no hanging leg after the hit. She will write the motion out when pictures have not got her what she wants: treat it as the reference and follow it step by step | chamber removed, leg locked from lift to floor, flexed foot, peak vertical, `_hold` 1 | D-126 |

| "Whats better" (the skip forward or kicking on the spot), then "Do it" | she wants a recommendation, not a list of options; give one, with the cost in a sentence | a step in instead of the hop; travel 1.4 → 0.7 m, named as a balance change | D-127 |

| "Does it look right to u", then "Fix all you just said" | she wants the honest list of what is still weak, not reassurance; she will then ask for all of it. Say only what the frames show, and say that motion cannot be watched here | five faults named from the strip and `body_angles.gd`, all fixed | D-128 |

| (a working rule) "inspect the rig ... verify their rotation axes. Do not guess bone orientations. Test ... with a small number of poses ... Preview ... from the side view ... Do not report ... complete until ... previewed and validated" | a standing rule for every animation, not only this move | `rig_inspect.gd`, `leg_check.gd`, `leg_report.py`; the validation found a thigh rolling half a turn when a bent leg is overhead | D-129 |
| (a full specification: six phases, biomechanics, a list to avoid, thirteen checks) | the knee rises first and the leg extends progressively; not locked; impact pose with recoil. Her newest text replaces older ones where they differ: this reverses "do not chamber" from the day before | re-keyed by phase as direction plus extension; each of her thirteen checks answered with a number | D-129 |
| "Check all his skills, look for maximum improvement in animation and motion, do not stop until everything is flawless, do trial and error" | go through the whole set yourself and fix what the checks show, round after round, without asking; approved and pending moves stay | every move audited; frozen recoveries, bent kicking legs and rolled thighs fixed | D-130 |
| "These need to be fixed" + another AI's written critique of the video (foot sliding, weight, recoil, twinning, linear easing) | she will get second opinions on the video and pass them on; measure each claim first, fix the true ones, and tell her plainly which ones the numbers do not support | `weight_report.py`; stepping feet lift, dashes, recoil, crouch clips, landing, knockdown | D-131 |
| "Fix all that u didn't fix and send me the video of all moves fixed again" | when a report lists things left undone, she wants them done, including the ones that need a balance change or touch an approved move; say plainly afterwards what changed in the game's numbers | both kicks over their foot (Front Kick hitbox 0.60 -> 0.78 m), jab trunk, axe-kick hands | D-132 |
| a second outside critique (foot skid, root midway, crouch, arm punches, no recoil, rigid head, twinning, flat knockdown, floaty jump) | as before: measure each point; this time the worst fault (the ultimate's feet skating 1.3 m) was real and had been hidden by measuring in body space | step planner, punch hip drive, crouch heel roll, head lag, knockdown arc, jump hang (a feel change), review video with travel and hit freeze | D-133 |
| a third outside critique (slides against the floor marks, flat landings, pelvis not over the foot, rigid spine, twinning, arm punches, uniform freeze, snappy recoveries) | three of nine were the review video's own doing (loop repeats snapping back, cuts, no camera shake): a reviewer judges the video, so the video must show what the game shows | `curl` channel, `hips_x`, ball-first landings, stance forearms, hand drag; camera-follow video with title cards and hit shake | D-134 |
| a 21-point review of the D-134 video (shaking after the dash, crouch snaps, block snaps, ultimate stall, knockdown/get-up pop, dash twitch, open guard, jab pulls back, three punches one pose, walk on the spot, weak low block, flex special, uppercut a raised arm) | five were the renderer (its clock during the crouch clip, a camera that followed him all the way, the long freeze on the wrong hit); the rest real: targets inside reach left arms bent, the cross over-turned, the counter was a copy of the cross, the anti-air aimed from the hitbox | renderer fixed; targets beyond reach, chest stops near square, a lead hook, aim from the body not the box; timing changes in data | D-135 |

Faults found by the checks before she had to name them:

| Found | Fix | Where |
|---|---|---|
| The thigh bone rolled half a turn about its length when the bent leg was overhead: the mesh knee bent backwards though every joint position was right | `<key>_hinge` in `fit_stance` / `retarget` | D-129 |
| Uppercut, Leg Sweep and fireball held a pose and popped home: recovery keys later than `_recover` plays | the way home keyed inside the reachable time | D-130 |
| Origin Break's roundhouse and the Leg Sweep bent the mesh knee backwards (thigh roll, as in D-129) | `_hinge` on every raised kick, as a weight | D-130 |
| Rift Break's leg snapped to vertical in one frame and waited eight at the top (likely what "too fast and unnatural" still meant) | the rise re-spaced over seven frames on a growing radius; no frame data change | D-125 |

## Rounds per move

| Move | Rounds | Why |
|---|---|---|
| Low Kick | 4 (D-108 … D-111), 2 after the picture | first two were guesses from words |
| Front Kick | 2 (D-096, D-097) | each a named, measured fault |
| Flying Side Kick | 8 entries so far (D-098, 099, 112, 115–119) | no picture until D-118; then misread (leg, trunk) |
| Rift Break | 13 entries so far (D-112, 114–117, 120–122, 125–129) | no picture until D-120; leg misread twice; timing; then her written sequence |

The pattern: with a picture and a careful reading, one or two rounds. Without,
any number.

## What approval looked like (Low Kick)

Big, aimed changes matching a picture: hips turned over ~90°, trunk leaning
back 29° and away 30° (measured), standing leg sunk, kicking-side arm along the kick, guard hand at
the face, leg near straight reaching far. Checked from the side, the front
and in the arena camera.

## Process failures (ours), so they are not repeated

- Reworked a move without a reference picture (several times).
- Read "the other leg" anatomically instead of on screen.
- Sent changes too small to see, then defended the video as "correct".
- Trusted the build log's limb extension instead of the game skeleton.
- Judged from six sampled frames, or from the three-quarter view.
- Pushed before the test run had finished; the push failed a test that
  named the striking limb (D-121).
- Godot's import cache can keep the old model after a `.glb` is swapped
  (HANDOFF: delete `.godot/imported/<id>.glb-*` before `--import`);
  `build_fighter.sh` does it every time.
- A share.google link was retried instead of asking for the image.
- Changed timing without at first calling it a balance change.
- Measured feet in body space on moves the game carries forward: the
  ultimate's feet skated 1.3 m and every check said OK (D-133). Add the travel.
- Filmed walks and dashes on the spot: planted feet then look like sliding.
- Filmed loops by repeating the same frames (he snapped back 0.8 m each
  repeat) and cut between clips without a break: both read as foot slides.
- Sent a video called "all moves" that left out five of them (the default
  list in `tools/review_video.py`); check the list against the move table.
