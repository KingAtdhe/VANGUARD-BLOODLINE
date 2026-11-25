#!/usr/bin/env bash
# Rebuild one fighter's model with its animations and install it in the project.
#
#   bash build_fighter.sh <fighter_id>            e.g. kairo
#   STANCE_ONLY=1 bash build_fighter.sh kairo     idle only, not installed
#   KAIRO_MOCAP_RIFT=1 bash build_fighter.sh kairo   any build switch passes through
#
# Does, in order:
#   1. exports the move timings from the game data (so animation timing is
#      always the real frame data),
#   2. builds with KEYED_DEBUG=1 and GLITCH_SCAN=1 and keeps the log
#      ($WORK/build_<id>.log, read by motion_report.py),
#   3. keeps the model being replaced as $WORK/prev_<id>.glb,
#   4. installs the new .glb and deletes Godot's cached import of it (a stale
#      cache can leave the old model in place, see docs/HANDOFF.md),
#   5. re-imports, prints the pose checker's findings, and lists the flags
#      (pops, pose faults) that are new against the previous build's log.
#
# WORK (default /root/work) and MOCAP (default /root/tools/cmu_mocap) can be
# set in the environment. Run from anywhere inside the repository.
set -euo pipefail
ID="${1:?usage: build_fighter.sh <fighter_id>}"
WORK="${WORK:-/root/work}"
MOCAP="${MOCAP:-/root/tools/cmu_mocap}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

for tool in godot python3; do
  command -v "$tool" >/dev/null || { echo "missing: $tool (see references/checks.md, Machine)"; exit 2; }
done
python3 -c "import bpy" 2>/dev/null || { echo "missing: python module bpy (pip install bpy numpy pillow)"; exit 2; }
SRC="assets/characters/_source/$ID/$ID.fbx"
[ -f "$SRC" ] || { echo "no source model: $SRC"; exit 2; }
mkdir -p "$WORK/out"
ls "$MOCAP"/*.bvh >/dev/null 2>&1 || bash tools/mocap/fetch_clips.sh "$MOCAP"

echo "== 1/5 move timings"
godot --headless --path . --script res://tools/blender/export_move_timing.gd -- "$WORK/moves_$ID.json" "$ID" 2>&1 \
  | grep -vE "^(Godot Engine|$)" || true
[ -s "$WORK/moves_$ID.json" ] || { echo "timing export failed (has the project been imported? godot --headless --path . --import)"; exit 1; }

echo "== 2/5 build (half a minute to a few minutes; log: $WORK/build_$ID.log)"
[ -n "${STANCE_ONLY:-}" ] || { [ -f "$WORK/build_$ID.log" ] && cp -f "$WORK/build_$ID.log" "$WORK/build_$ID.prev.log"; } || true
set +e
KEYED_DEBUG=1 GLITCH_SCAN=1 python3 tools/blender/import_rigged.py --src "$SRC" --fighter "$ID" \
  --moves "$WORK/moves_$ID.json" --out "$WORK/out" --mocap-dir "$MOCAP" > "$WORK/build_$ID.log" 2>&1
RC=$?
set -e
if [ $RC -ne 0 ] || [ ! -s "$WORK/out/$ID/$ID.glb" ]; then
  echo "BUILD FAILED (exit $RC). Last lines:"; tail -25 "$WORK/build_$ID.log"; exit 1
fi
echo "   pops reported: $(grep -c '^GLITCH' "$WORK/build_$ID.log" || true)"

if [ -n "${STANCE_ONLY:-}" ]; then
  echo "STANCE_ONLY build: not installed. Look at it with"
  echo "  xvfb-run -a godot --path . --rendering-driver opengl3 --script res://tools/godot/pose_views.gd -- $ID /root/work/stance.png IDLE_A 1 480 $WORK/out/$ID/$ID.glb"
  exit 0
fi

echo "== 3/5 keep the previous model: $WORK/prev_$ID.glb"
cp -f "assets/characters/$ID/$ID.glb" "$WORK/prev_$ID.glb"

echo "== 4/5 install and clear the stale import"
cp -f "$WORK/out/$ID/$ID.glb" "assets/characters/$ID/$ID.glb"
rm -f .godot/imported/"$ID".glb-*

echo "== 5/5 re-import"
godot --headless --path . --import > "$WORK/import_$ID.log" 2>&1 || true
ls .godot/imported/"$ID".glb-* >/dev/null 2>&1 || { echo "re-import did not produce the model; see $WORK/import_$ID.log"; exit 1; }

if [ -f "$WORK/out/$ID/pose_report.json" ]; then
  echo "== pose checker"
  python3 tools/blender/pose_check.py "$WORK/out/$ID/pose_report.json" 2>/dev/null | tail -25 || true
fi
if [ -f "$WORK/build_$ID.prev.log" ]; then
  echo "== flags against the build before this one"
  python3 "$HERE/motion_report.py" "$WORK/build_$ID.log" --diff "$WORK/build_$ID.prev.log" | head -40
fi
echo "done. Next: motion_report.py $WORK/build_$ID.log <CLIP>, tools/godot/body_angles.gd, frame_strip.py"
