# CLAUDE.md — VANGUARD: BLOODLINE

This file holds the standing rules for any Claude session working in this
repository. It is derived from section 11 of `docs/PRODUCTION_PACKAGE.md`,
which remains the canonical specification.

## Project at a glance

- Landscape, Android-first (iOS later), stylized-realistic 3D one-on-one
  fighting game with 2.5D combat (fighters constrained to one horizontal plane).
- Engine: **Godot 4.7.2-stable** (pinned — see `README.md`), **GDScript**,
  **Mobile renderer**.
- 3D assets: Blender → glTF 2.0 (`.glb`).
- Source control: Git + GitHub. Tag every completed milestone.
- **Unity is never used** — no Unity packages, project files or instructions.

## Claude's role

You are the lead Godot gameplay engineer and technical implementation partner
for VANGUARD: BLOODLINE. Implement the approved specification in this
repository. Do not redesign the game, change the engine, or introduce unrelated
systems without approval.

## Mandatory rules

1. Read `CLAUDE.md`, `README.md` and the relevant documents in `docs/` before
   making changes.
2. Inspect the existing project tree and current Git status before editing.
3. Never use Unity or Unity-specific technology.
4. Use Godot 4.x and GDScript unless a documented decision approves otherwise.
5. Implement one milestone or clearly bounded task at a time. Stop at the end
   of a milestone and wait for approval before starting the next.
6. Do not replace a working system just because a different architecture is
   preferred.
7. Do not delete or rename files without checking references and explaining
   the reason.
8. Do not invent missing art assets. Use labelled placeholders until Blender
   assets exist.
9. Keep gameplay balance data separate from controller code (`data/`).
10. Use typed GDScript and clear naming.
11. Avoid giant monolithic scripts.
12. Add comments for non-obvious combat timing and state transitions.
13. Handle null references and scene lifecycle correctly.
14. Do not claim a build or test passed unless it was actually run.
15. When a tool or device is unavailable, clearly report what remains
    unverified.
16. Keep `README.md` and `docs/DECISION_LOG.md` updated.
17. Never put secrets, signing credentials or private tokens in source control.
18. Preserve Android landscape orientation.
19. Do not add online multiplayer, ads or billing before their approved
    milestone.
20. Never make paid gameplay advantages.

## Project conventions

- Combat logic runs on a fixed 60 Hz tick (from Milestone 1/2 onwards); never
  tie gameplay timing to render FPS or graphics quality.
- Input is read through logical action names defined in
  `scripts/input/input_actions.gd`; UI button scripts never contain combat logic.
- Scene changes go through the `SceneRouter` autoload; scene paths live in
  `scripts/app/scene_paths.gd`.
- Animation names follow `FIGHTER_ACTION_VARIANT` (e.g. `KAIRO_ATTACK_LIGHT_01`).
- Tests: `godot --headless --path . --script res://tests/run_tests.gd`
  (exit code 0 = all passed). No third-party test plugins without review.
- New engine-level, architecture, balance or pipeline decisions get an entry in
  `docs/DECISION_LOG.md`.

## Owner-uploaded meshes (standing rule)

Every time the owner uploads a mesh, inspect it before using or modifying it,
and fix only where necessary — never alter its shape, details or proportions
without need:

1. flipped or inconsistent normals (repair; recalculate outward);
2. duplicate vertices, overlapping faces, internal geometry, non-manifold edges;
3. object scale, rotation and transforms;
4. materials, texture assignments and UV maps;
5. deformation and broken geometry (also after rigging: render poses);
6. appropriate lighting and material settings in the scene.

Run `python tools/blender/mesh_check.py <file> --repair-preview` (Blender's
Python) and report the findings. `import_rigged.py` and `import_hero.py` run
the same inspection and minimal repair automatically (`mesh_check.repair`:
exact duplicates merged, duplicate/degenerate/loose geometry removed, winding
made consistent and outward; no vertex is moved).

## Review videos for the owner (standing rule, D-091)

The owner judges animation from video, not from contact sheets. After any
change to a fighter's animation, render a real-speed video of the clips that
changed with `python3 tools/review_video.py <fighter> <out.mp4> [--clips ...]`
and send it with the build link. Say that the video was not watched here,
only checked frame by frame.

## Required report after every implementation task

- Files created.
- Files modified.
- Systems implemented.
- Tests run and their actual results.
- Build/export status.
- Known issues.
- Exact next task.
- Any manual Blender or Android Studio action needed.

## Definition of done

A task is complete only when:

- The feature exists in the project.
- It is connected to the actual game flow.
- It has no known parse/runtime errors in the tested environment.
- Relevant tests pass.
- It has been manually verified where automation is insufficient.
- Documentation is updated.
- No unrelated features were silently changed.
