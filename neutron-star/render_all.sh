#!/usr/bin/env bash
# Render every frame in batches of 100, each in a fresh Blender process (skips frames that exist).
# Usage: ./render_all.sh <frames_dir> [extra scene.py args...]
set -e
OUT=$1; shift
cd "$(dirname "$0")"
N=$(python3 -c "import timeline as T; print(T.NFRAMES)")
for start in $(seq 0 100 $((N - 1))); do
  python3 scene.py "$OUT" --range $start $((start + 99)) "$@" > /dev/null 2>&1
  echo "batch $start done ($(ls "$OUT"/f_*.png | wc -l)/$N)"
done
echo "ALL DONE"
