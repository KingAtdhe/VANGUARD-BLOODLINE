# Pose blueprints

One fighter at a time (owner's pose quality brief, 2026-11-22, D-075). A
fighter is listed here only after its stance was defined, fitted to its own
skeleton, measured, rendered from five sides and looked at, and all of its
animations were checked at their first, middle and last frame.

Numbers are **measured on the real rig** by `tools/blender/pose_check.py`
(written to `pose_report.json` by every model build), not the values typed
into `STYLES`. Metres and degrees; forward = toward the opponent; the fighter
faces the opponent with the left side leading unless noted.

How to work on the next fighter:

1. Give its `STYLES[...]["pose"]` entry `fit=True`, a `pelvis_h`, `trunk`,
   `pelvis`, `shoulders`, foot marks, hand positions and palms
   (`tools/blender/mocap_actions.py`, see `pose_stance` and `fit_stance`).
2. `STANCE_ONLY=1 python3 tools/blender/import_rigged.py ...` builds the idle
   alone in about ten seconds and prints the measured blueprint and faults.
3. Look at it: `tools/godot/pose_views.gd -- <id> out.png IDLE_A 1 480 <built.glb>`.
4. Full build, read the faults listed for every action, render the moves
   (`tools/godot/move_shot.gd`, `anim_shot.gd`) and look at them.

## Kairo — done (D-075)

Identity: Origin bloodline brawler; boxer. Reference approved by the owner:
Steve Fox (posed from knowledge of the character, not from footage).
Upright, light on a short base, constant small bob, both fists at the chin.

| | Blueprint (measured) |
|---|---|
| Lead (left) foot | 0.09 left of centre, 0.20 forward; turned 10° inward; flat |
| Rear (right) foot | 0.11 right of centre, 0.21 back; turned 45° out; heel 3 cm up, on the ball of the foot |
| Distance between feet | 0.40 along the fight line, 0.21 across it (shoulders are 0.38 wide) |
| Knee flexion | lead 30°, rear 48°; each knee bends over its own toes (0° and 2° off) |
| Pelvis | 0.94 m high (96.5% of standing); turned 32° side-on |
| Spine | leans 10° forward, 0° sideways |
| Chest | turned 42° side-on, lead shoulder in front; 10° of twist against the pelvis |
| Lead arm | elbow bent 114°, elbow below and outside the fist; wrist 0.40 forward of the stance centre at 1.35 m (chin height), 0.11 left |
| Rear arm | elbow bent 119°, tucked to the ribs; wrist at the right cheek, 1.39 m high |
| Hands | fists; palms face the centre line (thumbs up); wrists straight (0°) |
| Guard | lead fist out in front of the chin, rear fist on the cheek |
| Head | looks at the opponent (11° of the chest's turn), chin 6° down, no sideways tilt |
| Neck | 31° of turn against the chest |
| Weight | 58% on the lead foot |
| Centre of gravity | 0.03 forward of the stance centre, 9 cm inside the edge of the feet |
| Readiness | both knees bent, rear heel up: can step either way or punch without shifting first |
| Idle | two knee dips of 2 cm per second over planted feet; feet slide 0.000 m |

Checks: stance faults none. 75 action frames checked, 5 flagged, all looked
at and left on purpose or recorded in KNOWN_ISSUES (KI-050): the forward
dash has one foot in the air mid-step; Slip Counter leans the trunk 32° and
tilts the head (that is the slip) and starts with one foot unweighted; the
ultimate lunges past its feet; the defeat pose bends a wrist 67°.

## Drakon, Seraphina, Nox, Vexa, Ryuen — not done

Still on the D-074 stances, posed on the captured performer's proportions.
Faults the checker lists for them today are in KNOWN_ISSUES (KI-050).
