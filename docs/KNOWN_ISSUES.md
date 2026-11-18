# Known Issues

| ID | Milestone | Issue | Status |
|---|---|---|---|
| KI-001 | M0 | Android build and on-device landscape check not yet performed (no export templates / SDK / device in the setup environment). | Open — needs manual test |
| KI-002 | M0 | Mobile (Vulkan) renderer verified only headless; the visual check used the compatibility renderer under a virtual display. | Open — verify on device |
| KI-003 | M0 | Project icon and title are placeholders pending legal/trademark review. | Open — by design |
| KI-004 | M1 | P2 is an idle dummy; it can't move on its own until the AI milestone (M5). | Open — by design |
| KI-005 | M1 | Debug ◀ ▶ buttons use mouse-emulated touch: only one can be held at a time, and there is no attack input yet. Real multi-touch controls arrive in M4. | Open — temporary |
| KI-006 | M1 | No jump/crouch, so fighters cannot switch sides; side-switch facing is covered by a unit test only. | Open — by design |
| KI-007 | M1 | Combat does not pause when the app is backgrounded; on resume the clock drops the stalled time (max 5 catch-up ticks). Proper pause arrives in M3. | Open |
