"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_192_lasers", 4, [["192 LASERS"], ["VS 1 PELLET"]], {0: post.HOT}, 1340),
    ("thumb_star_on_earth", int((T.T_STAR[0] + 0.35) * T.FPS), [["A STAR"], ["ON EARTH"]], {1: post.HOT}, 1360),
    ("thumb_4x_energy", int((T.T_4X[0] + 0.4) * T.FPS), [["4× MORE"], ["ENERGY"]], {0: post.HOT}, 1360),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
