#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p frames qa
python3 - <<'PY'
from pathlib import Path
from PIL import Image
for p in Path('frames').glob('[0-9][0-9][0-9][0-9][0-9].png'):
 try:
  with Image.open(p) as im: im.load();assert im.width==1080
 except (OSError,AssertionError):p.unlink()
PY
n=$(python3 -c 'from timeline import NFRAMES;print(NFRAMES)')
for ((start=0; start<n; start+=40)); do
 python3 scene.py "$start" "$((start+40))"
done
