# Animation research: why the fighters do not read as fighters, and what to do

Written 2026-11-22 after the owner's test ("they look unnatural and they
don't look like fighters ... do research on how to properly do this").
Sources are listed at the end; rules marked (S) come from a summary of a
studio blog and are less reliable.

## What professional fighting-game animation does

1. **Anticipation, even one frame.** "Having even a frame of anticipation
   will make your move much better in terms of readability." Heavier attacks
   hold the wind-up longer; too long feels unresponsive, so slow wind-ups
   belong to risky moves.
2. **Speed is the gap between two poses**, not the frame count: arm
   recoiled, then outstretched, reads faster over 2 frames than over 5.
3. **Hold the contact pose** "a little longer than in reality" so the
   player sees it.
4. **Stagger the body.** Parts must not start or arrive together: the head
   and torso lead, the bent arm drags, the arm snaps just before impact, and
   the head settles after the body stops.
5. **Fast in, slow out.** Weight comes from the follow-through and the
   settle, not from the speed of the swing. Hold strong poses in recovery.
6. **Hips are the centre of mass** and move in arcs in walks, strikes and
   idles (S). Nothing ramps to full speed instantly: lean in and push off.
7. **Exaggerate, consistently.** "Real life never looks real enough": pose
   and arc further than the reference, at one level across the whole game.
8. **Silhouette first.** At 60 frames a second each frame is on screen for
   16 ms; a move must read as a black shape.
9. **Overshoot and smears** fill the gap when there are too few frames: one
   frame past the pose, then back.

## Where this game falls short of that (honest)

- **The motion itself.** Most strikes are generic motion capture of one
  boxer and one martial artist (CMU database), recorded for research, not
  performed as fighting-game moves, retargeted by script onto six different
  bodies. The rest is keyed by script: a hand moved between positions in a
  straight line at even speed. None of it was performed or animated as these
  characters.
- **Timing.** Captured strikes were played at even speed through the
  wind-up and straight through the contact pose with no hold; keyed moves
  interpolate linearly. That is rules 2-5 broken everywhere.
- **No exaggeration, no overshoot, no secondary motion** (hair, cloth,
  belts are skinned to the body and do not move on their own).
- **No animator's eye on motion.** Everything is checked on still frames by
  a model that cannot watch the result move. Numbers catch broken joints,
  not dull or wrong-feeling motion.

## What can be done, in order of effect

1. **Better source motion (largest effect).** Fight clips performed for
   games exist and may be used commercially:
   - Rokoko "13 free fight animations": FBX, 30 fps, Mixamo skeleton;
     "from passion project to commercial use". Needs an e-mail sign-up.
   - KinemIQ free library: 460 clips incl. 68 attacks (punches, kicks,
     combos), 64 idles and stances, blocks, hit reactions; FBX / GLB / BVH;
     175 CC0, 285 CC BY (credit required). Exported through its web studio.
   - Mixamo (Adobe): large fighting set, free for games with an Adobe ID;
     raw files may not be redistributed, so they cannot sit in this repo.
   - Not usable: SFU database (research only).
   These need the owner to download them (accounts and sign-ups cannot be
   created from the build machine). The retarget, the fit to each fighter's
   body and the checker built in D-075 to D-082 work on any such clip.
2. **Timing and exaggeration of what exists (done for captured strikes in
   D-083):** eased startup that whips into the blow, a held contact pose,
   an overshoot, fast-out slow-settle recovery, a small anticipation coil
   on slower moves.
3. **The same for keyed moves** (most of Vexa, Ryuen, Nox, Seraphina's
   specials): their straight-line, even-speed hand paths need arcs, eased
   timing, torso-leads-arm staggering and held contact. Not done yet.
4. **Secondary motion** (Seraphina's ponytail, sashes, Nox's hood): needs
   extra bones or in-engine spring bones. Not done.
5. **A person watching it move.** The owner's phone tests are the only
   check of motion; short notes like "the jab looks soft" are enough to act on.

## Sources

- https://80.lv/articles/tips-on-making-fluid-and-powerful-animations (Mariel Cartwright, Skullgirls, GDC 2014)
- https://www.gamedeveloper.com/production/the-12-principles-of-animation-in-video-games (Jonathan Cooper)
- https://80.lv/articles/animating-guilty-gear-inspired-fighting-game-combo-in-maya/ (Minh Nguyen)
- https://pixune.com/blog/role-of-exaggerated-animation-in-fighting-games/ (studio blog; summary only)
- https://www.rokoko.com/resources/rokoko-mocap-13-free-fight-animations
- https://kinemiq.app/free-game-animations/
- https://community.adobe.com/t5/mixamo-discussions/mixamo-faq-licensing-royalties-ownership-eula-and-tos/td-p/13234775
- https://mocap.cs.sfu.ca/
