# Milestones

Acceptance criteria are defined in `PRODUCTION_PACKAGE.md` §12. One milestone at
a time; each completed milestone is tagged in Git (`m0`, `m1`, …).

## Milestone 0 — repository and project setup  ✅ approved

- [x] Repository created (`KingAtdhe/VANGUARD-BLOODLINE`)
- [x] `CLAUDE.md` added
- [x] Design/technical documents added (`docs/`)
- [x] Godot project created (4.7.2-stable)
- [x] Landscape orientation configured (sensor landscape)
- [x] Input actions configured (keyboard + gamepad debug bindings)
- [x] Mobile renderer configured
- [x] Boot scene + placeholder main menu
- [x] Placeholder assets (labelled icon)
- [x] Android export preset without secrets
- [x] Headless test runner + 6 config tests, CI workflow

Acceptance:
- [x] Project opens in pinned Godot version — verified headless (import + run)
- [x] Main scene launches — verified headless; boot → main menu, no errors
- [ ] **Landscape orientation correct on a test device — NOT VERIFIED (needs physical Android device)**
- [x] No missing resource errors — verified headless
- [x] Git repository clean after milestone commit

## Milestone 1 — greybox arena and fighters  ✅ approved
- [x] Greybox stage (`scenes/arenas/greybox_arena.tscn`)
- [x] Two capsule/primitive fighters (P1 Kairo placeholder, P2 idle training dummy)
- [x] Camera rig (midpoint tracking, bounded zoom, visibility guarantee)
- [x] Spawn points (from `data/arenas/greybox_arena.tres`)
- [x] Arena boundaries (walls placed from the same data)
- [x] Movement and facing on a fixed 60 Hz tick, pushboxes, max separation
- [x] Basic debug display (F3) + temporary debug touch buttons
- [x] Main menu "Fight" opens the greybox scene; Menu/back returns

Acceptance:
- [x] Both fighters remain within the arena — unit + integration tests
- [x] They face each other correctly — unit + integration tests
- [x] Camera keeps both fighters visible — integration test (frustum check at
      feet/centre/head while walking to both walls) + visual capture
- [x] Movement works at different render frame rates — identical per-tick
      positions at 30/60/90/120/144 fps and jittery frame times
- [ ] **On-device check (touch debug buttons, framing on a real phone) — NOT VERIFIED**

## Milestone 2 — attacks and hit detection  ✅ approved
- [x] Attack data model (`MoveData`, all spec §4.3 fields) + `FighterDefinition`
- [x] Hurtbox and hitbox system (`HitboxSystem`), debug view (F4)
- [x] Light, heavy and kick attacks (Kairo placeholder data, spec §4.4 values)
- [x] Block (hold BLOCK), blockstun, chip
- [x] Damage and hit reaction (hitstun, lean, flash), KO
- [x] Global hit-stop and basic effects (sparks, camera shake, hitstop shake)
- [x] Combat log (tick-stamped events, on-screen + stdout)
- [x] Training dummy modes STAND / BLOCK / JAB, training reset

Acceptance:
- [x] Active hitboxes only exist during active frames — frame-by-frame test for all 3 moves
- [x] One attack cannot hit the same opponent repeatedly — test (held button, 80 ticks in range)
- [x] Blocking and damage rules are consistent — tests: damage, chip, stun lengths,
      frame advantage measured in the sim equals the data formula, punish, trade, attacking-can't-block
- [x] Hit detection is reproducible and debuggable — identical 1,200-tick combat logs across runs;
      hitbox debug view draws the exact simulation boxes; tick-stamped combat log
- [ ] **On-device check — NOT VERIFIED**
## Milestone 3 — match loop  ✅ approved
- [x] Health bars (with damage trail)
- [x] Timer (90 s, integer ticks, shown rounded up)
- [x] Round counter + round-win pips, ROUND n / FINAL ROUND / FIGHT! / K.O. / TIME announcer
- [x] Best-of-three logic (`MatchDirector`, `MatchRules` data)
- [x] Win/lose/draw results screen with per-round reasons
- [x] Rematch (results screen, pause menu "Restart match", debug R)
- [x] Pause (Esc/P/Start, on-screen II, Android back, auto on app background)

Acceptance:
- [x] Match always reaches a valid end state — KO, time-out, all-draw, double-KO,
      round-cap and 12 seeded random-mash matches all end; invariants checked every tick
- [x] Timer and health cannot become invalid — per-tick invariant checks (0 ≤ health ≤ max,
      0 ≤ timer ≤ 5,400, round wins ≤ target); timer ends at exactly 0
- [x] Round transitions reset positions and state correctly — test compares every field after round 1
- [x] Rematch starts a clean match — director + scene tests (round 1, 0–0, full health, empty log)
- [ ] **On-device check (HUD layout on a real phone, pause on home/back) — NOT VERIFIED**
## Milestone 4 — combo and input systems  ✅ approved
- [x] Touch controls: multi-touch stick + L/H/K/Block cluster, left-handed toggle (DEBUG buttons removed)
- [x] Keyboard/gamepad debug controls (every gameplay action has both — tested)
- [x] Input buffer (6 ticks, frozen during hitstop)
- [x] Cancel routes (tags, window, repeat limit) — Kairo L→L, L→K
- [x] Combo counter and scaling (HUD "N HITS", training panel)
- [x] Training mode + training reset (main menu → Training)
- [x] Input history (training panel)

Acceptance:
- [x] Simultaneous movement and attack works — sim test (attack while holding a direction,
      walk resumes) + touch test (two fingers: stick + button, independent release) + touch combo in scene
- [x] Buffered inputs execute only when legal — tests: executes on the first neutral tick only
      within the window; never during hitstun; reversal within window; illegal cancels stay unused
- [x] Invalid cancel routes are rejected — L→H, K→L, H→L, whiff, late, 3rd Light
- [x] No infinite combo possible in the tested move set — exhaustive 363-route × 4-situation
      search; max 3 hits; defender always recovers
- [ ] **On-device check (touch feel, thumb reach, multi-touch on a real phone) — NOT VERIFIED**
## Milestone 5 — AI  ✅ approved
- [x] AI state machine (spec states) — `AIController`
- [x] Distance evaluation (bands from the fighter's own move ranges, spacing projection)
- [x] Attack selection (weighted, in-range, close-range Light bias, combo route)
- [x] Block / punish behaviour (reaction-delayed blocks, guard, punish visible recovery, mash-out)
- [x] Difficulty settings (Beginner / Standard / Expert data profiles; main-menu selector)
- [x] Decision logging (per-AI log on debug panel + stdout in debug builds)

Acceptance:
- [x] AI uses the same legal combat actions as the player — outputs FighterInputFrame only;
      replaying its inputs as a human reproduces the fight exactly; no illegal cancels
- [x] AI does not read future input — perception-delay test (catches an instant-vision
      cheater 12–16/20) + diverging-worlds test
- [x] Each difficulty is distinguishable — stronger wins ≥ 75 % both sides (actual 10–0);
      blocking vs the same pressure script ordered by level
- [x] AI can be defeated and does not become idle permanently — scripted player beats
      Beginner/Standard; Expert takes hits; every level beats a passive opponent; idle
      streak bounded
- [ ] **Feel vs a human on a phone — NOT VERIFIED (needs playtests)**
## Milestone 6 — Kairo vertical slice  ✅ implemented (blockout art), awaiting approval
- [~] Create final Kairo model in Blender — **blockout** built from scratch by script; final art pending an artist
- [x] Rig and skin — humanoid skeleton (Godot profile names), rigid skin
- [x] Export to GLB / import into Godot (60 fps import)
- [x] Animation state machine — `FighterAnimator`, simulation-driven
- [x] Base animation set for the current mechanics (17 animations; dash/crouch/jump/throw wait for their mechanics)
- [x] Two special moves — Origin Palm, Rift Break
- [x] Origin Surge and ultimate (Origin Break) with meter, HUD, SP/ULT touch buttons, skippable cinematic
- [~] Voice/sound — original synthesized SFX placeholders; voice and final audio pending

Acceptance:
- [x] Kairo can complete a full match — CPU-vs-CPU full match through the real scene, results + victory pose
- [x] Animations transition cleanly — state-driven with cross-fades; attack poses reached before active frames
- [x] No severe mesh deformation — rigid skin, every vertex 100 % one bone (test)
- [x] Hitboxes align with attacks — limb inside hitbox on every active frame, both facings (test, mutation-checked)
- [ ] **Performance meets agreed device target — NOT VERIFIED** (no device; blockout is 1,638 tris × 2 fighters, 6 materials each)
## Milestone 7 — UI, menus and modes
## Milestone 8 — remaining fighters and arenas
## Milestone 9 — release preparation
