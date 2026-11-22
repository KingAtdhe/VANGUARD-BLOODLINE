# Changelog

## [Unreleased]
### Changed — Kairo's attacks, third pass (every frame checked)
- The jab is a real straight punch now (arm nearly locked out, moving from the second frame); strikes build over several frames instead of arriving in one; the cross winds up in one motion; hooks and the uppercut keep a bent elbow; the low kick's leg comes straight back down; recoveries are slower. Hit boxes and frame data unchanged.
### Changed — Kairo's attacks, second pass
- Wind-ups are visible now, recoveries use their full time instead of ending early and standing still, poses are pushed further than real boxing, the body swings slightly past the stance and settles, and his chin drops into each blow. The Slip Counter is a clear duck off the line.
### Changed — Kairo's attacks rebuilt from scratch (trial)
- All nine of Kairo's attacks are new, built by hand on boxing fundamentals instead of taken from a research recording: wind-up, hips then chest then fist, the hit held, the other hand guarding, the rear foot pivoting. His ultimate is now a four-punch combination. Timing and hitboxes for gameplay are unchanged.
### Changed — strikes timed like strikes
- Punches and kicks taken from motion capture (Kairo, Vexa, Seraphina, Nox) now coil briefly, whip into the blow, hold the hit for a moment, and settle back slowly, instead of playing at one even speed. Timing data for gameplay is unchanged.
- Added `docs/ANIMATION_RESEARCH.md`: how fighting-game animation is done professionally, where this game falls short, and what would close the gap.
### Fixed — from the owner's phone test
- The once-a-second "cut" in every fighter's stance animation is gone (the breathing now loops), and so is the cut every half second while walking.
- Kairo, Vexa, Seraphina and Nox walk with real steps: heel up, foot swings and lands heel first, hips and shoulders move with the step.
- Their feet stand on the floor: a raised heel no longer pushes the boot through the floor and lifts the other foot.
### Fixed — sway-backs
- Nox, Seraphina, Kairo and Vexa stand with a straight back. Nox's pelvis was tipped forward under a chest leaning back; Seraphina's back was arched and Kairo's hunched.
### Fixed — Nox stands upright; arms tested against each fighter's real body
- Nox stands straight (he was crouched low and leaning forward), with his lead hand out and his rear hand up in front of his shoulder; neither arm touches his body.
- The arm-through-body check now uses each fighter's own chest width and depth measured from the model, instead of one fixed size for everyone.
### Fixed — Nox's poses
- Nox crouches low and coiled, side-on, with his lead hand out and his rear hand cocked at the ribs; both knees bend over their own feet. His moves start and end on the same feet, and his low dash and low block no longer leave his feet behind.
### Fixed — Seraphina's arm through her body
- Seraphina's rear forearm no longer passes through her torso in the stance; it rests across the front of her waist. Arms are now checked against the body on every frame of every animation for Kairo, Vexa and Seraphina.
### Fixed — Seraphina's poses; hands and transitions for everyone
- Seraphina stands side-on and tall with her hands low, bouncing on both feet; her rear knee no longer points away from its foot. Her kicks start and end on the same feet and lean away from the kicking leg.
- Transitions between poses no longer fold a wrist on the way (most visible in the defeat animation). All fighters.
- Kairo, Vexa, Seraphina: hands turn naturally with the arm (palm in when bent, palm down in a straight punch) and are kept out of their own body in hit reactions.
### Fixed — Vexa's poses; walking and blocking for Kairo and Vexa
- Vexa stands in a balanced Muay Thai stance (she was leaning 16 cm behind her own feet): short square base, both gloves high with her face visible, lead foot light and tapping. Her strikes start and end on the same feet.
- Kairo and Vexa walk with a real shuffle step instead of feet that held and snapped back; their dashes and low blocks bend the legs over the stance's own foot positions; the high block covers the face from the fighter's own head height.
### Fixed — poses: root causes, and Kairo redone
- Kairo's model was built turned 35 degrees and the animation pipeline did not know: his hips, chest and head were off in every pose. Fixed at the source.
- Kairo's stance is solved on his own skeleton: both feet flat on the floor where the stance says, fists at his chin with straight wrists, head up and looking at the opponent. His punches now start and end on the same feet (no jump apart and slide back), reach with a straight arm, and no longer turn his back or duck his face away.
- All fighters: heads no longer tilt to the side in the stance; hands stay in line with the forearm when blocking.
- New pose checker: every model build measures the stance and every animation on the real skeleton and lists joints, balance, floating feet and hands inside the body.
### Changed — stances after reference fighters
- Each stance now follows a well-known fighter the owner approved: Kairo an upright boxer (Steve Fox), Drakon wide with open arms (Zangief), Seraphina side-on with low hands (Hwoarang), Nox low and coiled (Raven), Vexa a tall high guard (Sagat), Ryuen upright with his lead palm out (Leroy Smith). Posed from knowledge of those characters, not from footage.
- Kairo's lead shoulder and fist are now in front of him; fighters who stand side-on keep looking at the opponent.
### Changed — stances posed by hand
- All six stances rebuilt as designed poses instead of adjusted boxing guards: Drakon hunched and reaching, Nox in a very low lunge, Vexa in a high Muay Thai guard, Seraphina bladed with her lead heel up, Ryuen sunk on his rear leg, Kairo orthodox (left foot forward).
### Changed — stances, second pass
- Kairo stands more upright with his fists at his chin; Nox's hands hang low; Seraphina's knees are softer.
- Each fighter has their own idle habit: Kairo bobs, Seraphina bounces, Drakon and Nox rock from side to side, Vexa taps her front foot, Ryuen stays still.
### Added — dashes
- Tap a direction twice (flick the stick twice) to dash forward or back. Each fighter has their own dash: Nox the longest, Seraphina the best back dash, Drakon and Ryuen short ones. You cannot block while dashing; a forward dash can go straight into an attack, a back dash cannot.
- The CPU dashes in from range and sometimes dashes away (Standard and Expert).
### Changed — stances of Drakon, Seraphina, Nox and Ryuen
- Drakon stands lower and squarer with his head forward; Seraphina holds her lead hand out and her rear hand at the chin; Nox crouches on two bent knees with low hands; Ryuen stands shorter and more upright with his lead palm forward.
### Added — hit feel
- Counter-hits: hitting an opponent out of their own attack does 20% more damage, stuns longer and freezes longer; the HUD shows COUNTER. Vexa's Cut Kick staggers and Ryuen's Sinking Elbow knocks down on counter-hit.
- Fighters react to where they are hit: head snaps back, body hits fold them over, leg hits knock the lead leg away.
- Stronger hit effects (streaks, a ring on heavy hits, red on counter-hits) and slow motion on the knockout.
### Added — Ryuen's own move set (all six fighters now have their own)
- Palm Heel (L), Chain Punch (H, three hits), Shin Stamp (K, low), Sinking Elbow (down + H), Mountain Push (SP, sends them across the stage), Flowing Step (toward + SP, evasive), Returning Wave (away + SP, catches any strike, turns the attacker round and palms them in the back), Wrist Throw (down + SP), ultimate Thousand Rivers (a counter stance: struck during it, he answers; otherwise the meter is wasted).
- His block pushes attackers back. Slowest walk after Drakon.
- Multi-hit moves and side-switching counters in the combat engine.
### Fixed — legs in the floor, Kairo's and Vexa's stances
- Fighters no longer stand shin-deep in the stage in The Pit and the Origin Chamber (the raised stage is lowered to their feet).
- Kairo stands in a staggered boxer's stance instead of a squat with his feet together; Vexa stands tall with her hands high (Muay Thai). The two no longer share a pose.
### Added — Vexa's own move set
- Piston Jab (L, longest light), Teep (H, pushes far away), Cut Kick (K, low), Slashing Elbow (down + H, steps in, cancels into the knee), Pulse Shot (SP, a projectile that crosses the stage, one at a time), Overclock Knee (toward + SP, flying knee, punishable on block), Arc Guard (away + SP, parries one high or mid hit; lows and throws beat it), ultimate System Overdrive. 1000 health, even walk speed both ways.
- Projectiles and parries in the combat engine. Counter stances do not catch projectiles; armour absorbs them; two that meet cancel out.
- The CPU sees and blocks projectiles, and a CPU Vexa mixes shots with walking in.
- Tools: move contact sheets (`tools/godot/move_shot.gd`), stretched-edge check (`tools/blender/stretch_check.py`), filtered test runs.
### Added — Nox's own move set
- Fang Jab (L), Rising Backfist (H), Scythe Sweep (K, low), Drop Heel (down + H, overhead), Shade Step (SP, passes through the opponent), Throat Pierce (toward + SP), Feint Fang (away + SP, fake overhead into a low), ultimate Eclipse. 850 health, fastest forward walk, takes extra chip damage.
- Pass-through moves in the combat engine.
### Added — Seraphina's own move set
- Knife-hand (L), Side Kick (H), Roundhouse (K), Low Sweep (down + K), Crescent Arc (SP, launches), Seraph Dive (toward + SP, overhead), Halo Step (away + SP, evasive), ultimate Radiant Ascension. 900 health, fastest backward walk.
- Launching and air hits, invulnerable frames and backward-moving attacks in the combat engine.
### Added — Drakon's own move set
- Hammer Fist (L), Haymaker (H), Shoulder Check (down + H), Stomp (K, low), Anvil Slam (SP, unblockable grab), Forge Charge (toward + SP, absorbs one hit), Quake Stomp (away + SP, low, long reach), ultimate Molten Colossus (grab).
- Drakon has more health (1150), takes half chip damage when blocking and walks slower.
- Throws and armour in the combat engine.
### Added — Kairo's own move set
- Low Kick (K): must be blocked low. Body Hook (down + H): combos after the jab. Slip Counter (back + SP): slips a punch and answers with a hook; low attacks beat it.
- Counter stances in the combat engine.
### Added — low block and direction commands
- Low block: hold the stick down + BLOCK. Low attacks must be blocked low, overheads standing, everything else either way. No fighter has a low or overhead attack yet; they arrive with the per-fighter move sets.
- Down + attack buttons and back + SP are now separate inputs (unused until each fighter's new moves are built; until then they act as the plain button).
- AI guards low/high with a per-difficulty chance.
### Added — hands
- Fists close: the fighters keep their finger bones. Kairo, Drakon and Vexa guard with fists, Seraphina with an open lead hand, Nox with loose hands, Ryuen with open palms; the palm strike opens the hand.
- `docs/FIGHTER_COMBAT_DESIGN.md`: per-fighter combat design summary (not yet implemented).
### Fixed / changed — stances and floor contact
- Each fighter has their own guard from a different motion-capture performer, shaped to the character: Kairo crouched boxer, Drakon heavy wide brawler, Seraphina karate side stance, Nox low predatory crouch, Vexa bouncy boxer, Ryuen calm open-palm master.
- Feet no longer sink into (or float above) the floor: every frame of every animation is fitted so the lowest point of the actual mesh touches the ground (was off by up to 25 cm, worst while walking).
- Kairo's twisted arm and hair spike fixed: the converter assumed mirror-symmetric skeletons; it now uses each side's own joints (his shoulders are not symmetric).
- Importer: `--rebuild-joints` (ignore a misplaced supplied skeleton but keep its weights); torso-based centring.
### Changed — new fighter roster
- All six fighters replaced by the owner's new Tripo models (T-pose, Mixamo rig, 4K textures): no more torn strips or stuck cloth when they move.
- Importer: FBX support with separate roughness/metal maps; normals only flipped where actually wrong; 60 fps enforced after FBX import.
### Fixed — fighter skinning after the second phone test
- Kairo's gauntlets no longer leave flaps behind when he raises his guard (arm membership: nearer the arm bone than the body's centre line and the legs); his sash stays on the hip.
- Nox's coat edges no longer stretch from his fists (small hand reach, fitted sleeves).
- Forearm and hand weights are all-or-nothing (no half-glove, half-coat vertices), arm weights can no longer leak onto cloth through smoothing, and faces fusing a hand to the coat are separated (nothing moves at rest).
- Idle is a steady guard (35% of the captured shadow-boxing bounce) instead of "dancing".
- Menu backdrops no longer show arena dust/embers (blurry blobs on phones).
- Seraphina still stretches at the hands (fingers fused into the coat); waiting for a re-rigged model.
### Changed — real motion capture, cleaner meshes, fixes from the first phone test
- Fighters move with real motion capture (CMU database): a boxer's bouncing guard, snapping jab, rotating cross, chambered front kick, lunging specials, a one-two combination ultimate, a real fall onto the back and a sit-up get-up. Every strike still lands on its frame-data active frames.
- Imported meshes are inspected and repaired before use: surfaces split at texture seams are joined (no more torn strips around hands, sashes and boots), stray inward faces turned outward; shapes untouched.
- Fighter colour textures kept at full 4K; sharper phone texture compression (ASTC).
- All six fighters playable; "LOCKED · M8" removed.
- Arena dust/ember particles were drawn as squares (and as big blurry blobs near the menu camera): they are now soft dots that fade out near the camera.
- Fight camera closer, so fighters fill more of the screen.
- Training readout restyled: compact, themed, move names instead of internal ids.
- New tools: `tools/blender/mocap_actions.py`, `tools/mocap/bvh.py`, `tools/mocap/fetch_clips.sh`, `tools/blender/mesh_check.py`.
### Fixed — fighter models
- Parts hanging out of the fighters: Kairo's sash no longer lifts out sideways with his guard (it hangs from the hip), Nox's hood and cloak no longer crush with his arms, and long strands from Ryuen's and Vexa's hands to their hips are gone (arm joints placed correctly; sleeves follow the arm).
- Fighters are lit by their own key and rim lights, tuned per arena, so the painted models read clearly against bright or dark backgrounds.
- `tools/blender/import_roster.sh` rebuilds all six fighters with their checked settings.
### Changed — fight HUD and results
- HUD in the Blood Signet style: angled health bars leaning outwards with a bevelled top edge, colour going gold → ember → crimson as health drops, white damage trail; fighter names, timer (in a framed box with a crimson cap), combo counter and announcer in display type; angled round markers; matching Origin meters.
- Touch pads restyled: dark glass discs with coloured rims and display-type labels; the stick gets a crimson rim, direction ticks and a bone-white knob. Pad colours follow the game palette.
- Blocking shows an energy barrier (hex lattice, glowing edges, rising ripple, flash on a blocked hit) in the fighter's colour instead of the old flat box. New shader `shaders/fx/block_shield.gdshader`.
- Results: the winner's name in big type, "P1 WINS" under it, a scoreboard row and one tag per round with how it ended.
- `tools/godot/fight_shot.gd`: screenshot of a real CPU fight (optional health/meter override).
### Changed — menus round 3
- Story: chapter cards (big chapter number, arena and opponent, CLEARED / NEW / LOCKED tag) under a chapters-cleared progress bar; dialogue gets a crimson speaker nameplate and the backdrop switches to whoever is speaking (Ryuen, Kairo, the chapter's opponent).
- Arcade: STAGE / SCORE / BEST tiles and a five-stage ladder (cleared, next, boss marked); Fight and End run side by side.
- Survival: DEFEATED / SCORE / BEST tiles, a health-carried-over meter that turns ember then crimson as it drops, and a next-opponent card.
- Shared card, tag and stat-tile widgets in `MenuScreen`.
### Changed — new fighter models
- The six playable fighters use the owner's rigged models: Kairo (heroic warrior), Drakon (armoured warrior), Nox (purple hooded warrior), Seraphina (superhero female), Vexa (female warrior), Ryuen (elder monk). Each keeps its own textures and shape, and has all 17 fight animations (idle, walk, punches, kick, specials, Origin Surge, ultimate, hits, block, knockdown, get-up, victory, defeat).
- Their display bases were removed; three broken supplied rigs (Ryuen, Vexa, Seraphina) were re-skinned.
- Textured fighters are shown without toon outline; a mirror match gives P2 a colour-tinted costume.
- `tools/blender/import_rigged.py` (convert a supplied rigged model), `tools/godot/roster_shot.gd` (in-engine roster screenshot).
### Changed — arena pass 3
- Hand-placed decals behind and under the fighters: glowing impact cracks and invented-script paint on the Severed Line roof, cracks, leaves and stains in the Sanctuary, scorch marks and cracks on The Pit's stage, glowing fissures in the Origin Chamber floor.
- Moving backdrop layers: sweeping searchlights and blinking aircraft lights over the city, drifting cloud banks in the Sanctuary, dust haze over The Pit's crowd, fake light shafts from the stage rigs and the Origin ceiling.
### Fixed
- The Pit's carved crest ring arcs faced downward, so they were invisible (only their baked shadow showed as a dark smear). The full crest now shows.
- Sanctuary baked bounce light was too strong (washed-out stone).
### Changed — menu redesign ("Blood Signet")
- Menus, round 2: drifting embers and a crimson blade wipe as each screen arrives; the crest lands and the logo fades in; each main-menu mode previews its arena behind the menu (Story → Sanctuary, Arcade/Training → The Pit, Versus → Severed Line, Survival → Origin Chamber); a LIVE lore ticker; fighter select shows POWER / SPEED / REACH / HEALTH bars computed from each fighter's real data and a large name watermark in the fighter's colour.
- New menu look: angled blade buttons and panels, crimson/ember/gold palette, Teko + Chakra Petch fonts, animated crest emblem, dark angled slab with a pulsing Origin vein behind the menus, fade-in and slide-out animations.
- Main menu: crest + logo, player card, five numbered mode blades with a line of context each, compact Profile / Settings / Quit row.
- Fighter and arena select: big display-type names; pause and results overlays use the same theme.
- `tools/godot/menu_shot.gd`: screenshots of any menu screen as the game shows it.
### Changed — arena pass 2
- Baked bounce light and glow spill (neon on walls, lamp pools, Origin crack glow) on top of the real-time lights; new arena surface shader with grime in corners and no visible texture tiling.
- Painted 360-degree backdrops: the neon city skyline and the Sanctuary's sea of clouds with distant floating islands.
- More detailed hero pieces: the conduit (flanges, pipes, exposed glowing coils), the ring gate (outer flange, carved ribs, plinth, hanging chains), the mining cranes (wheels, ladder, exhaust, pulleys, hook block), the Origin heart (molten spikes).
- More life: a drone circling the city, birds over the clouds, camera flashes in the crowd, fragments orbiting the heart, glow travelling along the Origin cracks.
- Arenas react to the fight: impact dust, puddle splashes or sparks on knockdowns and KOs, the crowd jumps harder, glows flare.
- Per-arena colour grading.
### Changed — arena quality pass
- All four arenas are textured (stone, quarry strata, wet concrete, rusted paint, gravel, obsidian, plaster, roof tiles, facades, gold) with normal and roughness maps, and have baked ambient occlusion.
- Motion: The Pit's crowd cheers and waves flags; Ryuen's banners sway; the Origin heart's three rings turn; Origin veins, neon signs, the Sanctuary crystal and the Origin emblems pulse or flicker; incense smoke in the Sanctuary.
- Close detail behind the fighters: a conduit armour plate smashed into the Severed Line roof (glowing cracks, rubble), crates, generator, satellite dish, antenna; an incense burner, bell rack, broken stone guardian and prayer cairns in the Sanctuary; crowd barrier, speaker stacks, flight cases, cable drums and broadcast cameras at The Pit; crystal clusters, broken pillars and floating fragments in the Origin Chamber.
### Fixed
- The Pit's quarry walls and bench tops faced away from the camera, so the engine hid them and the red sky showed through.
### Changed
- Ascendant Arena rebuilt as "The Pit": an octagon ring cut into the bedrock of an abandoned Origin-ore mine, with the carved crest (a V of two blades inside a ring broken into six), a crowd on seven quarry benches with phone lights and flags, two lattice mining cranes holding the light rigs, flood-light towers, a haul truck, conveyor wreck and red Origin veins in the walls (~50k tris, 8 materials). English banner/screen/floor text removed.
- Forgotten Temple rebuilt as "Ryuen's Sanctuary": a courtyard of worn running-bond slabs on a floating island at dawn, the great carved ring gate with gold inlays and the dormant Origin crystal keystone, monastery halls on chained floating rocks, Ryuen's blue banners with gold trim and wave emblem, stone lanterns, a sea of clouds (~30k tris, 8 materials). The English inscription was removed.
- Neon District rebuilt as "The Severed Line": a wet rooftop above the district with the broken Origin conduit hanging over the street, invented-script neon signs, a torn wanted poster, three-row skyline, falling Origin sparks, soft steam and a reflection probe (~21k tris, 8 materials). Real-world shop-name signs removed.
### Added
- New arena "The Origin Chamber" (`origin`): inside the Origin core, black-glass floor with red fractures, the molten Origin heart in a cage of rings, a dome of obsidian blades, and the six bloodline emblems frozen in crystal (~14k tris, 8 materials). Locked; clearing Story chapter 6 unlocks it.
- `ArenaConfig.unlock_hint`: each locked arena says how to earn it on the arena select screen (was one hard-coded line).
- Tests: Origin Chamber starts locked and unlocks after chapter 6; every locked arena has an unlock hint.
- `tools/godot/arena_shot.gd`: in-engine arena screenshots from the gameplay camera.
- `tools/blender/arena_concept_{neon,sanctuary,pit,origin}.py`: concept renders for the four arenas.

## [0.0.8-m7] — 2026-11-18
### Added
- Menus: main menu, fighter select, arena select, Story, Arcade, Survival, Profile, Settings — shared themed `MenuScreen` base with live 3D backdrops, Back/Android-back everywhere.
- Modes: Story (6 data-driven chapters with dialogue, unique Origin Warden boss), Arcade (5-stage ladder ending in the boss, score), Survival (one-round fights, health carry-over with 15% recovery, boss every 5th), Versus CPU, Training via the new flow.
- `MatchSetup` + `ModeFlow`: mode routing, run state, results options (Retry / Next stage / Continue / Change fighter).
- `SaveManager`: versioned JSON save (atomic write, per-field validation, migration, corrupt-file recovery); settings applied to touch controls, camera, audio, ambience.
- Progression: account level, fighter mastery, Shards currency, earnable titles, arena unlocks, statistics. No purchases, no energy.
- Art: parametric from-scratch character builder — Kairo, Drakon, Seraphina, Nox, Vexa, Ryuen, Origin Sentinel, Origin Warden (≈4.5–6k tris, 6 materials, shared rig + 17 animations each).
- Art: three from-scratch arenas with lighting, fog, glow, particles and signage — Ascendant Arena, Forgotten Temple, Neon District.
- 21 new tests (save/load, modes, navigation, results, settings, roster and arena budgets).
- Quality pass (`tools/blender/hero_builder.py`): Kairo, Origin Sentinel and Origin Warden rebuilt sculpt-style — continuous smooth bodies with anatomy, a modelled face, layered clothing, smooth joint skinning, painted vertex colours with baked cavity shading (≈25–31k tris).
- Kairo remodelled to the owner's approved art sheet (heroic build, fitted top with Origin line, forearm guards and gloves, torn red sash, knee guards, armoured boots, spiky hair with a red streak).
- Cel-shaded fighters: toon lighting, rim light and inked outlines.
### Changed
- Kairo blockout replaced by the new model; debug panel/hitboxes start hidden (F3/F4); training tools only in Training.
### Removed
- `tools/blender/build_kairo_blockout.py`, `kairo_blockout.glb` (superseded; no remaining references).

## [0.0.7-m6] — 2026-11-18
### Added
- Kairo blockout model built from scratch in Blender by script (18-bone humanoid rig, rigid skin, 17 animations at 60 fps), exported to GLB and used in game for both fighters (P2 recoloured).
- Simulation-driven `FighterAnimator` (attacks seeked to move frames), victory/defeat poses.
- Specials: Origin Palm (Special), Rift Break (toward + Special, moving, knockdown); knockdown/get-up.
- Origin meter (gains, carry-over between rounds), Origin Surge, ultimate Origin Break; HUD meter bars; SP/ULT touch buttons.
- Skippable presentation-only ultimate camera cinematic; Surge aura.
- Original synthesized placeholder SFX and `CombatAudio`.
- AI uses specials, Surge and ultimate within meter rules (meter discipline per difficulty).
- 16 new tests incl. hitbox-vs-limb alignment on the real model, rigid-skin/budget checks, full CPU-vs-CPU match in the real scene, specials infinite-combo search; mutation-checked.
- `docs/BLENDER_PIPELINE.md`, Blender/audio tools.
### Fixed
- Combat log now records an ultimate's start before the Surge ending it causes.

## [0.0.6-m5] — 2026-11-18
### Added
- CPU opponent: finite-state-machine `AIController` with spec states, distance bands, weighted move selection, combo route, reaction-delayed blocking, guard, punish, mash-out reversals, spacing anticipation, anti-idle.
- Fair perception: `AIObservation` (human-visible info only), whole screen seen with reaction delay.
- Difficulty profiles Beginner / Standard / Expert (`data/ai/`), main-menu "AI:" selector, debug P2 cycling, HUD "CPU <level>" label.
- AI decision log (debug panel + stdout), `tools/ai_benchmark.gd`, `docs/AI_TUNING.md`.
- 9 new tests (perception delay, future-input, legality replay, difficulty ordering, defeatable, anti-idle, determinism); mutation-checked.
### Changed
- Versus P2 is now the CPU by default; the dummy remains in Training and via T.

## [0.0.5-m4] — 2026-11-18
### Added
- Multi-touch controls: floating stick + Light/Heavy/Kick/Block cluster, touch-down, per-finger tracking, left-handed toggle (pause menu).
- 6-tick input buffer (frozen during hitstop) in the simulation; `CombatTuning` data.
- Cancel routes via move `tags` / `cancel_tags`, cancel window and same-move repeat limit; Kairo L→L, L→K.
- Combo counter and damage scaling (100/100/80/70/60/50/40 %); HUD "N HITS".
- Training mode (main menu → Training): ∞ timer, no KO, health refill, Reset, combo/frame-data panel, input history.
- 16 new tests incl. exhaustive infinite-combo search and two-finger touch tests; mutation-checked.
### Changed
- Temporary DEBUG on-screen buttons removed (replaced by real touch controls).
- M2 hitstop press latch replaced by the input buffer.

## [0.0.4-m3] — 2026-11-18
### Added
- Best-of-three match loop: `MatchRules` data + deterministic `MatchDirector` (intro, fight, round end, match end).
- 90 s round timer, KO / time-out / draw / double-KO results, round cap guaranteeing termination.
- Match HUD: health bars with damage trail, timer, round label, round-win pips, announcer, pause button.
- Pause menu (Resume / Restart match / Quit), auto-pause on app background, Android back toggles pause.
- Results screen (winner or DRAW, score, per-round reason) with Rematch / Main menu.
- 13 new tests incl. per-tick invariants over 12 seeded random matches; mutation-checked.
### Changed
- Debug R/F5 restarts the match; on-screen Reset/Menu debug buttons removed; 3D name labels hidden (HUD shows names).

## [0.0.3-m2] — 2026-11-18
### Added
- Attack data model `MoveData` (all spec §4.3 fields) and `FighterDefinition`; Kairo light/heavy/kick data.
- Fighter state machine: idle, walk, block, attack (startup/active/recovery), hitstun, blockstun, KO.
- `HitboxSystem` (per-tick rect overlap) and `HitResolver` (hit/block, damage, chip, stun, pushback, corner transfer, trades, KO).
- Global hitstop with press latching; tick-stamped `CombatLog`.
- Placeholder hit reactions (lean, flash, hitstop shake), block shield, fist extension, hit/block sparks, camera shake.
- Hitbox debug view (F4), training reset (R/F5), dummy modes STAND/BLOCK/JAB (T/F6), temporary DEBUG attack/block touch buttons.
- 15 new tests incl. frame-advantage-vs-data, punish, trade, determinism of 1,200-tick combat logs; autoload guard test.
### Changed
- Combat scene uses `FighterDefinition` resources; heavy punch pushback 0.2 m.
### Fixed
- Removed a screenshot-capture helper accidentally committed in M1 (auto-pressed menu buttons; failed M1 CI).

## [0.0.2-m1] — 2026-11-18
### Added
- Fixed 60 Hz combat tick (`CombatClock`) with render interpolation and a catch-up cap.
- Deterministic `CombatSimulation`: walking (forward/back speeds), facing, pushboxes, arena walls, max separation.
- Typed data resources: `ArenaConfig` (`data/arenas/greybox_arena.tres`), `FighterMovementProfile` (`data/fighters/*.tres`).
- Greybox arena, placeholder capsule fighters, side-on camera rig with visibility guarantee.
- Debug overlay (F3), temporary debug touch buttons, Menu/back to main menu.
- 16 new tests (simulation, clock/frame-rate independence, scene integration with camera frustum checks).
### Changed
- Main menu "Fight" now opens the greybox scene.
- Test runner now runs on the first frame; CI fails on any script error in logs and smoke-runs the combat scene.

## [0.0.1-m0] — 2026-11-17
### Added
- Godot 4.7.2 project: Mobile renderer, sensor-landscape orientation, 2400×1080 reference viewport.
- Boot screen and placeholder main menu with safe-area margins; `SceneRouter` autoload.
- Input map (12 logical actions) with keyboard/gamepad debug bindings.
- Android export preset (no signing data).
- Headless test runner with project-configuration tests; GitHub Actions CI.
- `CLAUDE.md`, README, decision log, milestone checklist, known issues, doc stubs.
