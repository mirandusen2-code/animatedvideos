"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_hotter", 1, [["5X", "HOTTER"], ["THAN", "THE", "SUN"]], {0: post.AMBER, 4: post.AMBER}, 1380),
    ("thumb_50000", int((T.T_50 + 0.9) * T.FPS), [["50,000°F"]], {0: post.AMBER}, 1380),
    ("thumb_thunder", int((T.T_THUNDER + 0.3) * T.FPS), [["THIS", "IS"], ["THUNDER"]], {2: post.ICE}, 1380),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
