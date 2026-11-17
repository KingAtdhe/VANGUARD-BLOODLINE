# Milestones

Acceptance criteria are defined in `PRODUCTION_PACKAGE.md` §12. One milestone at
a time; each completed milestone is tagged in Git (`m0`, `m1`, …).

## Milestone 0 — repository and project setup  ✅ implemented, awaiting approval

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

## Milestone 1 — greybox arena and fighters
- [ ] Greybox stage
- [ ] Two capsule/primitive fighters
- [ ] Camera rig
- [ ] Spawn points
- [ ] Arena boundaries
- [ ] Movement and facing (fixed 60 Hz tick)
- [ ] Basic debug display

## Milestone 2 — attacks and hit detection
## Milestone 3 — match loop
## Milestone 4 — combo and input systems (touch controls)
## Milestone 5 — AI
## Milestone 6 — Kairo vertical slice
## Milestone 7 — UI, menus and modes
## Milestone 8 — remaining fighters and arenas
## Milestone 9 — release preparation
