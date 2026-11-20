# Licenses and Asset Ownership

All shipped assets must be original or properly licensed (spec §1.3, §16).
Record every third-party asset, font, sound, plugin or tool output here
**before** it is committed.

| Asset / dependency | Source | License | Used in | Added |
|---|---|---|---|---|
| Godot Engine 4.7.2 | godotengine.org | MIT | Engine | 2026-11-17 |
| Default Godot UI font | Bundled with Godot | (engine default font license — verify before release) | Fallback only (HUD, debug) | 2026-11-17 |
| Teko (SemiBold, Medium) — `assets/fonts/Teko-*.woff2` | Google Fonts via the @fontsource/teko npm package | SIL Open Font License 1.1 (`assets/fonts/OFL-Teko.txt`) | Menu display type: titles, buttons | 2026-11-20 |
| Chakra Petch (Medium, Bold) — `assets/fonts/ChakraPetch-*.woff2` | Google Fonts via the @fontsource/chakra-petch npm package | SIL Open Font License 1.1 (`assets/fonts/OFL-ChakraPetch.txt`) | Menu body text | 2026-11-20 |
| Arena textures, decals, lightmaps, panoramas, banner, poster | Generated from scratch by `tools/art/*.py` and `tools/blender/*.py` (the poster uses the owner's Kairo portrait) | Project-owned | Arenas | 2026-11-20 |
| `icon.svg` placeholder | Original, made for this project | Project-owned | Project icon | 2026-11-17 |
| `assets/characters/{kairo,drakon,nox,seraphina,vexa,ryuen}/*.glb` and `assets/characters/_source/*.glb` | Supplied by the project owner (generated with Tripo; rigged); converted by `tools/blender/import_rigged.py` | Project-owned (owner-supplied) | Playable fighter models | 2026-11-20 |
| `assets/characters/{sentinel,warden}/*.glb` | Generated from scratch by `tools/blender/character_builder.py` (no base mesh/external assets) | Project-owned | Boss models | 2026-11-18 |
| `assets/arenas/*/*_arena.glb` | Generated from scratch by `tools/blender/arena_builder.py` | Project-owned | Arena geometry | 2026-11-18 |
| `docs/art/reference_roster_sheet.png` | Character art sheet supplied by the project owner (source/tool to be recorded by the owner before release) | Owner-supplied — confirm rights before release | Approved design reference for the 3D models | 2026-11-18 |
| Story text, signage text, fighter names | Original, written for this project | Project-owned | Story/arenas | 2026-11-18 |
| `audio/sfx/placeholder_*.wav` | Synthesized by `tools/audio/generate_placeholder_sfx.py` (no samples) | Project-owned | Placeholder SFX | 2026-11-18 |
| Blender 5.3 (tool only, not shipped) | blender.org | GPL (tool output is not GPL) | Build pipeline | 2026-11-18 |

Project code license: **not yet chosen** (repository is public — decide before
outside contributions; until then all rights reserved by the owner).
