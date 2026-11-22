"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_leaving", 20, [["THE", "MOON", "IS"], ["LEAVING", "US"]], {3: post.AMBER, 4: post.AMBER}, 1000),
    ("thumb_young", int((T.T_SKY + 0.2) * T.FPS), [["WHEN", "THE", "MOON"], ["FILLED", "THE", "SKY"]], {3: post.AMBER, 5: post.AMBER}, 1400),
    ("thumb_eclipse", int((T.SHOTS[5][1] - 0.3) * T.FPS), [["NO", "MORE"], ["ECLIPSES"]], {2: post.AMBER}, 1350),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
