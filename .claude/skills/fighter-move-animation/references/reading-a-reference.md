# Reading a reference picture

The owner sends a picture (game art, a screenshot, a martial-arts photo
sequence) and a few words. The picture is the specification. Her words tell
you which part of it she cares about most. This file is how to get from the
picture to a pose brief without the misreadings that cost rounds before.

## 0. Can you actually see it?

- Open the image itself with Read. A `share.google` link, a search-result
  link or a page that needs a login cannot be opened here: ask for the image
  (a screenshot is fine). Do not work from the link's title.
- If it is a sequence (several figures, or numbered steps), each figure is a
  key pose. Note the order and which one is the contact.
- If the picture is small or dark, crop and enlarge it (Pillow) before
  reading limbs. Guessing a leg from a thumbnail is how "wrong leg" happens.

## 1. Set up the two frames of reference

**The game view.** The player's fighter (P1) stands on the left and faces
right. The camera looks at the fight from the side. Review videos and
`clip_frames.gd` show exactly this view. Kairo leads with his left side, so in
this view:

| | Kairo, as P1 facing right |
|---|---|
| Leg nearer the camera | right = **rear** leg (measured: 0.11 m nearer, D-122) |
| Leg farther from the camera | left = **lead** leg |
| Arm nearer the camera | right = rear arm |
| Chest | faces the camera when the shoulders are turned side-on toward it |

Other fighters: check which side leads (`STYLES[...]`, the blueprint in
`docs/POSE_BLUEPRINTS.md`) and, if in doubt, measure in the training scene as
D-122 did rather than reason it out.

**The picture's view.** Work out, in the picture: which way the fighter
faces (where is the opponent?), and where the camera is (front, back, side,
three-quarter). Game art is often drawn from behind or three-quarter, and
often mirrored relative to our view.

**Map one onto the other in screen terms.** Imagine turning the pictured
fighter until the opponent is on the right and the camera is at the side.
Then describe every limb as *nearer the camera / farther* and *toward the
opponent / away*. Never carry "left" and "right" across from the picture:
after a mirror or a turn they swap, and anatomical sides are not what the
owner means anyway. When she says "the other leg", she is pointing at the
screen.

If the picture is a back view or a mirrored view, there are two honest
readings of "which leg": the anatomical one (his rear leg) and the screen one
(the leg nearer the viewer). They can disagree. When they do, ask her once,
offering the two choices in screen words ("the leg nearer the camera, or the
one on the far side?"). That exact question settled Rift Break after two
wrong builds.

## 2. Read the contact pose, in this order

Go from the ground up. Write each line of the brief as you go; do not trust
an overall impression ("it's a side kick") to fill in parts you did not look
at. Each item below was got wrong at least once.

1. **Standing foot.** Flat or on the ball? Turned out how far (toes toward
   the opponent, across, or pointing away)? The pivot of this foot is what
   lets the hips turn.
2. **Standing knee.** Locked, soft, or deeply bent? (A straight standing leg
   under an axe kick read as "a pole"; a low roundhouse sits on a bent one.)
3. **Hips.** Square to the opponent, side-on, or turned over so the back
   shows? Estimate in rough quarters: 0°, 45°, 90°, more. Which hip is toward
   the opponent?
4. **Striking leg or arm.** Which one, in screen terms. Height of the foot
   or fist relative to his own body (knee, hip, chest, head, above the head).
   Straight or bent, and if straight, *fully* straight? Direction: level,
   rising, dropping.
5. **Trunk.** Upright, leaning back (away from the opponent), forward, or to
   the side? Roughly how far (10°, 25°, 40°)? Straight spine or curled? Does
   the chest face the camera, the opponent, or the floor?
   This was the most repeated miss: "his upper body stays straight, that's
   wrong", "he needs to lean with that kick".
6. **Arm on the striking side.** Where is the hand: along the kicking leg,
   at the hip, thrown back, up? Elbow straight or bent?
7. **Other arm.** Guard at the face, fist at the chest, out for balance?
8. **Head.** Looking at the opponent? Chin tucked? Over the standing foot or
   leaning with the trunk?
9. **Striking surface.** Kicks: heel, ball of the foot, instep, shin, the
   blade edge; toes pulled back or pointed. Punches: fist, palm, back fist;
   palm facing down, in or up.
10. **The line.** Squint: what single line or shape does the silhouette
    make? (Low roundhouse: one long diagonal from the head through the hips to
    the kicking foot. Flying side kick: a level leg with a curled body behind
    it. Axe kick: a vertical leg beside an upright body.)

## 3. Pick the must-reads

From the ten lines choose the two or three that make this picture this move
and would be noticed at a glance if they were missing. Those are the
must-reads. They get the boldest keys and they are what you check first at
game size. Everything else serves them.

Use her words to choose. "Like this" on a low roundhouse meant hips over, the
lean, and the arm. "With foot down" on the axe-kick sequence meant the heel
has to come down through the target, not stop at the top.

## 4. The moments around the contact

A single picture gives only the contact. For the rest:

- If she sent a sequence, each figure is a key: use them all, in order.
- Otherwise take the wind-up, chamber and return from
  `technique-form.md`, and say in the brief that those parts are from the
  technique, not from her picture.

## 4b. When the picture is of a different situation

- **A different move than ours** (an airborne kick as the model for a
  standing one, a high kick for a mid one): take from the picture what
  carries over (which limb, the leg's line and height, the foot shape, the
  trunk's lean, the arms) and get the rest (standing leg, pivot, wind-up)
  from `technique-form.md`. Mark those rows "(inferred)". Check that the
  move's hitbox is where the pictured strike lands; if it is not, this is
  also a data change (SKILL.md "When the move's data has to change").
- **A picture of our own game** (a screenshot of another of his moves, or of
  another fighter): find the clip and measure it with `body_angles.gd`
  instead of estimating angles by eye. The brief's "reference shows" column
  can then be numbers.
- **Several pictures that disagree:** her words say which one rules; if they
  do not, the latest one does.

## 5. What a picture cannot tell you

Speed, weight and timing. If she says "too fast" or "unnatural" about a move
whose pose now matches, it is the motion: phases without enough frames, parts
that move together, a body that slides. See SKILL.md "What makes motion read
as a fighter" and, for timing, "When the move's data has to change".

## 6. Proportions and the model's limits

- Art exaggerates leg length and flexibility. Match the angles and the line,
  not the absolute reach; keep the foot inside the move's hitbox.
- The skeleton has no toe bones: toes cannot curl back; the whole foot angles
  (`point` < 0).
- Extreme folds pinch the mesh (a leg folded to 0.28 of its length crushed
  the knee, D-099). Check with `stretch_check.py`, and if the picture needs a
  fold the mesh cannot take, key as close as holds and say so.

## 6b. Comparing afterwards

`compare_reference.py` puts the picture beside the contact frame. It does
not scale or align them, and the picture's camera is rarely ours: compare
angles and the line, part by part down the brief, not outlines.

## 7. Write it down

Fill in `assets/pose-brief-template.md`. Keep it to what you can see. Where
you are inferring, mark it "(inferred)". A brief with honest gaps is better
than a confident wrong one, because the gap is where you look hardest in
step 6 of the loop, or ask.
