# Known Issues

| ID | Milestone | Issue | Status |
|---|---|---|---|
| KI-001 | M0 | Android build and on-device landscape check not yet performed (no export templates / SDK / device in the setup environment). | Open — needs manual test |
| KI-002 | M0 | Mobile (Vulkan) renderer verified only headless; the visual check used the compatibility renderer under a virtual display. | Open — verify on device |
| KI-003 | M0 | Project icon and title are placeholders pending legal/trademark review. | Open — by design |
| KI-004 | M1 | P2 is an idle dummy; it can't move on its own until the AI milestone (M5). | Open — by design |
| KI-005 | M1 | Debug touch buttons were single-touch only. | Fixed in M4 (multi-touch TouchControls) |
| KI-006 | M1 | No jump/crouch, so fighters cannot switch sides; side-switch facing is covered by a unit test only. | Open — by design |
| KI-007 | M1 | Combat does not pause when the app is backgrounded. | Fixed in M3 (auto-pause) |
| KI-008 | M1 | A screenshot-capture helper (`cap.gd` + autoload) was accidentally committed in the M1 commit: it auto-pressed Fight/Menu after launch and failed the M1 CI run. Removed in M2; a test now fails on any unexpected autoload. | Fixed in M2 |
| KI-009 | M2 | No input buffer. | Fixed in M4 (6-tick buffer) |
| KI-010 | M2 | No health bars or round end; KO just freezes the fighter until training reset. | Fixed in M3 |
| KI-011 | M2 | Attacker's extended limb has no hurtbox, so attacks can't be whiff-punished at the limb. | Open — revisit with real models (M6) |
| KI-012 | M2 | Camera shake has no setting yet (spec: reduced-shake option); `CameraRig.shake_scale` is ready for M7 settings. | Open |
| KI-013 | M3 | "Fight" is P1 vs the scripted dummy — the dummy never attacks unless set to JAB, so matches are one-sided until the AI (M5). | Open — by design |
| KI-014 | M3 | Results/menus are plain placeholder UI; no character select, no localisation, no accessibility text sizing yet (M7). | Open — by design |
| KI-015 | M3 | HUD health bars use the default font and colours; colour-blind-safe palette and contrast review pending (M7). | Open |
| KI-016 | M4 | Left-handed layout, control size and opacity are not saved between sessions (save system is M7). | Open |
| KI-017 | M4 | Stick up/down emit jump/crouch actions, but jump/crouch are not implemented. | Open — by design |
| KI-018 | M4 | Touch controls show in debug builds even without a touchscreen (handy for desktop testing; a setting will control this in M7). | Open |
| KI-019 | M4 | Tap feel, thumb reach and button spacing are unverified on real phones; layout constants are in `touch_controls.gd`. | Open — needs device test |
