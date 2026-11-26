# Keying a move in `tools/blender/mocap_actions.py`

Contents: Where moves live · Frames and the move window · Coordinates and
signs · Channels · Eases · Special keys · Recipes (the patterns that solved
past problems) · The Flying Side Kick is keyed differently · Other fighters ·
Build switches · Before you rebuild.

## Where moves live

| What | Where |
|---|---|
| Kairo's ground attacks | `kairo_keys(moves, base, g, S)` → `out["<SLOT>"] = dict(...)` |
| Slots | `LIGHT`, `HEAVY`, `KICK` (Low Kick), `DOWN_HEAVY` (Front Kick), `DOWN_LIGHT` (Rising Uppercut), `DOWN_KICK` (Leg Sweep), `SPECIAL` (Origin Palm), `DOWN_SPECIAL` (Fireball), `FORWARD_SPECIAL` (Rift Break), `FOLLOWUP` (counter strike), `string_cross`, the counter stance and ultimate further down |
| Kairo's Flying Side Kick | in `build()`, the Kairo branch that fills `at = {...}` and calls `keyed_frames(n_air, at, settle=0, air=True, blend_in=0)` |
| Stance, block, idle life | `STYLES["kairo"]` (`pose`, `block`, `life`) |
| Walk, dash, jump, crouch, reactions | `walk()`, `dash()`, and the generic block in `build()` |
| How tracks become poses | `keyed_frames()` / `keyed_move()` in `build()`; `curve()`; `fit_stance()` |
| Other fighters | `<id>_set(c)` in `OWN_SETS`; new keyed sets use `class Kit` (`ryuen_set` is the example) |

Timing never lives here. It comes from `data/moves/*.tres` through
`tools/blender/export_move_timing.gd` (→ `moves_<id>.json`), which
`build_fighter.sh` runs for you.

## Frames and the move window

```python
a0, a1, T, hx, hz = win(moves["KICK"])
```

- Key frames are 0-based. `a0` = first active frame, `a1` = last active frame,
  `T` = total length. Startup includes the first active frame (a 9-frame
  startup hits on key frame 8). The reports, strips and frame data count from
  1: **key frame k is frame k + 1 there**.
- `hx`, `hz` = centre of the hitbox: metres forward of the fighter and
  height off the floor. The striking foot or fist has to be inside the box
  (`hitbox_size` in the `.tres`) on `a0 … a1`.
- Key relative to `a0`, `a1`, `T` (`a0 - 3`, `a1 + 5`, `T - 2`), not absolute
  frame numbers, so a later change of frame data moves the keys with it. Keys
  tied to the game's travel use `m0`, `m1` (see "Travel").

## Coordinates and signs

Model space, the fighter facing the opponent:

- `x`: across. For Kairo (left side leading) **+x is his left** = away from
  the game camera when he is P1. −x is toward the camera.
- `forward`: metres toward the opponent from the stance centre.
- `height`: metres above the floor.
- Lengths are in the fighter's own scale (`S` = hip height / 0.95).

Signs as used in Kairo's keys (confirm on a render when unsure; a wrong sign
shows at once in the strip):

| Channel | + | − |
|---|---|---|
| `pelvis`, `shoulders` (via `pel(d)`, `sho(d)`: degrees from the stance) | lead side further in (jab: `pel(12)`) | rear side comes through (cross: `pel(-40)`, Low Kick: `pel(-74)`) |
| `trunk` via `lean(f, sd)` | `f` forward (chop: `lean(8)`) | `f` back (Low Kick: `lean(-26, 24)`); `sd` is the side lean |
| `pelvis_h` via `low(d)` | — | `low(0.055)` sinks 0.055 × 1.22 = 6.7 % of standing height |

`pel`, `sho`, `low`, `lean` multiply by `X = 1.22`, the set's exaggeration.
So `pel(-74)` is about 90° of real turn (measured: 93°). Trunk lean does not
map so simply: `lean(-26, 24)` measures 29° back and 30° to the side on the
game model. Key toward the brief, then read the result off `body_angles.gd`
and correct; do not trust the typed number.

What the brief's words are in channels:

| Brief says | Channel |
|---|---|
| chest faces the opponent (square) | `shoulders` toward 0 |
| chest (or back) faces the camera, side-on | `shoulders` large, + or − by which side comes forward |
| hips turned over | `pelvis` far from the stance value, with the standing `*_toe` pivot |
| leans back / forward | `trunk` first value (− back) |
| leans away to the side | `trunk` second value (toward the lead side is +) |
| curled, chin tucked | there is no curl channel: a back lean plus `chin` (and `neck`) down |
| on the ball of the foot | `*_heel` up |
| sunk on the standing leg | `pelvis_h` lower |

## Channels

Body:

| Channel | Value |
|---|---|
| `hips` | `(forward of stance centre, 0)` — the pelvis carried forward/back |
| `hips_x` | pelvis sideways, + toward the lead side (a slip, a weight shift) |
| `pelvis_h` | hip height as a share of standing height |
| `pelvis`, `shoulders` | turn in degrees (side-on amount) |
| `trunk` | `(forward lean°, side lean°)` |
| `chin`, `neck` | chin drop and neck turn in degrees |

Legs on the floor:

| Channel | Value |
|---|---|
| `lead_foot`, `rear_foot` | floor mark `(across, along)` |
| `lead_toe`, `rear_toe` | turn-out in degrees (the pivot of a standing foot) |
| `lead_heel`, `rear_heel` | heel lift in metres (on the ball of the foot) |
| `knees` | knees pushed out |

A leg in the air:

| Channel | Value |
|---|---|
| `lead_foot_abs`, `rear_foot_abs` | ankle at `(x, forward, height, point)` |
| `point` | 1 = pointed along the shin, 0 = flat, **< 0 = toes pulled back** (−0.95 for heel or ball-of-foot kicks) |

A `*_foot_abs` track takes the foot over for the whole clip, including the
frames it stands on the floor: start and end it on the stance ankle
(`FL + (0.0,)` / `FR + (0.0,)`). `_feet_abs=(first, last)` limits it to a
frame range instead.

Arms:

| Channel | Value |
|---|---|
| `lead_hand`, `rear_hand` | wrist **relative to the head joint**: (across, forward, up) |
| `lead_hand_abs`, `rear_hand_abs` | wrist in **model space**: (x, forward, height) |
| `lead_elbow`, `rear_elbow` | how far the elbow swings out (0 tucked … 1 flared) |
| `lead_palm`, `rear_palm` | `"auto"`, or in / out / down / up / forward / back, or a vector |
| `lead_wrist`, `rear_wrist` | degrees the fist is cocked back |

Use `*_hand_abs` for a hand that has to be somewhere in the world (a fist in
the hitbox). Use `*_hand` for a hand that belongs to the body (a guard at the
face): it rides with the head when the trunk leans. A guard keyed in model
space was left behind by the hard lean and straightened the arm (a 14 cm pop,
D-110).

Stance values to start and end on: `L`, `R` (wrists), `FL`, `FR` (ankles),
`pel0`, `sh0`, `ph0`, `tr0`, `hips0`, `lf0`, `rf0`, `chin0`, `neck0`,
`base["lead_hand"]`, `base["lead_toe"]`, `head_z`.

## Eases

A key is `(frame, value)` or `(frame, value, ease)`. The ease says how the
value **arrives** at that key:

| Ease | Arrives | Use |
|---|---|---|
| `"in"` | slow away, snaps in | a strike landing, a foot planting |
| `"out"` | leaves fast, settles slowly | recovery |
| `"io"` | slow at both ends | a pose that is reached and left gently (air poses, chambers) |
| `"lin"` | even speed | a pendulum swing through the target |
| `"hold"` | stays on the previous value until this frame | a true wait |
| none | **passes through** on a smooth curve | everything in between |

Leave the ease off for in-between keys. Easing every key makes the body stop
dead at every pose: that was the first cause of "robotic" (D-090).

## Special keys in a move's dict

| Key | Does |
|---|---|
| `_recover=1.3…2.1` | plays the frames after `a1` that many times slower, so the return fills the recovery instead of ending early and standing still |
| `_hold` | frames the last active pose stays (set automatically for single strikes: ~16 % of recovery, max 4). It is a moving hold: the pose creeps on at 1/8 speed |
| `_lag` | in recovery, parts start home late: hips and feet 0, trunk 1, shoulders 1.5, hands 1, head 3 frames (default for single strikes) |
| `_air=(first, last)` | a hop inside a grounded move: on those frames the hips are placed from `pelvis_h` instead of standing the lowest foot on the floor |
| `_feet_abs=(first, last)` | `*_foot_abs` applies only on those frames |
| `_spring` | follow-through springs on loose parts (on by default for strikes) |

`keyed_frames(total, tracks, a1, settle=6, air=False, blend_in=2)` blends the
first frames out of the stance and the last `settle` frames back into it.

## Recipes

### Lock a limb straight

The two-bone solver never opens a limb past its `reach` share of full
length: 0.995 for arms and standing legs (an 11° bend), 0.9995 for a kicking
foot (`*_foot_abs`, ~3.6°). To get a truly straight leg, put the ankle target
**beyond the leg's length** so the solver saturates:

```python
hip_z = head_z - 0.60
arc_r = 1.25                       # longer than the leg: the knee locks
def arc(deg, x=FR[0] * 0.6):
    a = math.radians(deg)
    return (x, arc_r * math.cos(a), hip_z + arc_r * math.sin(a), 0.7)
# top -> strike on one arc around the hip: a straight leg swinging like a pendulum
"rear_foot_abs": [..., (a0 - 4, arc(98)), (a0 - 2, arc(62), "io"), (a0, arc(26), "in"), (a1, arc(-6), "lin"), ...]
```

Keep **every** key between "straight" and "strike" on that arc. One key
inside the leg's length bends the knee for those frames. Then prove it with
`body_angles.gd` (the build log's `legext 1.00` once hid an 11° knee).

### Spread a snap over two frames

A limb that covers its whole distance in one frame is reported as a pop and
reads as a glitch. Add an in-between key one frame before arrival, further
along than half way:

```python
(a0 - 3, chamber), (a0 - 1, half, "in"), (a0, out_far), (a0 + 1, out_hold), (a1, out_hold)
```

The same on the way back: a re-chamber spread over three or four frames
(one frame once moved the foot 0.46 m). If a bolder pose makes the pull-back
snap, space the return wider rather than shrinking the pose.

### The standing foot pivots

```python
"lead_heel": [(0, 0.0), (a0, 0.045, "in"), (a1, 0.045), (a1 + 6, 0.0)],
"lead_toe":  [(0, base["lead_toe"]), (a0, base["lead_toe"] + 60, "in"), (a1, base["lead_toe"] + 60), (a1 + 8, base["lead_toe"])],
```

Key it with the hip turn, arriving on the same frame.

### Hips first, chest later, limb last

Put the pelvis key a frame or two before the shoulders', and the fist or
foot last (cross: pelvis arrives `a0 - 2`, shoulders `a0 - 1`, fist `a0`).
For kicks the chest must end turned the same way as the hips: keep the
difference under about 45° (53° was flagged; 39° passed).

### Travel: the game moves him, the feet must agree

If the move has `move_distance`, the simulation slides the fighter forward
on frames `move_start … move_end`. In model space a foot that should stay on
one spot of the floor must therefore move **back** by the travel so far:

```python
m0, m1 = mvf["move_start"] - 1, mvf["move_end"] - 1
v = mvf["move_distance"] / float(m1 - m0 + 1)
def travel(k):
    return v * min(max(0, k - m0 + 1), m1 - m0 + 1)
# planted on frame k:
(k, (foot_x, foot_fwd - travel(k), foot_h, 0.0))
```

**How far one step goes.** If the rear foot is still on the floor when the
lead foot lands, the feet are then (travel so far + stance length) apart, and
by the end the supporting foot has to be near the hips. For Kairo that caps
a single step at about 0.7 m of travel (feet 0.83 m apart at lunge height,
D-127). More distance needs a second step or a hop, or less travel in the
data: say so to the owner rather than stretching the legs.

Cover the distance with something a body does: a step, a skip (plant → push
off → hop with `_air` → land ahead → body rides over the planted foot), or a
lunge off the rear foot. A planted pose gliding 1.4 m was "robotic and
unnatural" (D-115). On the first and last frame of a hop, check the head and
hands for a jump (`pelvis_h` in the air must meet the grounded height; a 7–13
cm body jump came from that).

### A hand that follows the body

Guard hands: `lead_hand` / `rear_hand` (head-relative). Striking hands:
`*_hand_abs`. The arm on the kicking side: reach it forward and down along
the leg with a near-straight elbow, home again through the recovery.

### The body follows the limb into the hit

When the trunk, hips and hands all drive with a kick, key their arrival on
the last active frame, not on the contact frame: everything landing on `a0`
moved the head 24 cm and a hand 30 cm in one frame (D-128). The limb hits,
the body finishes behind it.

### Recovery keys and `_recover`

`_recover` stretches key time after `a1`. With recovery `r` frames, keys
later than about `a1 + 1 + (r - 1) / _recover` are never played (Rift Break:
26 frames at 1.5 reaches `a1 + 17`). Keys written at `T - 3` in such a move
do nothing; the last frames are the blend back to the stance.

### Weight catches itself

```python
"pelvis_h": [...] + settle(T, a1 + 9, ph0, 0.018)     # a small dip as he comes home
**head(a0, a1, T, 3.0)                                 # chin into the blow, up late
```

### Foot shapes

`point` 1.0: instep/shin kicks (roundhouse). −0.7 … −0.95: ball of the foot
or heel (front kick, side kick, flying side kick). Run it from the chamber
(−0.3 or so) to full on contact and back to 0 as the foot is set down
through a low key (a toe flick of 9 cm came from skipping that key).

### Folding a leg

A leg folded to 0.28 of its length (ankle to hip) crushed the knee and
pinched the thigh (D-099). Chambers at 0.34–0.38 are in the game without
trouble. Stay above about 0.33 (`motion_report.py` prints FOLD below it) and
check the frame with `stretch_check.py` and from the front.

### A leg as direction plus extension (`_reach`), and the hinge (`_hinge`)

`<key>_reach` (D-129) caps how far a `*_foot_abs` leg may open (default
0.9995 = locked). Put the target beyond reach with `arc(angle)` and the leg
points that way, bent by exactly what `_reach` allows:

| `_reach` | 0.9995 | 0.996 | 0.985 | 0.975 | 0.95 | 0.82 | 0.62 | 0.56 |
|---|---|---|---|---|---|---|---|---|
| Knee bend | 4° | 10° | 20° | 25° | 36° | 70° | 103° | 112° |

So a kick that chambers and then extends is two tracks: the angle rising and
the reach opening (Rift Break: knee up at 0.56–0.63, opening to 0.996 at the
peak, 0.975 as the strike starts, 0.997 at the hit). Use plain position keys
(inside reach) near the floor and for the way back: a target beyond reach
that points below the floor drives the foot into it.

`<key>_hinge: 1.0` records which way the knee's hinge faces so the thigh
cannot roll about its own length. Set it on any kick where the leg is bent
while raised near or past vertical. Without it the thigh is turned by the
shortest way from its rest direction, which is undefined when the leg points
opposite to rest: all joint positions stay right and the mesh knee bends
backwards. `leg_report.py` shows it as a negative knee bend and a jump in the
non-flexion rotation. It is opt-in (a move without the key builds exactly as
before); only Rift Break uses it so far, and the ultimate's roundhouse and
the Flying Side Kick have not been checked for the same roll.

`rear_toe` to 0 as the leg lifts takes the stance's turn-out off the knee, so
it comes straight forward instead of out to the side.

### Extension is not straightness

For a limb of two near-equal bones, bend ≈ 2·acos(extension):

| Extension | 1.00 | 0.99 | 0.97 | 0.95 | 0.90 | 0.80 |
|---|---|---|---|---|---|---|
| Bend at the joint | 0° | 16° | 28° | 36° | 52° | 74° |

So "0.96 extended" is a plainly bent knee. When the brief says straight, the
target is beyond reach (see "Lock a limb straight") and the proof is the knee
column of `body_angles.gd`.

### Sharing the frames

Before building, lay the keys of the striking limb on the startup and count:
how many frames to the chamber or the top, how many there, how many into the
hit (technique-form.md "Sharing out the frames"). Rift Break before D-125
spent one frame rising and eight waiting: the keys were right, their frames
were not. A target that jumps from inside the leg's reach to an arc beyond it
locks the knee in a single frame; lead up to the arc with keys on a growing
radius, or, for a leg meant to be straight all the way, with one or two plain
keys near full reach just before the first `arc()` key (Rift Break, D-126).
Never put a `#` comment in the middle of a key list line: it silently drops
the keys after it on that line.

### Retiming an existing move

When frame data changes, or a move is reused for a string at other timing:
rescale the wind-up and recovery keys, but keep the last three frames into
the hit at their own spacing. A plain rescale moved the fist 46 cm in one
frame (D-113).

### Bold enough

Before building, compare your key values with the approved Low Kick's:
pelvis `pel(-74)`, shoulders `sho(-58)`, trunk `lean(-26, 24)`, standing leg
`low(0.055)`, toe pivot +60°, kicking-side hand 22 cm below the guard and
36 cm forward. If your must-reads move by a few degrees or centimetres where
the picture shows a different shape, it will not be seen.

## The Flying Side Kick is keyed differently

It lives in `build()`, not in `kairo_keys()`, and does not use the helpers:

- Degrees are raw (`pel0 - 88`, `(tr0[0] - 20, tr0[1] + 12)`): no `X = 1.22`.
- Stance ankles are `hl`, `hr` (not `FL`, `FR`); lengths are scaled by
  `S_fit`; `tuck` is the jump's leg tuck.
- Hands are head-relative (`lead_hand`, `rear_hand`), as they should be in
  the air.
- It is built with `keyed_frames(n_air, at, settle=0, air=True, blend_in=0)`:
  no stance blend, hips from `pelvis_h`, and the game adds the jump arc.
- `T = n_air - 1`; `a0`, `a1` come from the jump attack's data.

## Other fighters

Kairo is the only fighter with the full treatment (keyed set, holds, lag,
springs, living stance, own block, tuned walk). The other five use captured
strikes retimed by `strike()` plus keyed specials in their `*_set`. Drakon
and Ryuen are still on unfitted stances. To give another fighter a keyed set:
stance first (`docs/POSE_BLUEPRINTS.md`), then a `<id>_keys()` in that
fighter's own style, one fighter per task. Check which side the fighter leads
with before reading any reference: it changes which leg is nearer the camera.

## Build switches (environment variables)

| Switch | Effect |
|---|---|
| `KEYED_DEBUG=1` | prints wrists, feet, head and limb extension for every frame of keyed clips (`motion_report.py` reads it) |
| `GLITCH_SCAN=1` | prints joints that jump on one frame |
| `STANCE_ONLY=1` | builds the idle only, ~10 s (not shippable): for stance work |
| `KAIRO_MOCAP_RIFT=1`, `KAIRO_MOCAP_AIR=1` | the recorded-motion versions of Rift Break / Flying Side Kick (D-117), kept for comparison |
| `KAIRO_RECORDED=1` | the recorded-karate trial (D-095); the owner chose keyed |

`build_fighter.sh` always sets the first two.

## Before you rebuild

- A build takes from half a minute to a few minutes depending on the machine.
  Make all the changes for the move and read them once against the brief
  before building; when a sign or a direction is in doubt, a quick build and
  a strip settle it faster than reasoning.
- Keep the previous `.glb` or its frames for the before/now comparison.
- Comment the keys with the owner's words and the D-number, as the existing
  ones do. The next session learns the move's history from those comments.
