#!/usr/bin/env bash
# Downloads the CMU Graphics Lab motion-capture clips the fighter animations
# are built from (BVH conversion by Bruce Hahne, mirrored on GitHub).
# CMU: "This data is free for all uses"; the BVH conversion adds no
# restrictions. See LICENSES.md. Clips are not stored in the repo.
#   tools/mocap/fetch_clips.sh [dir]   (default /tmp/cmu_mocap)
set -euo pipefail
DIR="${1:-/tmp/cmu_mocap}"
mkdir -p "$DIR"
BASE=https://raw.githubusercontent.com/sfd158/cmu-mocap/master/data
# 13_17 boxer (guard, jab, cross, combos)   144_13 / 144_20 martial-arts straight punches
# 144_05 front kicks                         113_08 lie down and get up
# 14_01 / 14_02 / 144_07 other performers' guards (per-fighter stances)
# 143_24 side kick   86_08 roundhouse   135_04 rising front kick (Seraphina)
for c in 13_17 144_13 144_20 144_05 113_08 14_01 14_02 144_07 143_24 86_08 135_04; do
  s=${c%%_*}
  [ -s "$DIR/$c.bvh" ] || curl -sSL --fail -o "$DIR/$c.bvh" "$BASE/$s/$c.bvh"
done
echo "clips in $DIR"
