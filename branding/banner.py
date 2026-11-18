"""YouTube banner for 'MindBlown 3D' (2560x1440).

Deliberately different from the profile picture: deep blue / neon cyan, a 3D perspective grid,
a ringed planet and an atom instead of the brain. Text and props sit inside YouTube's safe area
(1546x423, centred), which is visible on every device; the rest is decoration for TV/desktop.
Usage: python3 banner.py [out.png] [--guides]
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 2560, 1440
SAFE = (W - 1546) // 2, (H - 423) // 2, (W + 1546) // 2, (H + 423) // 2
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viral-hooks", "fonts")
CYAN = (0, 225, 255)
ORANGE = (255, 140, 40)
HORIZON = SAFE[3] + 60


def background():
    y = np.linspace(0, 1, H)[:, None, None]
    top, mid, floor = np.array([4, 8, 32.]), np.array([10, 70, 125.]), np.array([3, 8, 26.])
    hy = HORIZON / H
    sky = top + (mid - top) * np.clip(y / hy, 0, 1) ** 2.2
    ground = mid + (floor - mid) * np.clip((y - hy) / (1 - hy) * 3, 0, 1)
    col = np.where(y < hy, sky, ground)
    img = Image.fromarray(np.repeat(col, W, axis=1).astype(np.uint8), "RGB").convert("RGBA")

    rnd = random.Random(4)
    d = ImageDraw.Draw(img)
    for _ in range(260):                                   # stars
        x, yy = rnd.uniform(0, W), rnd.uniform(0, HORIZON - 30)
        if SAFE[0] < x < SAFE[2] and SAFE[1] - 20 < yy < SAFE[3]:
            continue
        r = rnd.choice([1.5, 2, 2.5, 3.5])
        d.ellipse([x - r, yy - r, x + r, yy + r], fill=(255, 255, 255, int(rnd.uniform(80, 230))))

    # neon perspective grid on the floor (the "3D")
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    vx = W / 2
    for k in range(-24, 25):
        g.line([(vx, HORIZON), (vx + k * 260, H)], fill=CYAN + (150,), width=4)
    for k in range(1, 14):
        yy = HORIZON + (H - HORIZON) * (k / 13) ** 2.2
        g.line([(0, yy), (W, yy)], fill=CYAN + (150,), width=4)
    # fade the grid out towards the horizon
    fade = np.zeros((H, W), np.uint8)
    rows = np.clip((np.arange(H) - HORIZON) / (H - HORIZON), 0, 1) ** 0.6
    fade[:] = (rows * 255).astype(np.uint8)[:, None]
    grid.putalpha(Image.fromarray(np.minimum(np.array(grid.getchannel("A")), fade)))
    img.alpha_composite(grid.filter(ImageFilter.GaussianBlur(7)))   # glow
    img.alpha_composite(grid)
    # horizon glow line
    hg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(hg).rectangle([0, HORIZON - 3, W, HORIZON + 3], fill=CYAN + (255,))
    img.alpha_composite(hg.filter(ImageFilter.GaussianBlur(14)))
    img.alpha_composite(hg)
    return img


def planet(img, cx, cy, r):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ring = [cx - r * 1.6, cy - r * 0.38, cx + r * 1.6, cy + r * 0.38]
    d.ellipse(ring, outline=(255, 200, 120, 255), width=int(r * 0.12))           # back of ring
    # planet body with a simple light-to-dark gradient
    yy, xx = np.mgrid[0:2 * r, 0:2 * r]
    dist = np.sqrt((xx - r * 0.65) ** 2 + (yy - r * 0.6) ** 2) / (2 * r)
    c1, c2 = np.array([255, 170, 70.]), np.array([200, 40, 120.])
    body = (c1 + (c2 - c1) * np.clip(dist * 1.4, 0, 1)[..., None]).astype(np.uint8)
    mask = Image.new("L", (2 * r, 2 * r), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
    layer.paste(Image.fromarray(body, "RGB"), (int(cx - r), int(cy - r)), mask)
    d.arc(ring, 0, 180, fill=(255, 220, 150, 255), width=int(r * 0.12))          # front of ring
    glow = layer.filter(ImageFilter.GaussianBlur(30))
    img.alpha_composite(glow)
    img.alpha_composite(layer)


def atom(img, cx, cy, r):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i, ang in enumerate((15, 75, 135)):
        orb = Image.new("RGBA", (int(2.4 * r), int(2.4 * r)), (0, 0, 0, 0))
        o = ImageDraw.Draw(orb)
        c = orb.width / 2
        o.ellipse([c - r, c - r * 0.34, c + r, c + r * 0.34], outline=(235, 245, 255, 230), width=int(r * 0.045))
        e = r * 0.09                                    # electron on each orbit
        ex = c + r * math.cos(1.1 + i * 2.1)
        ey = c + r * 0.34 * math.sin(1.1 + i * 2.1)
        o.ellipse([ex - e, ey - e, ex + e, ey + e], fill=CYAN + (255,))
        orb = orb.rotate(ang, resample=Image.BICUBIC)
        layer.alpha_composite(orb, (int(cx - c), int(cy - c)))
    d = ImageDraw.Draw(layer)
    n = r * 0.13
    for dx, dy, col in ((-0.6, 0.3, (255, 80, 90)), (0.6, 0.3, (90, 140, 255)), (0, -0.45, ORANGE)):
        x, y = cx + dx * n, cy + dy * n
        d.ellipse([x - n, y - n, x + n, y + n], fill=col + (255,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(14)))
    img.alpha_composite(layer)


def fit_font(path, text, max_w, start):
    size = start
    while size > 20:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 4
    return ImageFont.truetype(path, size)


def main():
    out = next((a for a in sys.argv[1:] if not a.startswith("--")), "mindblown3d_banner.png")
    img = background()
    sx0, sy0, sx1, sy1 = SAFE
    cy = (sy0 + sy1) / 2

    atom(img, sx0 + 160, cy, 135)
    planet(img, sx1 - 175, cy + 5, 95)

    black = os.path.join(FONTS, "Montserrat-Black.otf")
    semi = os.path.join(FONTS, "Montserrat-SemiBold.otf")
    max_w = 2 * min(W / 2 - (sx0 + 330), (sx1 - 360) - W / 2)   # keep clear of atom and planet ring
    f_title = fit_font(black, "MINDBLOWN 3D", max_w, 190)
    f_tag = fit_font(semi, "MIND-BLOWING FACTS, ANIMATED IN 3D", max_w * 0.9, 50)
    tw = f_title.getlength("MINDBLOWN 3D")
    tx = W / 2 - tw / 2 + 0
    ty = cy - 30
    w_mind = f_title.getlength("MINDBLOWN ")

    # cyan glow behind the title
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((tx, ty), "MINDBLOWN 3D", font=f_title, fill=CYAN + (200,), anchor="lm",
                              stroke_width=14, stroke_fill=CYAN + (200,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(26)))
    d = ImageDraw.Draw(img)
    sw = max(6, f_title.size // 16)
    d.text((tx, ty), "MINDBLOWN", font=f_title, fill=(255, 255, 255), anchor="lm",
           stroke_width=sw, stroke_fill=(5, 15, 45))
    d.text((tx + w_mind, ty), "3D", font=f_title, fill=ORANGE, anchor="lm",
           stroke_width=sw, stroke_fill=(5, 15, 45))
    d.text((W / 2, ty + f_title.size * 0.8), "MIND-BLOWING FACTS, ANIMATED IN 3D", font=f_tag,
           fill=(170, 240, 255), anchor="mm")

    if "--guides" in sys.argv:
        d.rectangle(SAFE, outline=(0, 255, 0), width=4)
    img.convert("RGB").save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
