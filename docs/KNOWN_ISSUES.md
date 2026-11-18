# Known Issues

| ID | Milestone | Issue | Status |
|---|---|---|---|
| KI-001 | M0 | Android build and on-device landscape check not yet performed (no export templates / SDK / device in the setup environment). | Open — needs manual test |
| KI-002 | M0 | Mobile (Vulkan) renderer verified only headless; the visual check used the compatibility renderer under a virtual display. | Open — verify on device |
| KI-003 | M0 | Project icon and title are placeholders pending legal/trademark review. | Open — by design |
| KI-004 | M1 | P2 is an idle dummy; it can't move on its own until the AI milestone (M5). | Open — by design |
| KI-005 | M1 | Debug touch buttons use mouse-emulated touch: only one can be held at a time (e.g. you cannot walk and block together on a phone). Real multi-touch controls arrive in M4. | Open — temporary |
| KI-006 | M1 | No jump/crouch, so fighters cannot switch sides; side-switch facing is covered by a unit test only. | Open — by design |
| KI-007 | M1 | Combat does not pause when the app is backgrounded; on resume the clock drops the stalled time (max 5 catch-up ticks). Proper pause arrives in M3. | Open |
| KI-008 | M1 | A screenshot-capture helper (`cap.gd` + autoload) was accidentally committed in the M1 commit: it auto-pressed Fight/Menu after launch and failed the M1 CI run. Removed in M2; a test now fails on any unexpected autoload. | Fixed in M2 |
| KI-009 | M2 | No input buffer: a press during attack recovery or stun is dropped (presses during hitstop are latched but also dropped if the fighter is still busy). Input buffer is M4. | Open — by design |
| KI-010 | M2 | No health bars or round end; KO just freezes the fighter until training reset. Match loop is M3. | Open — by design |
| KI-011 | M2 | Attacker's extended limb has no hurtbox, so attacks can't be whiff-punished at the limb. | Open — revisit with real models (M6) |
| KI-012 | M2 | Camera shake has no setting yet (spec: reduced-shake option); `CameraRig.shake_scale` is ready for M7 settings. | Open |
