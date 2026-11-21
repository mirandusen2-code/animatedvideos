"""Three thumbnail candidates (1080x1920) from the most striking frames, with a short title in the safe zone.
Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
f_earth = int(1.4 * T.FPS)                               # Earth, beacon, streaking stars
f_gal = int((T.SHOTS[3][1] - 0.3) * T.FPS)               # the whole Milky Way with "you are here"
f_pang = int((T.T_DINO + 0.5) * T.FPS)                   # Pangaea
for name, f, lines, colors, y in [
    ("thumb_speed", f_earth, [["500,000"], ["MPH"]], {0: post.AMBER}, 560),
    ("thumb_galaxy", f_gal, [["ONE", "LAP", "="], ["230", "MILLION"], ["YEARS"]], {3: post.AMBER, 4: post.AMBER}, 1380),
    ("thumb_pangaea", f_pang, [["LAST", "TIME"], ["WE", "WERE", "HERE"]], {4: post.AMBER}, 1380),
]:
    t = f / T.FPS
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), t)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
