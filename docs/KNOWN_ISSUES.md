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
| KI-013 | M3 | "Fight" was P1 vs a passive dummy. | Fixed in M5 (CPU opponent) |
| KI-014 | M3 | Results/menus are plain placeholder UI; no character select, no localisation, no accessibility text sizing yet (M7). | Open — by design |
| KI-015 | M3 | HUD health bars use the default font and colours; colour-blind-safe palette and contrast review pending (M7). | Open |
| KI-016 | M4 | Left-handed layout, control size and opacity are not saved between sessions (save system is M7). | Open |
| KI-017 | M4 | Stick up/down emit jump/crouch actions, but jump/crouch are not implemented. | Open — by design |
| KI-018 | M4 | Touch controls show in debug builds even without a touchscreen (handy for desktop testing; a setting will control this in M7). | Open |
| KI-019 | M4 | Tap feel, thumb reach and button spacing are unverified on real phones; layout constants are in `touch_controls.gd`. | Open — needs device test |
| KI-020 | M5 | AI difficulty is tuned machine-vs-machine only; Standard loses to frame-perfect L, L, K pressure scripts and may feel easy to strong players. Needs human playtests. | Open |
| KI-021 | M5 | AI difficulty choice is session-only (resets on app restart) until the M7 save system. | Fixed in M7 (saved setting) |
| KI-022 | M5 | P2 in versus uses the "Training Dummy" fighter data (a Kairo copy) until more fighters exist (M8); HUD labels it "— CPU <level>". | Open — by design |
| KI-023 | M6 | Kairo is a scripted blockout (labelled BLOCKOUT), not final art; P2 is the same model recoloured blue. | Superseded in M7 by the roster builder (still stylized, script-made) |
| KI-024 | M6 | Placeholder synthesized SFX only; no voice. | Open — needs audio |
| KI-025 | M6 | Meter economy tuned machine-vs-machine: a dominant player rarely reaches Surge in a 2–0; even matches do. Needs playtests. | Open |
| KI-026 | M6 | Quitting the app while a sound is playing can print "resources still in use at exit" (engine exit-time audio race; harmless; headless CI unaffected). | Open |
| KI-027 | M6 | Device performance unmeasured; spec target 60 FPS on chosen devices. | Open — needs device |
| KI-028 | M6 | P2 AI may still log "sees … → BLOCK" while knocked down (no effect; cosmetic in the AI log). | Open |
| KI-029 | M7 | Drakon, Seraphina, Nox, Vexa, Ryuen are viewable but locked: their movesets are Milestone 8. | Open — by design |
| KI-030 | M7 | Fighter models use rigid per-part skinning; joints show seams up close (menus). | Open — needs artist/skinning pass |
| KI-031 | M7 | Visual review was done with the desktop GL Compatibility renderer under xvfb; the Mobile (Vulkan) renderer on a phone may differ (glow/fog strength). | Open — needs device |
| KI-032 | M7 | Menu 3D backdrops render a second 3D world; cost on low-end phones unmeasured. "Reduce arena effects" only disables particles. | Open — needs device |
| KI-033 | M7 | No music yet, so there is no music volume setting. | Open — needs audio |
| KI-034 | M7 | Story text and character names are placeholders pending writing/legal review. | Open |
| KI-035 | M7 | Drakon, Seraphina, Nox, Vexa, Ryuen still use the older toy-like models (fighter select only); they move to the hero pipeline with their movesets in M8. | Open |
| KI-036 | M7 | Animations are still the M6 pose-to-pose set (stiff); arenas and UI have not had their quality pass yet. | Open — next |
| KI-037 | M7 | Godot's glTF import leaves the first surface's vertex colours off; `ModelUtil.enable_vertex_colors` fixes it at load (tested). | Worked around |
| KI-038 | M7 | Test APKs are signed with a fresh throwaway key per build, so a new build won't install over an old one: uninstall first (progress is lost). | Open — stable debug key needed |
| KI-039 | M7 | Only Kairo is modelled to the approved art sheet. Drakon, Seraphina, Nox, Vexa and Ryuen still use old models; Sentinel/Warden keep the earlier construct look. | Open — next |
| KI-040 | M7 | Kairo's 3D face is simpler than the art sheet; no textures (vertex colour only); sash is rigid cloth (no physics). | Open |
| KI-041 | M7 | Provenance/rights of the owner-supplied art sheet are not recorded yet. | Open — owner |
| KI-042 | M8 | The Severed Line (neon) uses a ReflectionProbe; Godot 4.7.2 prints "7 RIDs of type Texture were leaked" at engine shutdown whenever a probe has existed (reproduced in an empty project with one probe). Exit-time only, no in-game effect. | Engine — monitor |
| KI-043 | M8 | The Severed Line was checked only on Mesa software Vulkan (lavapipe) with the Mobile renderer; frame rate, glow and the reflection probe cost on a phone are unverified. | Open — needs device |
| KI-044 | M8 | Ryuen's Sanctuary: the Origin crystal keystone sits above the gameplay camera's view at normal zoom (visible in menus and wide shots); banners are rigid panels (no cloth motion). | Open |
