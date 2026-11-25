"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_impact", 6, [["NASA HIT"], ["AN ASTEROID"]], {1: post.HOT}, 1340),
    ("thumb_no_crater", int((T.T_SAND + 0.3) * T.FPS), [["NO"], ["CRATER?!"]], {1: post.HOT}, 1360),
    ("thumb_last_view", T.NFRAMES - 12, [["DART'S"], ["LAST PHOTO"]], {1: post.AMBER}, 1360),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
