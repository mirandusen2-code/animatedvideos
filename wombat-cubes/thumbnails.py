"""Three thumbnail candidates (1080x1920) from the most striking frames, with a short title in the safe zone.
Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
f_cube = int((T.T_CORNERS + 0.35) * T.FPS)          # macro cube with glowing edges and corners
f_gut = int((T.SHOTS[4][1] - 0.2) * T.FPS)          # square poop leaving the x-ray gut
f_rock = int((T.T_ROUND + 0.1) * T.FPS)             # cubes on the rock + the round one
for name, f, lines, colors, y in [
    ("thumb_cube", f_cube, [["WOMBATS"], ["POOP", "CUBES"]], {2: post.AMBER}, 1250),
    ("thumb_xray", f_gut, [["HOW", "POOP"], ["GETS", "SQUARE"]], {3: post.AMBER}, 1250),
    ("thumb_why", f_rock, [["WHY", "CUBES?"]], {1: post.AMBER}, 1250),
]:
    t = f / T.FPS
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), t)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
