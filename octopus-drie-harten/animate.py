"""Animatie: 'Wist je dat... een octopus drie harten heeft?'

Gebruik:  python3 animate.py [uitvoer.mp4]
Vereist: Pillow, NumPy, ffmpeg (met libx264).
"""
import math
import os
import random
import subprocess
import sys
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
SS = 2                      # supersampling
FPS = 30
DUR = 35.0
NFRAMES = int(DUR * FPS)
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

OCT = (236, 104, 128)
OCT_DARK = (186, 66, 98)
OCT_LIGHT = (255, 172, 180)
WHITE = (255, 255, 255)
YELLOW = (255, 214, 90)
RED = (255, 88, 112)
BLUE = (90, 175, 255)
STROKE = (6, 22, 48)

BEAT_F = 1.15               # hartslagen per seconde
POP_TIMES = [0.3, 11.0, 11.4, 11.8, 20.3, 21.5, 22.3, 26.3, 31.4]


# ---------------------------------------------------------------- helpers
_fonts = {}


def font(size, bold=True):
    key = (max(1, int(size * SS)), bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_B if bold else FONT_R, key[0])
    return _fonts[key]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out_back(x):
    x = clamp(x)
    c1 = 1.9
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ramp(t, a, b):
    return clamp((t - a) / (b - a))


def window(t, a, b, fade=0.4):
    return ease(ramp(t, a, a + fade)) * (1 - ease(ramp(t, b - fade, b)))


def lerp(a, b, x):
    return a + (b - a) * x


def lerpc(c1, c2, x):
    return tuple(int(lerp(a, b, x)) for a, b in zip(c1, c2))


def P(v):
    return v * SS


def circ(d, x, y, r, fill=None, outline=None, width=1):
    d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], fill=fill, outline=outline, width=width)


def draw_text(canvas, txt, x, y, size, color=WHITE, alpha=1.0, scale=1.0, bold=True, anchor="mm"):
    if alpha <= 0.01 or scale <= 0.02:
        return
    f = font(size * scale, bold)
    sw = max(2, int(size * 0.09 * scale * SS))
    tw = f.getlength(txt) + 2 * sw
    th = (size * scale * SS) * 1.4 + 2 * sw
    lw, lh = int(tw + 8), int(th + 8)
    layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((lw / 2, lh / 2), txt, font=f, fill=color + (255,),
                               anchor="mm", stroke_width=sw, stroke_fill=STROKE + (255,))
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    px = P(x) - lw / 2
    if anchor == "lm":
        px += tw / 2
    elif anchor == "rm":
        px -= tw / 2
    canvas.paste(layer, (int(px), int(P(y) - lh / 2)), layer)


def pop(t, t0, dur=0.45):
    """schaal voor een 'plop'-animatie (0 -> overshoot -> 1)."""
    return ease_out_back(ramp(t, t0, t0 + dur))


# ---------------------------------------------------------------- achtergrond
_BG = None
_RAYS = None
rng = random.Random(7)
SNOW = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(4, 14), rng.uniform(0, 6.28),
         rng.uniform(1, 2.6), rng.randint(40, 120)) for _ in range(90)]
BUBBLES = [(rng.uniform(20, W - 20), rng.uniform(35, 95), rng.uniform(0, 2000), rng.uniform(3, 10),
            rng.uniform(0, 6.28)) for _ in range(26)]


def init_bg():
    global _BG, _RAYS
    if _BG is not None:
        return
    hs, ws = H * SS, W * SS
    y = np.linspace(0, 1, hs).reshape(hs, 1, 1)
    top = np.array([16, 78, 132], float)
    bot = np.array([3, 12, 36], float)
    arr = top * (1 - y) ** 1.2 + bot * (1 - (1 - y) ** 1.2)
    arr = np.repeat(arr, ws, axis=1)
    yy, xx = np.mgrid[0:hs, 0:ws]
    r = np.sqrt(((xx - ws / 2) / ws) ** 2 + ((yy - hs * 0.35) / hs) ** 2)
    arr *= np.clip(1.15 - r * 0.9, 0.55, 1.0)[..., None]
    _BG = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")

    extra = 300
    rays = Image.new("RGBA", ((W + extra) * SS, hs), (0, 0, 0, 0))
    d = ImageDraw.Draw(rays)
    for k in range(7):
        x = (extra / 2 + 80 + k * 180 + (k % 2) * 40)
        wtop = 18 + (k % 3) * 10
        d.polygon([(P(x - wtop), 0), (P(x + wtop), 0), (P(x + 160 + wtop * 3), hs), (P(x + 40 - wtop), hs)],
                  fill=(190, 230, 255, 26 + (k % 3) * 8))
    rays = rays.filter(ImageFilter.GaussianBlur(28 * SS))
    _RAYS = rays


def background(t):
    init_bg()
    c = _BG.copy()
    off = int(P(150 + 60 * math.sin(t * 0.35)))
    rays = _RAYS.crop((off, 0, off + W * SS, H * SS))
    c.paste(rays, (0, 0), rays)
    d = ImageDraw.Draw(c, "RGBA")
    for x0, y0, sp, ph, r, a in SNOW:
        y = (y0 + t * sp) % (H + 10) - 5
        x = x0 + 10 * math.sin(t * 0.6 + ph)
        circ(d, x, y, r * 0.6, fill=(210, 230, 255, a))
    for x0, sp, off2, r, ph in BUBBLES:
        y = H + 30 - ((t * sp + off2) % (H + 80))
        x = x0 + 9 * math.sin(t * 2.0 + ph)
        circ(d, x, y, r, outline=(200, 235, 255, 150), width=max(2, int(1.2 * SS)))
        circ(d, x - r * 0.35, y - r * 0.35, r * 0.25, fill=(240, 250, 255, 170))
    return c, d


# ---------------------------------------------------------------- octopus
KEYS = [  # t, cx, cy, schaal, mantel-alpha, spreiding
    (0.0, 640, 960, 1.0, 1.0, 0.7),
    (4.0, 640, 960, 1.0, 1.0, 0.7),
    (6.2, 640, 430, 1.0, 1.0, 1.0),
    (10.0, 640, 430, 1.0, 1.0, 1.0),
    (11.0, 640, 400, 1.3, 0.33, 1.0),
    (19.0, 640, 400, 1.3, 0.33, 1.0),
    (20.0, 430, 425, 1.15, 0.33, 1.0),
    (26.0, 430, 425, 1.15, 0.33, 1.0),
    (27.0, 640, 480, 1.1, 0.33, 1.0),
    (27.6, 640, 480, 1.1, 0.33, 1.0),
    (28.6, 640, 450, 1.1, 0.33, 0.45),
    (31.0, 640, 420, 1.1, 0.33, 0.45),
    (32.0, 640, 455, 0.95, 1.0, 1.0),
    (DUR, 640, 455, 0.95, 1.0, 1.0),
]


def octo_state(t):
    for (t0, *a), (t1, *b) in zip(KEYS, KEYS[1:]):
        if t0 <= t <= t1:
            x = ease((t - t0) / (t1 - t0)) if t1 > t0 else 1
            cx, cy, sc, ma, sp = [lerp(p, q, x) for p, q in zip(a, b)]
            break
    swim = window(t, 27.6, 31.0, 0.6)
    cy += 6 * math.sin(t * 1.6) + swim * 16 * math.sin(t * 5.0)
    sp *= 1 + swim * 0.45 * math.sin(t * 5.0 + 1.2)
    return cx, cy, sc, ma, sp, swim


def tentacle(cx, cy, sc, i, t, spread, swim, n=30):
    k = i - 3.5
    sign = 1 if k > 0 else -1
    bx, by = cx + k * 21 * sc, cy + 38 * sc
    ang = math.radians(90 - k * 19 * spread)
    step = 235 * sc / n
    ph = i * 1.37
    x, y = bx, by
    pts = [(x, y, 18 * sc)]
    for j in range(1, n + 1):
        s = j / n
        sway = (0.85 + swim * 0.4) * s * math.sin(t * (2.1 + swim * 2) - s * 4.2 + ph)
        a = ang + sway - sign * 1.3 * s * s * (1 - 0.7 * swim)
        x += math.cos(a) * step
        y += math.sin(a) * step
        pts.append((x, y, (16 * (1 - s) ** 0.9 + 2.8) * sc))
    return pts


def heart_poly(x, y, size):
    pts = []
    for k in range(64):
        a = 2 * math.pi * k / 64
        hx = 16 * math.sin(a) ** 3
        hy = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) - 2.5
        pts.append((P(x + hx * size / 16), P(y + hy * size / 16)))
    return pts


def beat(t):
    ph = (t * BEAT_F) % 1.0
    return (math.exp(-(ph / 0.06) ** 2) + 0.65 * math.exp(-((ph - 0.2) / 0.06) ** 2)
            + math.exp(-((ph - 1) / 0.06) ** 2))


def draw_heart(d, x, y, size, color, alpha, glow=True):
    if alpha <= 0.01 or size <= 0.5:
        return
    a = int(255 * alpha)
    if glow:
        for g in range(4, 0, -1):
            circ(d, x, y, size * (0.9 + g * 0.25), fill=color + (int(18 * alpha),))
    d.polygon(heart_poly(x, y, size), fill=color + (a,))
    hl = lerpc(color, WHITE, 0.55)
    d.ellipse([P(x - size * 0.62), P(y - size * 0.62), P(x - size * 0.3), P(y - size * 0.38)], fill=hl + (int(a * 0.8),))


def draw_octopus(canvas, d, t):
    cx, cy, sc, ma, sp, swim = octo_state(t)
    if cy - 220 * sc > H:
        return None
    tents = [tentacle(cx, cy, sc, i, t, sp, swim) for i in range(8)]
    # tentakels: achterste (donker) eerst
    for order in (0, 1):
        for i in range(order, 8, 2):
            col = OCT_DARK if order == 0 else OCT
            for x, y, r in tents[i]:
                circ(d, x, y, r, fill=col)
            if order == 1:
                for j, (x, y, r) in enumerate(tents[i][3:-2]):
                    if j % 3 == 0:
                        circ(d, x, y + r * 0.35, r * 0.33, fill=OCT_LIGHT)

    # lijf/mantel op aparte laag (kan doorzichtig worden)
    ox, oy = P(cx - 140 * sc), P(cy - 210 * sc)
    lw, lh = int(P(280 * sc)), int(P(300 * sc))
    body = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    bd = ImageDraw.Draw(body, "RGBA")

    def le(x0, y0, x1, y1, **kw):
        bd.ellipse([P(x0) - ox, P(y0) - oy, P(x1) - ox, P(y1) - oy], **kw)

    my = cy - 75 * sc
    le(cx - 102 * sc, my - 122 * sc, cx + 102 * sc, my + 112 * sc, fill=OCT + (255,))
    le(cx - 88 * sc, cy - 50 * sc, cx + 88 * sc, cy + 62 * sc, fill=OCT + (255,))
    for sx, sy, sr in [(-50, -150, 13), (40, -165, 9), (62, -110, 15), (-70, -95, 8), (10, -125, 7), (-20, -180, 6)]:
        le(cx + (sx - sr) * sc, cy + (sy - sr * 0.8) * sc, cx + (sx + sr) * sc, cy + (sy + sr * 0.8) * sc,
           fill=OCT_DARK + (200,))
    le(cx - 70 * sc, my - 100 * sc, cx - 25 * sc, my - 40 * sc, fill=(255, 220, 225, 90))
    if ma < 0.999:
        body.putalpha(body.getchannel("A").point(lambda v: int(v * ma)))
    canvas.paste(body, (int(ox), int(oy)), body)
    if ma < 0.999:  # contour blijft zichtbaar
        a = int(255 * (1 - ma))
        lwid = max(2, int(3 * sc * SS))
        d.arc([P(cx - 102 * sc), P(my - 122 * sc), P(cx + 102 * sc), P(my + 112 * sc)], 150, 390,
              fill=OCT_LIGHT + (a,), width=lwid)
        d.arc([P(cx - 88 * sc), P(cy - 50 * sc), P(cx + 88 * sc), P(cy + 62 * sc)], -10, 190,
              fill=OCT_LIGHT + (a,), width=lwid)

    # harten
    inside = clamp((1 - ma) / 0.6)
    hearts = None
    if inside > 0.01:
        bluish = ease(ramp(t, 20.3, 21.2))
        stop = ease(ramp(t, 28.0, 28.8))
        b = beat(t)
        col = lerpc(RED, (70, 130, 255), bluish)
        hx, hy = cx, cy - 85 * sc
        gl, gr = (cx - 62 * sc, cy - 45 * sc), (cx + 62 * sc, cy - 45 * sc)
        # vaten
        vcol = lerpc((255, 120, 140), (110, 180, 255), bluish) + (int(150 * inside * ease(ramp(t, 12.2, 13))),)
        vw = max(2, int(4 * sc * SS))
        for gx, gy in (gl, gr):
            d.line([P(hx), P(hy), P(gx), P(gy)], fill=vcol, width=vw)
        for i in (1, 3, 4, 6):
            bx = cx + (i - 3.5) * 21 * sc
            d.line([P(hx), P(hy), P(bx), P(cy + 38 * sc)], fill=vcol, width=vw)
        s1 = pop(t, 11.0) * inside
        s2 = pop(t, 11.4) * inside
        s3 = pop(t, 11.8) * inside
        main_col = lerpc(col, (130, 130, 150), stop)
        draw_heart(d, gl[0], gl[1], 24 * sc * s1 * (1 + 0.15 * b), col, inside)
        draw_heart(d, gr[0], gr[1], 24 * sc * s2 * (1 + 0.15 * b), col, inside)
        draw_heart(d, hx, hy, 40 * sc * s3 * (1 + 0.15 * b * (1 - stop)), main_col, inside, glow=stop < 0.5)
        hearts = dict(main=(hx, hy), gl=gl, gr=gr, sc=sc)

    # ogen
    ey = cy + 2 * sc
    blink = 1.0
    bt = (t + 0.7) % 3.9
    if bt < 0.16:
        blink = abs(bt - 0.08) / 0.08
    look = 4 * math.sin(t * 0.7) * sc
    for sx in (-38, 38):
        ex = cx + sx * sc
        d.ellipse([P(ex - 21 * sc), P(ey - 19 * sc * blink - 1), P(ex + 21 * sc), P(ey + 19 * sc * blink + 1)],
                  fill=(252, 247, 238))
        if blink > 0.3:
            ph = 5 * sc * blink
            d.rounded_rectangle([P(ex - 11 * sc + look), P(ey - ph), P(ex + 11 * sc + look), P(ey + ph)],
                                radius=P(ph * 0.9), fill=(22, 18, 34))
            circ(d, ex - 6 * sc + look, ey - 7 * sc, 3.5 * sc, fill=WHITE)
        d.arc([P(ex - 24 * sc), P(ey - 30 * sc), P(ex + 24 * sc), P(ey + 4 * sc)], 205, 335,
              fill=OCT_DARK, width=max(2, int(4 * sc * SS)))
    for sx in (-62, 62):
        d.ellipse([P(cx + sx * sc - 12 * sc), P(ey + 16 * sc), P(cx + sx * sc + 12 * sc), P(ey + 26 * sc)],
                  fill=(255, 150, 170, 150))
    d.arc([P(cx - 13 * sc), P(ey + 14 * sc), P(cx + 13 * sc), P(ey + 34 * sc)], 20, 160,
          fill=(120, 30, 60), width=max(2, int(3 * sc * SS)))

    # blauw bloed door tentakels
    flow = window(t, 20.6, 31.2, 0.6) * inside
    if flow > 0.01:
        for i, pts in enumerate(tents):
            for m in range(4):
                s = (t * 0.45 + m / 4 + i * 0.13) % 1.0
                x, y, r = pts[int(s * (len(pts) - 1))]
                circ(d, x, y, r * 0.75 + 3, fill=BLUE + (int(70 * flow),))
                circ(d, x, y, r * 0.35 + 1.5, fill=(190, 225, 255, int(230 * flow)))
    return hearts


def drop(d, x, y, r, color):
    pts = [(P(x), P(y - 2 * r))]
    for k in range(41):
        th = math.radians(-30 + 240 * k / 40)
        pts.append((P(x + r * math.cos(th)), P(y + r * math.sin(th))))
    d.polygon(pts, fill=color)
    d.ellipse([P(x - r * 0.6), P(y - r * 0.55), P(x - r * 0.25), P(y - r * 0.05)],
              fill=lerpc(color, WHITE, 0.5) + (200,))


def line_label(d, x0, y0, x1, y1, a):
    if a > 0.01:
        d.line([P(x0), P(y0), P(x1), P(y1)], fill=(255, 255, 255, int(200 * a)), width=P(2))
        circ(d, x0, y0, 4, fill=(255, 255, 255, int(255 * a)))


# ---------------------------------------------------------------- frame
def render(fi):
    t = fi / FPS
    c, d = background(t)
    hearts = draw_octopus(c, d, t)

    # Scène 1: intro
    a = window(t, 0.0, 4.0, 0.4)
    draw_text(c, "Wist je dat...?", 640, 300, 88, YELLOW, a, pop(t, 0.3))
    draw_text(c, "een random weetje uit de diepzee", 640, 400, 34, WHITE, a * ease(ramp(t, 0.9, 1.4)), bold=False)

    # Scène 2: kennismaking
    draw_text(c, "Dit is een octopus.", 640, 85, 52, WHITE, window(t, 5.0, 10.0), pop(t, 5.0))
    draw_text(c, "Hij verbergt een geheim...", 640, 150, 36, WHITE, window(t, 7.0, 10.0), bold=False)

    # Scène 3: drie harten
    a3 = window(t, 10.3, 19.0)
    draw_text(c, "Een octopus heeft", 640, 42, 34, WHITE, a3)
    draw_text(c, "3 HARTEN!", 640, 104, 72, RED, a3, pop(t, 11.0))
    if hearts and t < 19.5:
        sc = hearts["sc"]
        la = window(t, 13.0, 19.0)
        gx, gy = hearts["gl"]
        line_label(d, gx - 18 * sc, gy, 360, 365, la)
        draw_text(c, "kieuwhart", 350, 365, 32, WHITE, la, anchor="rm")
        draw_text(c, "pompt bloed door de kieuwen", 350, 402, 20, WHITE, la, bold=False, anchor="rm")
        gx, gy = hearts["gr"]
        line_label(d, gx + 18 * sc, gy, 920, 410, la)
        draw_text(c, "kieuwhart", 930, 410, 32, WHITE, la, anchor="lm")
        draw_text(c, "pompt bloed door de kieuwen", 930, 447, 20, WHITE, la, bold=False, anchor="lm")
        lb = window(t, 14.5, 19.0)
        hx, hy = hearts["main"]
        line_label(d, hx + 30 * sc, hy - 10, 900, 240, lb)
        draw_text(c, "hoofdhart", 910, 240, 36, YELLOW, lb, anchor="lm")
        draw_text(c, "pompt bloed door het lichaam", 910, 279, 20, WHITE, lb, bold=False, anchor="lm")
    draw_text(c, "2 voor de kieuwen, 1 voor de rest van het lichaam", 640, 670, 30, WHITE, window(t, 16.3, 19.0))

    # Scène 4: blauw bloed
    a4 = window(t, 19.3, 26.0)
    draw_text(c, "En zijn bloed is...", 640, 50, 38, WHITE, a4)
    draw_text(c, "BLAUW!", 640, 118, 78, BLUE, a4, pop(t, 20.3))
    bob = 6 * math.sin(t * 2)
    for t0, x, col, name, sub, el in [(21.5, 860, (220, 40, 60), "Mens", "ijzer (Fe)", "Fe"),
                                      (22.3, 1100, (50, 110, 245), "Octopus", "koper (Cu)", "Cu")]:
        s = pop(t, t0) * a4
        if s > 0.02:
            y = 345 + bob * (1 if el == "Fe" else -1)
            drop(d, x, y, 48 * s, col)
            draw_text(c, el, x, y + 6, 34, WHITE, a4, s)
            la = a4 * ease(ramp(t, t0 + 0.2, t0 + 0.6))
            draw_text(c, name, x, 440, 32, WHITE, la)
            draw_text(c, sub, x, 478, 24, YELLOW if el == "Cu" else WHITE, la, bold=False)
    a4b = window(t, 23.5, 26.0)
    draw_text(c, "Het eiwit hemocyanine gebruikt koper", 640, 628, 32, WHITE, a4b)
    draw_text(c, "in plaats van ijzer, daardoor is het blauw", 640, 672, 26, WHITE, a4b, bold=False)

    # Scène 5: bonus
    a5 = window(t, 26.2, 31.0)
    draw_text(c, "BONUS", 640, 45, 34, YELLOW, a5, pop(t, 26.3))
    draw_text(c, "Als een octopus zwemt,", 640, 100, 40, WHITE, a5 * ease(ramp(t, 26.6, 27.0)))
    draw_text(c, "stopt zijn hoofdhart met kloppen!", 640, 150, 40, RED, a5 * ease(ramp(t, 27.0, 27.4)))
    if hearts and 28.0 < t < 31.3:
        hx, hy = hearts["main"]
        pa = window(t, 28.3, 31.0)
        line_label(d, hx + 30 * hearts["sc"], hy, hx + 150, hy - 25, pa)
        draw_text(c, "PAUZE", hx + 160, hy - 25, 28, YELLOW, pa, anchor="lm")
    draw_text(c, "Daarom kruipt hij liever dan te zwemmen.", 640, 670, 32, WHITE, window(t, 29.0, 31.0))

    # Scène 6: outro
    a6 = window(t, 31.2, DUR + 1)
    draw_text(c, "Wist jij dit al?", 640, 110, 66, YELLOW, a6, pop(t, 31.4))
    draw_text(c, "3 harten  •  blauw bloed  •  koper i.p.v. ijzer", 640, 655, 30, WHITE,
              a6 * ease(ramp(t, 32.2, 32.7)))

    out = c.reduce(SS)
    fade = ease(ramp(t, 0, 0.5)) * (1 - ease(ramp(t, DUR - 0.7, DUR)))
    if fade < 1:
        out = Image.eval(out, lambda v: int(v * fade))
    return out.tobytes()


# ---------------------------------------------------------------- audio
def make_audio(path):
    sr = 44100
    n = int(DUR * sr)
    tt = np.arange(n) / sr
    rnd = np.random.default_rng(3)
    au = np.zeros(n)
    for f, a in [(55, 0.10), (82.4, 0.06), (110, 0.045), (164.8, 0.025), (220, 0.012)]:
        au += a * np.sin(2 * np.pi * f * tt + 0.4 * np.sin(2 * np.pi * 0.11 * tt)) * \
            (0.7 + 0.3 * np.sin(2 * np.pi * 0.07 * tt + f))
    noise = rnd.standard_normal(n)
    for _ in range(3):
        noise = np.convolve(noise, np.ones(60) / 60, mode="same")
    au += noise * 0.35 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.15 * tt))

    def add(t0, sig):
        i = int(t0 * sr)
        if 0 <= i < n:
            j = min(n, i + len(sig))
            au[i:j] += sig[: j - i]

    # belletjes
    t0 = 0.4
    while t0 < DUR:
        d = rnd.uniform(0.03, 0.06)
        st = np.arange(int(d * sr)) / sr
        f0 = rnd.uniform(500, 900)
        f = f0 * (1 + 2.5 * st / d)
        add(t0, 0.05 * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.sin(np.pi * st / d))
        t0 += rnd.uniform(0.25, 1.4)
    # pops
    for tp in POP_TIMES:
        d = 0.09
        st = np.arange(int(d * sr)) / sr
        f = 280 + 900 * (st / d) ** 0.6
        add(tp, 0.28 * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-st * 28))
    # hartslag
    k = math.ceil(11.0 * BEAT_F)
    while k / BEAT_F < 31.2:
        tb = k / BEAT_F
        vol = 0.55 if tb < 28.0 else 0.22
        for off, v in ((0.0, 1.0), (0.2 / BEAT_F, 0.65)):
            st = np.arange(int(0.18 * sr)) / sr
            sig = (np.sin(2 * np.pi * 52 * st) + 0.5 * np.sin(2 * np.pi * 85 * st)) * \
                np.exp(-st * 22) * (1 - np.exp(-st * 400))
            add(tb + off, vol * v * sig)
        k += 1
    env = np.clip(tt / 0.8, 0, 1) * np.clip((DUR - tt) / 1.0, 0, 1)
    au *= env
    au = au / np.max(np.abs(au)) * 0.85
    pcm = (au * 32767).astype(np.int16)
    stereo = np.stack([pcm, pcm], axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(stereo.tobytes())


# ---------------------------------------------------------------- main
def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "octopus-drie-harten.mp4")
    wav = out + ".wav"
    make_audio(wav)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, frame in enumerate(pool.imap(render, range(NFRAMES), chunksize=4)):
            ff.stdin.write(frame)
            if i % 60 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    os.remove(wav)
    print("klaar:", out)


if __name__ == "__main__":
    main()
