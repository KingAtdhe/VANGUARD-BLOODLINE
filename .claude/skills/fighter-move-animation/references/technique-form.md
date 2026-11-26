# Technique form: what the body does, and what has to read

For each technique: how a trained fighter does it, what a fighting game shows
of it, and what must be visible in our side view. Use this for the parts of a
move the owner's picture does not show (wind-up, chamber, return), and to
sanity-check a pose brief. Where the owner's picture disagrees with this
file, the picture wins.

Contents: Universal mechanics · Sharing out the frames · Reading in the side view · Kicks (low
roundhouse, mid/high roundhouse, front kick, side kick, axe kick, flying side
kick, sweep, knee, spinning/back kicks) · Punches (jab, cross, hook,
uppercut, palm/lunge) · Movement (stance, walk, jump, crouch) · Reactions.

"Status" lines say what the owner has said about Kairo's version.

---

## Universal mechanics

**Power comes up from the floor.** Foot pushes and pivots → hips turn → trunk
turns → shoulder → limb. In animation that is an order of *starting*: the
standing foot's pivot and the hips begin, the chest follows one or two frames
later, the limb goes last and fastest. If every part starts and stops on the
same frame, it is a mannequin being rotated.

**The standing foot pivots, on the ball, heel up.** How far tells you the
kick:

| Kick | Standing foot turns out (toes away from the target) |
|---|---|
| Front kick | 0–45° |
| Roundhouse | 90–135° (a full one near 180°) |
| Side kick | ~180°: heel points at the target |
| Axe kick | 0–45° |

A roundhouse or side kick on an unpivoted foot cannot turn the hips; the
result is the "body doesn't turn with the kick" look. Key the pivot
(`*_toe`) and the heel lift (`*_heel`) with the hip turn.

**Chamber, extend, re-chamber, set down.** Snap kicks fold the knee up first
(the chamber), open from the knee, fold back, then put the foot down. Swing
kicks (axe, crescent) go out with a straight or nearly straight leg and do
not re-chamber. A kick that goes from the floor to the target in a straight
line, or drops from the target straight to the floor, has no technique in it.

**Counterbalance.** The leg is 15–20 % of body weight. When it goes out, the
trunk goes the other way to keep the weight over the standing foot. The
higher or longer the kick, the more lean. The head stays roughly over or
behind the standing foot. An upright trunk over an extended leg looks stiff
and, on a real body, falls over.

**Hip position decides the kick's family.** Hips square to the target: front
and axe kicks. Hips turned over (kicking hip on top, rolled toward the
target): roundhouse. Hips side-on with the kicking-side hip toward the
target: side kick. The foot shape follows: ball or heel for front, instep or
shin for roundhouse, heel or blade for side, heel for axe.

**Arms.** The arm on the kicking side swings *with the leg's direction*, down
and forward along the thigh or toward the hip, as a counter-rotation to the
hip turn. The other hand stays at the face. Not sideways, not up behind the
head. In punches, the non-punching hand returns to the chin (boxing) or pulls
back to the ribs (karate hikite, Kairo's style).

**Eyes on the opponent, chin down.** Through every phase. The head turns
less than the chest and arrives last on the way home.

**A fighting game pushes all of this further.** Bigger hip turn, deeper lean,
longer line, contact held longer than life. One level across the set
(Kairo: `X = 1.22`).

## Sharing out the frames

The move's startup is fixed by its data; how the animation spends it is the
animator's choice, and spending it badly is what "too fast", "weird" and
"just stands there" have meant. Rough shares of the startup frames:

| Kind | Load / sink | Chamber or rise | Extension into contact | At the top |
|---|---|---|---|---|
| Jab | 1 frame | — | the rest, the fist over 3 frames | — |
| Cross, palm | 50–60 % (one continuous coil) | — | last 2–3 frames | — |
| Snap kick (front, side, roundhouse) | 20–30 % | 35–45 % (knee up, hips turning) | last 2 frames, with an in-between key | — |
| Axe / crescent (a swing) | 15–20 % | 50–60 % rising, steadily | last 3–4 frames, coming down | **1–3 frames**, still moving |
| Sweep | 30 % (drop) | — | the arc over 3–4 frames | — |

Signs it is wrong, all visible in `motion_report.py`: a limb that covers most
of its path in one or two frames early in the startup (FAST away from the
strike); a raised foot keeping its height for six or more frames (DWELL); a
wind-up pose reached early and held. After the hit: a moving hold of 2–5
frames, then a return that uses the whole recovery (set-down in the last
third), not a return that finishes early and stands.

If the shares are right and it still reads as too fast, the move needs more
frames: that is the owner's decision (SKILL.md "When the move's data has to
change").

## Reading in the side view

The game camera looks across the fighting line. So:

- **Along the fighting line reads; across it does not.** A lean back (away
  from the opponent) is seen in full. A lean sideways across his body points
  at or away from the camera and is nearly invisible (D-109). The same for
  arms: forward/back/up/down read, in/out barely.
- **Depth collapses.** A limb that crosses in front of the body merges with
  it. Keep the striking limb and the guard hand outside the trunk's outline
  on the contact frame. Check the silhouette.
- **The nearer limb covers the farther one.** A kick with the far leg is
  partly hidden behind the standing leg and the body. That is one reason the
  owner asks for "the leg nearer the camera".
- **Turning the hips over shows as the back or the chest coming to the
  camera.** That is how hip rotation reads from the side; if the outline of
  the torso does not change width during the move, the turn is too small.

---

## Kicks

### Low roundhouse (Kairo: Low Kick, `KICK` / `KICK_LOW_01`)

Status: **approved by the owner** (the D-111 version; "its good now,
continue", quoted in D-112). The model to copy.

- Load: weight shifts onto the lead (standing) leg, a small step or sink;
  shoulders counter-turn a little the other way.
- Standing foot pivots out ~60° or more on the ball, heel up; standing knee
  bent, sinking.
- Hips turn over: the kicking hip rolls on top and through. Measured on the
  approved version at contact (`body_angles.gd`): pelvis 93° from the stance,
  chest 76°, so only 15° of twist between them.
- The shin whips round on an arc, from outside in; it does not go straight
  forward. Leg straight at contact (knee 4° measured, easing to ~13–28° over
  the other active frames as it rides through), contact with the shin/instep,
  foot pointed.
- Trunk counter-leans **back, away from the opponent**: measured 29° back
  and 30° to the side in the approved version (keys `lean(-26, 24)`); head
  over the bent standing leg (knee 78°). Leg and trunk make one long diagonal.
- Kicking-side arm reaches forward and down along the kick at chest height,
  near-straight elbow. Guard hand at the face, riding with the head.
- Return: the leg comes straight down the way it came (no hanging chamber),
  hips unwind, the lean comes back in two steps.

What went wrong on the way: chest not turning with the hips (D-108); lean
mostly sideways, invisible in play (D-109); arm thrown up and back as a
counterweight (D-110 → "the hands swing totally wrong"); guard hand fixed in
space and left behind by the lean (fix: place it relative to the head).

### Mid and high roundhouse

Same family, the knee chambers higher and points at the target before the
shin opens; standing foot pivots further (toward 135–180° for a high one);
lean back grows with height (45° or more for head height); the kicking hip
is clearly above the standing hip. Contact with shin or instep. Re-chamber on
the way back for a snap version; swing through for a Muay Thai one.

### Front kick (Kairo: Front Kick, `DOWN_HEAVY` / `ATTACK_BODY_HOOK_01`)

Status: reworked D-096/D-097 after "extend his leg more" and "foot like a
ballerina"; no complaint since. **Known gap:** measured on the game model the
kicking knee is still bent 34° at contact (the log's 0.96 extension *is* a
~32° bend), with only 20° of lean and little hip drive. If she calls this
kick stiff or not extended, start there.

- Dip onto the standing foot; knee driven straight up toward the chest
  (chamber), shin hanging.
- Hips stay square and **push forward** into the kick at the end; the
  extension comes from the knee opening plus the hip thrust.
- Contact with the **ball of the foot, toes pulled back** (snap kick) or the
  heel/flat sole (push kick). Never a pointed foot. (`point` −0.7 … −0.95.)
- Leg straight or within a few degrees at contact for a snap kick (aim for a
  knee under ~10°; note that "0.95–0.97 of its length" is still a 28–36°
  bend), ankle inside the far part of the hitbox.
- Trunk leans back a little (about 19°) as a counterweight; both hands stay
  up; standing heel may lift.
- Re-chamber (knee stays high as the shin folds), then set the foot down
  through a low key. Spread the snap over two frames with an in-between key.

### Side kick

No grounded side kick exists in the game yet; the Flying Side Kick is the
nearest keyed example (its numbers are below).

- Chamber: knee lifted across the body, heel pulled in toward the standing
  thigh, the body already turning side-on. Keep the fold above ~0.33 of the
  leg's length (keying.md "Folding a leg").
- Standing foot pivots until its heel points at the target (~180° on a real
  body). The approved Low Kick keys +60° on `*_toe`; go further for a side
  kick, in steps, and watch the pose checker's "knee points N away from its
  foot": the standing knee has to follow the toes.
- Hips side-on, kicking hip toward the target and rolled slightly over;
  the leg drives out in a straight line from the chamber (a thrust, not a
  swing): hip, knee, heel on one line.
- Contact with the heel or the blade of the foot, toes pulled back and
  turned down, foot parallel to the floor.
- Trunk leans away along the line of the leg: at full extension head, hip
  and heel are close to one straight line. Eyes over the shoulder.
- Same-side arm along the kicking leg; other fist at the chest or chin.
- Re-chamber along the same line, then down.

### Axe kick (Kairo: Rift Break, `FORWARD_SPECIAL` / `SPECIAL_RIFT_BREAK`)

Status: keyed to the owner's **specification** (D-129,
`docs/images/references/kairo_rift_break_axe_kick_spec.md`); **not yet
confirmed**. Twelve entries of history; what she has settled on the way: the
leg nearer the camera; a step in, no hop; and, in the specification, the knee
rising first with the leg extending progressively (her earlier text asked for
a straight-leg lift; the specification replaces it and names "straight-leg
lifting" as wrong).

Her six phases, with the frames they have (51 in all, contact 22):

- **Preparation** (1–9): weight onto the supporting leg with one step in; the
  kicking foot pushes off and leaves the floor.
- **Knee up** (10–12): the knee comes straight forward and up, bent about
  110°, not out to the side.
- **Lift and extension** (13–18): the thigh keeps rising toward vertical while
  the knee opens steadily. Never a rigid leg, never bent all the way.
- **Peak** (18–20): near vertical (80°), foot above the head, knee about 10°
  (mostly extended, not locked). It does not freeze: the heel is carried
  forward over the target, the body keeps adjusting.
- **Strike** (20–22): down in one fore-aft plane, the knee flexing a little as
  it starts (25°) and extending into the hit (8°), speeding up; heel first,
  toes pulled back.
- **Impact** (22–26): the heel slows through the active frames into a short
  impact pose and rebounds a few degrees; chest and fists come down with it
  and recoil. No long pause.
- **Recovery** (27–51): the leg comes down with the knee bending, is set down
  in the stance, the supporting foot steps up, he settles.

Also from her text and from D-128: he stands tall on a nearly straight
supporting leg with the foot **flat** on the floor; the lean back at the peak
is small (10°); the arms stay in a compact guard but move (they sink, pull
down with the heel and recoil); the supporting foot does not slide; nothing
sideways, no spin.

"Predominantly vertical" and "foot above the target": a near-vertical leg puts
the foot over his own head, not over a target 0.8 m away. The peak therefore
tips forward (the heel carried to about 0.25 m ahead while still at 1.6 m)
before the strike, so the strike itself falls more than it travels (57° below
level; 75° through the hit).

The game hits at 43 % of the clip; her phases put the impact at 70–75 %. The
phases keep their order inside the time before the hit; matching 70 % would
be a slower move (a balance change).

Keyed as a direction plus an extension with the hinge set: keying.md "A leg as
direction plus extension".

### Flying side kick (Kairo: `JUMP_ATTACK`)

Status: keyed to the owner's Ryu art (D-118/D-119); **not yet confirmed**.
Her corrections: rear leg deformed when over-tucked; kicking leg fully
extended; upper body must not stay straight; wrong leg (settled: the rear,
right leg, the one nearer the camera).

- In the air the knee chambers up to the chest.
- Hips turn the kicking side to the target (measured 86° from the stance at
  contact; chest 39°, so 46° of twist: at the limit).
- Kicking leg shoots out **straight and nearly level, a little below hip
  height**, heel/blade first, toes pulled back.
- The other leg folds tight under the hips, knee forward (0.38 of its length
  at contact; 0.28 pinched the mesh in D-099, and the kicking leg's own
  chamber touches 0.28 on frame 3 today).
- Trunk **leans back and away and curls**, chin dropped into the kick. Not
  upright. (Keyed 20–24° back and 12–14° to the side; measured on the game
  model at contact it is 13° back and 11° to the side, less than keyed. If
  she still finds the body too straight, this is where to look.)
- Kicking-side arm straight down along the kicking leg; other fist at the
  chest, elbow up.
- Through the hold the kick keeps driving a few centimetres, then rides down
  with the jump arc; the leg re-chambers over four frames (one frame moved
  the foot 0.46 m) and both feet reach for the floor.

### Sweep (Kairo: Leg Sweep, `DOWN_KICK`)

Low and long: the standing leg bends deep (he drops), the sweeping leg goes
out nearly straight and close to the floor on a wide horizontal arc, foot
hooked to catch the ankle; the trunk leans away over the standing leg or a
hand goes toward the floor; hips turn through as for a roundhouse. Getting up
takes time: the recovery is long on purpose.

### Knee (Kairo: Knee Throw, `L+K`)

Clinch first: both hands take the opponent's head or shoulders and pull down
as the hips drive **forward and up**; the knee rises to chest height with the
foot pointed down behind it; the trunk leans back as the hips go through.
The victim is drawn into the clinch and tipped forward (D-105).

### Spinning and back kicks (not in the game yet)

The head turns first and finds the target over the shoulder before the leg
arrives; the back shows to the opponent mid-turn; the standing foot pivots
through the whole turn. Needs a clear wind-up and has long recovery.

---

## Punches

### Jab (Kairo: lead straight, `LIGHT`)

Almost no wind-up. Lead shoulder and hip go in with the fist; a 5–6 cm step
of the lead foot; arm all but locked at contact (0.99 today; 0.85 read as a
"bent-arm push"); rear hand home. The fist travels over three frames, not
two. Kairo's guard hand is already out, so it snaps back a little first.

### Cross / reverse punch (Kairo: `HEAVY`, string cross)

Rear foot pivots, heel up; hips turn first, chest a frame or two later, fist
last on a slight arc. Wind-up is one continuous coil. Lead hand pulls back to
the ribs as the rear goes out (hikite). Chin drops into the blow. Held out
for several frames with a moving hold; recovery swings a little past the
stance and settles with a small dip.

### Hook

Elbow bent near 90° and level with the fist; the arm stays bent through the
swing (0.7 of its length, not locked); power from the hip and foot pivot on
the punching side; short range.

### Uppercut (Kairo: Rising Uppercut, `DOWN_LIGHT`)

Dip first (knees, not the waist), fist drops to hip height, then legs drive
up; elbow stays bent (about 0.6), fist rises along the centre line; the body
rises with it, heels may leave the floor on an anti-air.

### Palm thrust / lunge (Kairo: Origin Palm, `SPECIAL`)

Long load onto the rear leg with the palm chambered at the ribs, guard hand
up; then a lunge off the rear foot with the hips, the palm arriving last.
Keep the chest's turn moderate at contact (a 77° neck twist came from
over-turning it).

---

## Movement

- **Stance** (see `docs/POSE_BLUEPRINTS.md`): alive, never still. Breath
  moves the chest a few degrees, hands float and follow late, a slow sink of
  a few centimetres. Feet do not slide (0.000 m). Arms clear of the trunk
  (forearm clearance measured; the rear fist once sank into the armour).
- **Walk**: a fighter's shuffle, the stance kept open; planted feet move back
  under the body exactly as fast as the game moves him (`foot_slide.gd`: 0.5 cm
  per planted frame today, against 3.6 when it was "sliding on ice"); legs not frantic (a foot planted ~55 % of the
  loop so each swing takes ~11 frames).
- **Jump**: a real crouch before take-off, arms drive up, knees tucked at the
  top, legs reach for the floor, a deep landing dip.
- **Crouch**: sits on the rear heel, back fairly upright, guard pulled in;
  not folded flat ("squashed").

## Reactions

A hit moves the struck part first and the rest follows: head snaps, then
chest, then hips; the reaction's size matches the hit height and strength.
They are quick to start (frame 1) and slow to settle.
