# Kairo — Rift Break (axe kick): the owner's animation specification (2026-11-26)

This is the current target for the move (D-129). It replaces the shorter
written sequence of 2026-11-25 (`kairo_rift_break_axe_kick.md`, D-126), which
asked for a straight-leg lift; this one asks for the knee to rise first and
the leg to extend progressively. The owner's text, unedited, with the working
rule she sent just before it.

## Working rule (sent first)

> Before animating, inspect the rig, identify the correct hip, knee, ankle, foot, pelvis, spine and armature control bones, and verify their rotation axes. Do not guess bone orientations. Test the leg movement with a small number of poses before building the full animation. Preview the animation from the side view to verify the vertical trajectory of the kicking leg. If the leg trajectory is incorrect, correct the keyframes before proceeding. Do not report the animation as complete until the animation has actually been previewed and validated.

## ANIMATION SPECIFICATION — AXE KICK (HIGH-QUALITY 3D FIGHTING GAME)

### OBJECTIVE

Create a physically believable, fluid, combat-ready Axe Kick (Downward Vertical Heel Strike) animation for the existing rigged fighter. This is a martial arts axe kick, NOT a roundhouse kick, front kick, side kick, or straight-leg lifting animation.

The animation must look like a trained martial artist deliberately lifting the kicking leg high above the opponent's head and forcefully bringing it straight down, striking with the heel or sole of the foot.

The animation must be suitable for a polished 3D fighting game.

### 1. ANIMATION SEQUENCE

PHASE 1 — FIGHTING STANCE / PREPARATION (0–15%)

- Start in the fighter's existing natural fighting stance.
- Maintain a balanced, alert posture.
- Slightly shift the body weight onto the supporting leg.
- The supporting foot must firmly contact the ground.
- Slightly rotate the torso and hips to prepare for the kick.
- Raise the kicking knee forward and upward in a controlled motion.
- The kicking leg begins bending at the knee during the initial lift.
- Maintain appropriate guard positioning with both arms.
- The movement must be fluid and intentional, not robotic.

PHASE 2 — LEG LIFT AND EXTENSION (15–40%)

- Lift the kicking leg progressively upward in front of the fighter.
- The thigh travels upward toward the vertical position.
- Extend the knee progressively as the leg rises.
- The kicking leg eventually reaches a very high position above the fighter's head.
- The foot must travel upward before descending. This upward motion is essential to the axe kick.
- The leg should reach a near-vertical position, with the heel positioned above the target.
- The hip must flex naturally to support the high leg position.
- Do not rotate the leg sideways into a roundhouse trajectory.
- Do not swing the leg horizontally.

PHASE 3 — HIGH POSITION / BRIEF CONTROL (40–50%)

- The kicking leg reaches its peak height.
- The leg is nearly vertical, positioned above and slightly in front of the fighter.
- The knee is mostly extended but not locked unnaturally.
- The foot is positioned above the intended striking target.
- The fighter maintains balance through the supporting leg, core, hip and upper-body adjustments.
- Briefly control the leg at its peak before initiating the downward strike.
- Do not freeze the entire character. Subtle body movement and balance adjustments must continue.

PHASE 4 — AXE STRIKE / DOWNWARD MOTION (50–70%)

- Forcefully bring the raised leg straight down toward the target.
- The kicking leg travels in a predominantly vertical downward trajectory.
- The heel or sole is the primary striking surface.
- The knee may flex slightly during the descent and extend appropriately toward the strike.
- Generate the strike through hip movement and controlled leg acceleration.
- The torso must naturally adjust to maintain balance.
- The supporting leg must remain grounded and stable.
- The arms must react naturally, maintaining defensive positioning and balance.
- The strike must feel explosive, with noticeable acceleration during the downward phase.
- The foot must not swing sideways or horizontally.
- The striking foot must not rotate into a roundhouse kick.
- The strike must not be performed as a front kick.
- The strike must not be performed as a knee attack.

PHASE 5 — IMPACT (70–75%)

- Create a clear, decisive downward striking moment.
- The heel or sole is the contact point.
- The leg should reach the appropriate strike position without unnatural hyperextension.
- Apply a brief impact pose with controlled body recoil.
- The torso and shoulders react subtly to the impact.
- The arms may adjust slightly to counterbalance the strike.
- Do not create exaggerated cartoon deformation.
- Do not make the fighter fall over.
- Do not allow the supporting foot to slide.
- Avoid excessive impact pauses or unnatural snapping.

PHASE 6 — RECOVERY (75–100%)

- Retract the kicking leg naturally following the strike.
- Bend the knee slightly as the leg comes down.
- Bring the kicking leg back toward the ground.
- Return the foot to its original fighting stance position or an appropriate nearby combat stance.
- Restore the fighter's center of gravity.
- Reposition the torso, hips, arms and shoulders into a balanced fighting posture.
- Finish in a stable, combat-ready stance.
- The final pose must not be identical to an artificial frozen T-pose.
- The animation must end with the fighter ready to perform the next action.

### 2. BIOMECHANICAL REQUIREMENTS

- Use anatomically plausible joint rotation.
- Preserve the original character's proportions.
- Do not distort the mesh.
- Do not stretch the limbs.
- Do not twist the knee unnaturally.
- Do not bend the knee in the wrong direction.
- Avoid excessive hip rotation.
- Avoid excessive lumbar or spinal bending.
- Maintain realistic weight distribution.
- Use the supporting leg to maintain balance.
- Prevent the supporting foot from sliding across the ground.
- Prevent foot penetration into the floor.
- Maintain natural shoulder, elbow, wrist and hand movement.
- Ensure the kicking foot follows a coherent trajectory.
- Ensure the leg is not detached visually from its hip or knee.
- Maintain believable center-of-mass movement.
- Avoid sudden discontinuous rotations.
- Avoid unnatural joint flipping or axis inversions.

### 3. ANIMATION QUALITY

- High-quality professional martial arts animation.
- Fluid transitions between all phases.
- Controlled anticipation.
- Strong upward leg lift.
- Clearly defined near-vertical peak.
- Explosive downward acceleration.
- Convincing impact.
- Smooth recovery.
- Natural secondary movement in the arms, torso and head.
- Subtle balance corrections.
- No robotic movement.
- No motionless upper body.
- No stiff limbs.
- No sudden teleportation between poses.
- No abrupt animation cuts.
- No exaggerated motion unless needed for fighting-game readability.

### 4. TECHNICAL REQUIREMENTS

- Animate the existing character rig only.
- Do not create a new character.
- Do not change the character mesh.
- Do not modify the character's proportions.
- Do not replace the skeleton.
- Do not add unnecessary bones.
- Do not alter the existing rig hierarchy.
- Do not destroy existing animations.
- Use the existing bone names and bone structure.
- Ensure the animation is compatible with the current rig.
- Ensure the animation can be exported and used in the game.
- Ensure the animation starts and ends in usable combat poses.
- Keep the animation root motion consistent with the existing animation system.
- If root motion is disabled, keep the character's overall position stable and animate the kick without unwanted translation.
- Do not introduce unintended rotations of the character root.
- Ensure the animation can be played from the existing fighting stance.

### 5. NEGATIVE PROMPT — STRICTLY AVOID

DO NOT create any of the following:

- Roundhouse kick.
- Side kick.
- Front kick.
- Straight forward kick.
- Knee strike.
- Jumping kick.
- Spinning kick.
- Crescent kick.
- Axe kick with a sideways swinging trajectory.
- Horizontal leg swing.
- Low kick.
- Kick without a high vertical leg lift.
- Kick without a downward striking motion.
- Kick where the foot never rises above the head.
- Kick where the leg is lifted and immediately lowered without a striking motion.
- Kick where the leg remains bent throughout the entire motion.
- Kick where the leg becomes unnaturally rigid.
- Kick with a locked, hyperextended knee.
- Kick with reversed knee bending.
- Kick with broken hip rotation.
- Kick with twisted ankle.
- Kick with distorted foot geometry.
- Kick with warped arms.
- Kick with deformed torso.
- Kick with excessive leaning backward.
- Kick with excessive leaning sideways.
- Kick with the supporting foot sliding.
- Kick with the supporting leg bending unnaturally.
- Kick with the fighter losing balance.
- Kick with the fighter falling.
- Kick with the fighter rotating uncontrollably.
- Kick with the character moving across the floor unintentionally.
- Kick with foot clipping through the ground.
- Kick with leg clipping through the torso.
- Kick with mesh deformation.
- Kick with jittering.
- Kick with sudden pose changes.
- Kick with teleportation.
- Kick with animation snapping.
- Kick with robotic movement.
- Kick with stiff upper body.
- Kick with static arms.
- Kick with unrealistic timing.
- Kick with excessive motion blur that hides the movement.
- Kick with an exaggerated cartoon style.
- Kick with an unnatural recovery.
- Kick ending in a broken or unstable stance.

### 6. FINAL VALIDATION

Before finalizing the animation, inspect the complete animation from beginning to end.

Verify the following:

1. The kicking leg lifts high above the fighter's head.
2. The leg reaches a near-vertical position.
3. The foot is positioned above the intended target before striking.
4. The leg descends predominantly vertically.
5. The heel or sole performs the downward strike.
6. The kick is clearly recognizable as an axe kick.
7. The supporting foot remains stable.
8. The fighter maintains realistic balance.
9. The joints do not deform unnaturally.
10. The mesh does not distort.
11. The animation has no sudden snapping or jittering.
12. The fighter smoothly returns to a combat-ready stance.
13. The animation is compatible with the existing rig and game animation system.

If any of these conditions are not satisfied, correct the animation before declaring it complete.

Do not substitute a different kick. The required animation is specifically a high, vertical axe kick with a downward heel/sole strike.

## Decisions carried over (not in the specification)

- The kicking leg is the one nearer the camera: his right, rear leg (D-122).
- One step in with the supporting foot before the lift, 0.7 m of travel
  (D-127, the owner's choice). The specification's "moving across the floor
  unintentionally" does not cover this intended step.
- The game's timing (22 frames to the hit, 4 active, 26 to recover) puts the
  hit at 43 % of the clip, not at 70–75 %. The phases keep their order and
  their shares of the time before the hit; the recovery is longer than the
  specification's 25 %. Matching 70 % would mean a slower move: a balance
  change, offered to the owner.
