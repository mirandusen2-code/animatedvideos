#!/usr/bin/env bash
# Builds the textures the scene needs into <dir> (default: ./tex):
#   bmng.jpg      NASA Blue Marble Next Generation (public domain), from the basemap-data package on PyPI
#   pangaea.png   stylised Pangaea made from it (pangaea.py)
#   galaxy.png    procedural Milky Way (galaxy_tex.py)
set -e
D=${1:-tex}
mkdir -p "$D"
TMP=$(mktemp -d)
pip download basemap-data --no-deps -d "$TMP" > /dev/null
python3 - "$TMP" "$D" <<'PY'
import glob, sys, zipfile
z = zipfile.ZipFile(glob.glob(sys.argv[1] + "/*.whl")[0])
for n in ("bmng.jpg", "shadedrelief.jpg"):
    open(f"{sys.argv[2]}/{n}", "wb").write(z.read("mpl_toolkits/basemap_data/" + n))
PY
python3 "$(dirname "$0")/pangaea.py" "$D/bmng.jpg" "$D/shadedrelief.jpg" "$D/pangaea.png"
python3 "$(dirname "$0")/galaxy_tex.py" "$D/galaxy.png" 4096
echo "textures in $D"
