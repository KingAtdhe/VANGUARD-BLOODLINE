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

## Milestone 1 — greybox arena and fighters  ✅ implemented, awaiting approval
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

## Milestone 2 — attacks and hit detection
## Milestone 3 — match loop
## Milestone 4 — combo and input systems (touch controls)
## Milestone 5 — AI
## Milestone 6 — Kairo vertical slice
## Milestone 7 — UI, menus and modes
## Milestone 8 — remaining fighters and arenas
## Milestone 9 — release preparation
