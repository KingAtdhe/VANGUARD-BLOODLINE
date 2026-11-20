# Blender Pipeline

Canonical source: `PRODUCTION_PACKAGE.md` §8.2–§8.4. Implemented in
Milestone 6 with a **scripted blockout**; final art plugs into the same
pipeline.

## What exists now

`tools/blender/character_builder.py` builds Kairo **from scratch** (no
base mesh, no external assets) and exports `assets/characters/<id>/<id>.glb`:

- stylized blockout mesh from primitives — 1,638 triangles, 6 materials
  (`BLOCKOUT_*`), red Origin-energy accents;
- humanoid skeleton (18 bones) named per Godot `SkeletonProfileHumanoid`;
- rigid skinning (every vertex 100 % on one bone → no joint deformation);
- 17 actions, 60 fps, named `FIGHTER_ACTION_VARIANT`.

The script is the source asset: it is versioned, reviewable and reproducible.
It is a **placeholder** — clearly labelled, to be replaced by final art.

### Rebuild

```bash
# 1. Export current move timings from the game data
godot --headless --path . --script res://tools/blender/export_move_timing.gd -- /tmp/kairo_moves.json
# 2. Build + export (Blender 5.x; works as `pip install bpy` or `blender -b -P`)
python tools/blender/character_builder.py --fighter kairo --moves /tmp/kairo_moves.json --out assets/characters
# 3. Re-import and run tests (hitbox alignment will fail if anything drifted)
godot --headless --path . --import && godot --headless --path . --script res://tests/run_tests.gd
```

## Conventions (final art must keep these)

| Item | Convention |
|---|---|
| Units / scale | Metres; Kairo ≈ 1.8 m tall; origin on the ground between the feet |
| Orientation | Character faces **−Y** in Blender (+Z after glTF export); Z up |
| Skeleton | Bone names: `Root, Hips, Spine, Chest, Neck, Head, Left/Right UpperArm, LowerArm, Hand, UpperLeg, LowerLeg, Foot`. Extra bones (fingers, cloth) may be added; these must not be renamed |
| Root motion | **None.** Animations are in place; the simulation moves the fighter (e.g. Rift Break's 1.4 m travel) |
| Frame rate | 60 fps. Frame N of an attack animation = combat tick N of the move |
| Attack length | Animation frames = move `startup + active − 1 + recovery` (test enforced) |
| Hit poses | On every active frame the striking hand/foot must sit inside the move's hitbox (`hitbox_center` ± size/2, 6 cm tolerance; test enforced, both facings) |
| Names | `KAIRO_IDLE_A`, `KAIRO_WALK_FORWARD`, `KAIRO_WALK_BACKWARD`, `KAIRO_BLOCK_HIGH`, `KAIRO_HIT_LIGHT`, `KAIRO_HIT_HEAVY`, `KAIRO_KNOCKDOWN`, `KAIRO_GETUP`, `KAIRO_VICTORY`, `KAIRO_DEFEAT`, `KAIRO_ATTACK_LIGHT_01`, `KAIRO_ATTACK_HEAVY_01`, `KAIRO_KICK_01`, `KAIRO_SPECIAL_ORIGIN_PALM`, `KAIRO_SPECIAL_RIFT_BREAK`, `KAIRO_SURGE_ACTIVATE`, `KAIRO_ULTIMATE_ORIGIN_BREAK` |
| Export | glTF 2.0 binary (`.glb`), skins on, animations as actions, force sampling, Y-up |
| Godot import | `animation/fps = 60` in the `.glb.import` (Godot's default 30 drops keys) |
| Budgets | ≤ 45k triangles, 3–6 material slots (test enforced) |
| Source files | `.blend` sources go through Git LFS (`.gitattributes`); never overwrite the only copy |

Skin weights for final art may blend across bones (unlike the rigid
blockout); the rigid-skin test then becomes a visual deformation review at
extreme poses.

## How the game uses the model

`FighterDefinition.model_scene` points at the `.glb`; reaction animations are
mapped on the definition (`anim_idle`, `anim_hit_light`, …) and attacks via
each `MoveData.animation`. `FighterAnimator` picks the animation from
simulation state and **seeks** attacks to their move frame — the animation is
never the combat clock. `FighterView` turns the model to face the opponent
(78° yaw: profile, slightly toward the camera) and recolours the Origin
accent per player.

## Base animation list — status

| Spec §8.4 item | Status |
|---|---|
| Idle loop / walk forward / walk backward | ✅ |
| Light, heavy, kick, block high, hit light, hit heavy | ✅ |
| Knockdown, get-up | ✅ |
| Special 1 (Origin Palm), special 2 (Rift Break), ultimate (Origin Break) | ✅ + Surge activation |
| Victory, defeat | ✅ |
| Idle variation, dash F/B, crouch idle/transition, jump start/air/land, block low, throw start/receive | ⏳ not needed until those mechanics exist |


## Milestone 7: roster and arenas

```
python tools/blender/character_builder.py --all --moves /tmp/kairo_moves.json --out assets/characters
python tools/blender/arena_builder.py --out assets/arenas
```
- Each fighter: one parametric body (proportions, outfit pieces, hair, palette)
  on the shared rig; materials `<ID>_Skin/Cloth/Cloth2/Accent/Hair/Gear`
  (`_Accent` is recoloured for mirror matches). Clips are `<ID>_*`.
- Arenas: one mesh per arena, ≤8 materials, emissive trims; lights, fog,
  glow, particles and text are in `scenes/arenas/*.tscn`.
- After a rebuild, keep `animation/fps=60` in each `.glb.import`.
- Arena surfaces (D-051): `python3 tools/art/make_arena_textures.py` makes the
  shared textures; `arena_builder.py` then bakes AO and writes the Godot
  materials (`--no-bake` is a fast geometry preview only: it writes
  materials without AO). After a rebuild run Godot's import once, then
  `python3 tools/art/arena_texture_imports.py` and import again so the
  textures are VRAM-compressed with mipmaps.
- Arena pass 2 (D-052): the full build (`arena_builder.py`, no flags) bakes
  AO and the lightmap (several minutes per arena). `--materials-only`
  rewrites the Godot materials after a tuning change without re-baking.
  Panorama skies: `python tools/blender/arena_panorama.py <neon|temple>
  assets/arenas/<id>/<id>_sky.png 4096 <samples>`.
- Arena design flow (D-048): concept render first
  (`tools/blender/arena_concept_<name>.py <out.png> [samples] [width]`),
  owner approval, then the game version in `arena_builder.py`. Check the
  game version from the gameplay camera with:
  `xvfb-run -a godot --path . --rendering-method mobile --script res://tools/godot/arena_shot.gd -- res://scenes/arenas/<scene>.tscn <out.png> [distance]`

## Hero pipeline (quality pass)

```
python tools/blender/hero_builder.py --fighter kairo --moves /tmp/kairo_moves.json --out assets/characters
```
Fighters in `HEROES` (kairo, sentinel, warden) are built as layered shells:
forms → voxel remesh → smooth → decimate → weight/colour transfer. Colour is
vertex paint (`Col`); slots keep the `<ID>_<Slot>` names. Smooth skinning,
max 4 influences.

## 3D character sheets

```
python tools/blender/hero_builder.py --fighter kairo --moves /tmp/kairo_moves.json --out /tmp/concept --quality concept
python tools/art/render_character_sheet.py /tmp/concept/kairo/kairo.glb KAIRO /tmp/concept
python3 tools/art/compose_character_sheet.py /tmp/concept kairo KAIRO "The Exiled" docs/art/kairo_3d_sheet.png
```
