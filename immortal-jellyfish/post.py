"""Post-production for the immortal jellyfish Short: grade + bloom + grain, captions & counters in the Shorts
safe zone, original music + sound effects + processed voice, loudness -14 LUFS, H.264 1080x1920.

Usage: python3 post.py <frames_dir> <out.mp4> [--preview f1,f2,...]   (preview writes PNGs only)
Also writes <out>.srt (subtitles).
"""
import json
import math
import os
import re
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeline as T  # noqa: E402
from script import LINES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
FONT_DIR = os.path.join(HERE, "..", "viral-hooks", "fonts")
AMBER = (255, 181, 71)
ICE = (127, 216, 255)
WHITE = (255, 255, 255)
INK = (8, 12, 24)
# Shorts safe zone: top 250 px (search bar), bottom 420 px (title/channel), right ~200 px (buttons)
# Measured on a real phone screenshot of a published Short (YouTube crops ~46 px per side on tall phones):
# top ~260 px = status/search icons, right x>880 (y 1050-1760) = like/comment/share, bottom from y~1580 =
# channel name + title. Everything essential stays inside this column:
SAFE = (92, 300, 860, 1540)
CX = (SAFE[0] + SAFE[2]) / 2                         # 476: centre of the safe column
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = T.L
_f = {}


def font(size, kind="Black"):
    k = (int(size), kind)
    if k not in _f:
        _f[k] = ImageFont.truetype(os.path.join(FONT_DIR, f"Montserrat-{kind}.otf"), k[0])
    return _f[k]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def back_out(x):
    x = clamp(x)
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def window(t, a, b, fade=0.18):
    return clamp((t - a) / fade) * clamp((b - t) / fade)


# ---------------------------------------------------------------- text helpers
def text_block(img, lines, cx, cy, size, alpha=1.0, scale=1.0, colors=None, kind="Black", maxw=None):
    """Centred multi-line text with outline + soft shadow. lines: list of lists of words.
    colors: dict word-index -> colour. Shrinks to fit the safe column."""
    if alpha <= 0.01:
        return
    maxw = maxw or (SAFE[2] - SAFE[0])
    size = int(size * scale)
    while True:
        f = font(size, kind)
        widths = [f.getlength(" ".join(l)) for l in lines]
        if max(widths) <= maxw or size < 30:
            break
        size -= 4
    lh = size * 1.1
    sw = max(4, size // 10)
    pad = sw * 3
    layer = Image.new("RGBA", (int(maxw + 2 * pad), int(lh * len(lines) + 2 * pad)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    k = 0
    for i, (words, wdt) in enumerate(zip(lines, widths)):
        x = layer.width / 2 - wdt / 2
        y = pad + i * lh
        for w in words:
            c = (colors or {}).get(k, WHITE)
            d.text((x + size * 0.05, y + size * 0.07), w, font=f, fill=(0, 0, 0, 140), stroke_width=sw,
                   stroke_fill=(0, 0, 0, 140))
            d.text((x, y), w, font=f, fill=c, stroke_width=sw, stroke_fill=INK)
            x += f.getlength(w + " ")
            k += 1
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    x0, y0 = int(cx - layer.width / 2), int(cy - layer.height / 2)
    assert x0 + pad >= SAFE[0] - 2 and x0 + layer.width - pad <= SAFE[2] + 2, "text outside safe zone"
    img.alpha_composite(layer, (x0, y0))


def number(img, text, cx, cy, size, color, alpha=1.0, suffix=""):
    """Counter with fixed-width digits (no horizontal jitter while it counts) + optional unit."""
    if alpha <= 0.01:
        return
    f = font(size)
    cell = max(f.getlength(d) for d in "0123456789")
    widths = [cell if ch.isdigit() else f.getlength(ch) for ch in text]
    gap = f.getlength(" ")
    total = sum(widths) + (gap + f.getlength(suffix) if suffix else 0)
    sw = max(4, size // 10)
    layer = Image.new("RGBA", (int(total + 6 * sw), int(size * 1.6)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = 3 * sw, layer.height / 2
    for ch, w_ in zip(text, widths):
        for dx, dy, fill, stroke in ((size * 0.05, size * 0.07, (0, 0, 0, 140), (0, 0, 0, 140)), (0, 0, color, INK)):
            d.text((x + w_ / 2 + dx, y + dy), ch, font=f, fill=fill, anchor="mm", stroke_width=sw, stroke_fill=stroke)
        x += w_
    if suffix:
        x += gap
        for dx, dy, fill, stroke in ((size * 0.05, size * 0.07, (0, 0, 0, 140), (0, 0, 0, 140)), (0, 0, WHITE, INK)):
            d.text((x + dx, y + dy), suffix, font=f, fill=fill, anchor="lm", stroke_width=sw, stroke_fill=stroke)
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def pill(img, text, cx, cy, size=40, fg=WHITE, bg=(10, 16, 32, 200), alpha=1.0, accent=None):
    """Label chip (>= 56 px tall, <= 4 words)."""
    if alpha <= 0.01:
        return
    f = font(size, "ExtraBold")
    tw = f.getlength(text)
    h = max(56, int(size * 1.6))
    wdt = tw + size * 1.4
    layer = Image.new("RGBA", (int(wdt) + 4, h + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([2, 2, wdt, h], radius=h / 2, fill=bg, outline=(*(accent or ICE), 255), width=3)
    d.text((wdt / 2 + 1, h / 2 + 2), text, font=f, fill=fg, anchor="mm")
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    x0 = int(min(max(cx - layer.width / 2, SAFE[0]), SAFE[2] - layer.width))
    y0 = int(min(max(cy - layer.height / 2, SAFE[1]), SAFE[3] - layer.height))
    img.alpha_composite(layer, (x0, y0))


def project(p, t):
    """World point -> output pixel, using the same camera as Blender (portrait, sensor fit on height)."""
    loc, tgt, lens, _fs, _fo, roll = T.camera(t)
    loc, tgt, p = np.array(loc), np.array(tgt), np.array(p)
    f = tgt - loc
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    d = p - loc
    z = d @ f
    vh = 18.0 / lens
    return W / 2 + (d @ r / z) / (vh * 9 / 16) * W / 2, H / 2 - (d @ u / z) / vh * H / 2


# ---------------------------------------------------------------- captions (1-3 words, active word amber)
def line_of(t):
    """Index of the narration line a word belongs to."""
    starts = sorted(v[0] for v in L.values())
    return sum(1 for s0 in starts if s0 <= t + 0.06)


def caption_groups():
    """Caption chunks as written in the script ('|' marks), never across narration lines."""
    words = TIMING["words"]
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        last_of_line = i + 1 == len(words) or line_of(words[i + 1][0]) != line_of(w[0])
        if (len(w) > 4 and w[4]) or last_of_line:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    out = []
    for i, g in enumerate(groups):
        t0, t1 = g[0][0], g[-1][1]
        if i == 0:
            t0 = 0.0                               # on screen from frame 0: no empty flash at the loop
        if i + 1 < len(groups):
            t1 = max(t1, min(groups[i + 1][0][0], t1 + 0.5))
        else:
            t1 = T.DUR + 1                         # last chunk stays until the loop restarts
        out.append((t0, t1, g))
    return out


GROUPS = caption_groups()


def draw_captions(img, t):
    for t0, t1, g in GROUPS:
        if t0 <= t < t1:
            words = [w[2].upper() for w in g]
            colors = {}
            for i, w in enumerate(g):
                if w[0] <= t < w[1] + 0.05:
                    colors[i] = AMBER
                elif w[3]:
                    colors[i] = ICE
            s = 0.88 + 0.12 * back_out((t - t0) / 0.14)
            # one line if it fits, else two
            f = font(int(72 * s))
            lines = [words] if f.getlength(" ".join(words)) <= 700 else [words[:2], words[2:]]
            text_block(img, lines, CX, SAFE[3] - 95, 72, scale=s, colors=colors, maxw=700)
            return


# ---------------------------------------------------------------- counters / labels
def fmt(n):
    return f"{int(n):,}"


def overlays(img, t):
    """Big, readable labels (>= 44 px), max 2 text elements at once."""
    S = T.SHOTS
    GREEN = (120, 235, 170)
    pill(img, "THE IMMORTAL JELLYFISH", CX, 380, 48, alpha=window(t, T.W("hook", "forever")[0], S[0][1], 0.15), accent=ICE)
    pill(img, "TURRITOPSIS DOHRNII", CX, 380, 46, alpha=window(t, S[1][0] + 0.1, S[1][1], 0.15), accent=ICE)
    pill(img, "BABY STAGE: POLYP", CX, 380, 50, alpha=window(t, T.T_BABY, S[4][1], 0.15), accent=AMBER)
    pill(img, "ZOOM: ITS CELLS", CX, 380, 50, alpha=window(t, S[5][0] + 0.1, S[5][1], 0.15), accent=ICE)
    pill(img, "NEW JELLYFISH", CX, 380, 50, alpha=window(t, T.T_RELEASE + 0.05, S[6][1], 0.15), accent=GREEN)
    _s, _g, n = T.cycle(t)
    a = window(t, T.T_AGAIN[0] - 0.12, S[7][1], 0.12)
    if a > 0:
        k = n - 2
        pop = 1 + 0.25 * math.exp(-max(0.0, t - T.T_AGAIN[min(k, 2)] + 0.12) / 0.08)
        text_block(img, [["LIFE", f"#{n}"]], CX, 420, 96, alpha=a, scale=pop, colors={1: GREEN})


# ---------------------------------------------------------------- image finishing
RNG = np.random.default_rng(5)
YY, XX = np.mgrid[0:H, 0:W]
VIGNETTE = (1 - 0.32 * np.clip(((XX - W / 2) / (W * 0.62)) ** 2 + ((YY - H / 2) / (H * 0.62)) ** 2, 0, 1) ** 1.3)[..., None]


def finish(src, t):
    if src.size == (W, H):
        img = src                                   # rendered at full resolution: no upscale needed
    else:
        img = src.resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2.2, percent=55, threshold=2))
    a = np.asarray(img).astype(np.float32) / 255.0
    # bloom: blur of the bright parts at quarter resolution
    small = img.resize((W // 4, H // 4), Image.BILINEAR)
    s = np.asarray(small).astype(np.float32) / 255.0
    lum = s.max(axis=2, keepdims=True)
    bright = np.clip((lum - 0.74) / 0.26, 0, 1) * s
    bl = Image.fromarray((bright * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14))
    bl2 = Image.fromarray((bright * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(40))
    bloom = (np.asarray(bl.resize((W, H), Image.BILINEAR)).astype(np.float32) * 0.55 +
             np.asarray(bl2.resize((W, H), Image.BILINEAR)).astype(np.float32) * 0.45) / 255.0
    a = 1 - (1 - a) * (1 - 0.42 * bloom)                      # screen blend
    a = a * VIGNETTE
    # subtle grade: cool shadows, warm highlights
    lum = a.mean(axis=2, keepdims=True)
    a = a + (0.015 * (1 - lum)) * np.array([-0.4, 0.1, 0.6]) + (0.02 * lum) * np.array([0.5, 0.2, -0.4])
    # film grain
    # (no film grain: the image must stay perfectly clean)
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("RGBA")


HI_RES_DIR = os.environ.get("HI_RES_FRAMES", "")   # optional dir with full-resolution re-renders


def source_frame(frames, f):
    hi = os.path.join(HI_RES_DIR, f"f_{f:04d}.png") if HI_RES_DIR else ""
    return hi if hi and os.path.exists(hi) else os.path.join(frames, f"f_{f:04d}.png")


def render_frame(frames, f):
    t = f / T.FPS
    src = Image.open(source_frame(frames, f)).convert("RGB")
    img = finish(src, t)
    overlays(img, t)
    draw_captions(img, t)
    return img.convert("RGB")


# ---------------------------------------------------------------- audio
SR = 44100


def note_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def reverb(x, seconds=2.4, mix=0.35, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    tt = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-tt * 6.0 / seconds)
    ir = np.convolve(ir, np.ones(8) / 8, mode="same")         # darker tail
    ir /= np.sqrt((ir ** 2).sum())
    m = len(x) + n
    nfft = 1 << (m - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]
    return (1 - mix) * x + mix * wet * 0.6


def env(n, a, r):
    e = np.ones(n)
    ka, kr = int(a * SR), int(r * SR)
    e[:ka] = np.linspace(0, 1, ka)
    e[-kr:] *= np.linspace(1, 0, kr)
    return e


def pad_voice(freq, dur, bright=4.0):
    tt = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(tt)
    for det in (-0.004, 0.0, 0.0045):
        f = freq * (1 + det)
        for h in range(1, 9):
            out += np.sin(2 * np.pi * f * h * tt + h) * (1 / h) * math.exp(-h / bright)
    return out / 3


def keys(freq, dur=1.6):
    tt = np.arange(int(dur * SR)) / SR
    x = (np.sin(2 * np.pi * freq * tt) + 0.35 * np.sin(2 * np.pi * 2 * freq * tt) * np.exp(-tt * 3)
         + 0.12 * np.sin(2 * np.pi * 3 * freq * tt) * np.exp(-tt * 6))
    return x * np.exp(-tt * 2.2) * env(len(tt), 0.005, 0.2)


def fold(x, n):
    """Wrap everything that rings on past the loop point back onto the start (circular buffer)."""
    out = x[:n].copy()
    k = n
    while k < len(x):
        seg = x[k:k + n]
        out[:len(seg)] += seg
        k += n
    return out


def make_music_and_sfx():
    """Music + effects as one exact loop period: tails past the end continue at the start."""
    n = int(round(T.DUR * SR))
    ext = n + int(6 * SR)
    music = np.zeros(ext)
    sfx = np.zeros(ext)

    def add(buf, t0, sig, g=1.0):
        i = int(t0 * SR)
        j = min(ext, i + len(sig))
        buf[i:j] += g * sig[: j - i]

    # dreamy, weightless bed: Dmaj7 Bm9 Gmaj7 A | Dmaj7 Gmaj7 A  -> back to Dmaj7 at the loop.
    # Exactly 7 bars per loop (tempo fitted to the video, ~88 bpm), so the last A resolves into the first D.
    chords = [[50, 57, 61, 64], [47, 54, 61, 62], [43, 50, 54, 59], [45, 52, 57, 61],
              [50, 57, 61, 64], [43, 50, 54, 59], [45, 52, 57, 61]]
    bar = T.DUR / 7
    bpm = 240 / bar
    k = 0
    t0 = 0.0
    stop0, stop1 = T.T_DIE + 0.42, L["melt"][0]            # a breath of silence after "it doesn't die"
    while t0 < T.DUR - 1e-6:
        ch = chords[k % 7]
        dur = bar + 1.5
        for m in ch:
            v = pad_voice(note_hz(m), dur, bright=3.5)
            add(music, t0, v * env(len(v), 0.9, 1.3), 0.05)
        step = 60 / bpm / 2
        arp = ch[1:] + [ch[1] + 12, ch[2] + 12]
        tt = t0
        i = 0
        while tt < t0 + bar - 1e-6:
            add(music, tt, keys(note_hz(arp[i % len(arp)] + 12)), 0.05)
            tt += step
            i += 1
        st = np.arange(int(0.5 * SR)) / SR
        add(music, t0, np.sin(2 * np.pi * note_hz(ch[0] - 12) * st) * np.exp(-st * 4), 0.16)
        k += 1
        t0 += bar
    tt = np.arange(ext) / SR
    gate = np.ones(ext)
    gate[(tt >= stop0) & (tt < stop1)] = 0.0
    edge = int(0.08 * SR)
    i0, i1 = int(stop0 * SR), int(stop1 * SR)
    gate[i0 - edge:i0] = np.linspace(1, 0, edge)
    gate[i1:i1 + edge] = np.linspace(0, 1, edge)
    music *= gate
    music = fold(reverb(music, 3.0, 0.45, seed=1), n)            # no fades: the loop is circular

    # --- sound effects (only key moments)
    def thump(f0=110, f1=38, d=1.1, g=1.0):
        st = np.arange(int(d * SR)) / SR
        f = f1 + (f0 - f1) * np.exp(-st * 8)
        return g * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-st * 4.5) * env(len(st), 0.002, 0.2)

    def clink(f=1180, d=0.6):
        st = np.arange(int(d * SR)) / SR
        x = sum(a * np.sin(2 * np.pi * f * r * st) * np.exp(-st * dk) for r, a, dk in
                ((1.0, 0.5, 7), (2.3, 0.3, 9), (3.6, 0.15, 12)))
        return x * env(len(st), 0.001, 0.1)

    def shimmer(d=2.2):
        st = np.arange(int(d * SR)) / SR
        x = sum(np.sin(2 * np.pi * f * st + p) for f, p in ((1175, 0), (1480, 1), (1760, 2), (2217, 3)))
        return x / 4 * np.sin(np.pi * st / d) ** 2

    def swoosh(d=0.6, seed=6, up=True):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        for _ in range(3):
            x = np.convolve(x, np.ones(10) / 10, mode="same")
        st = np.arange(len(x)) / SR
        f = (300 + 900 * st / d) if up else (900 - 700 * st / d)
        tone = 0.25 * np.sin(2 * np.pi * np.cumsum(f) / SR)
        return (x / (np.abs(x).max() + 1e-9) + tone) * np.sin(np.pi * st / d) ** 2

    def pulse_swish(d=0.45, seed=20):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        for _ in range(4):
            x = np.convolve(x, np.ones(14) / 14, mode="same")
        st = np.arange(len(x)) / SR
        return x / (np.abs(x).max() + 1e-9) * np.sin(np.pi * st / d) ** 3

    def snap(d=0.25, seed=21):
        rng = np.random.default_rng(seed)
        st = np.arange(int(d * SR)) / SR
        x = rng.standard_normal(len(st)) * np.exp(-st * 40)
        return x + 0.6 * np.sin(2 * np.pi * 220 * st) * np.exp(-st * 25)

    def chomp(d=0.35, seed=22):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        x = np.convolve(x, np.ones(30) / 30, mode="same")
        st = np.arange(len(x)) / SR
        return x / (np.abs(x).max() + 1e-9) * np.exp(-st * 18) + 0.7 * thump(160, 60, d)

    t_ = 0.0                                                                    # soft swish on each swim stroke
    while t_ < T.T_DIE + 0.5:
        if T.pulse(t_ + 0.15) > 0.3 and T.pulse(t_ + 0.15 - 1 / 30) <= 0.3:
            add(sfx, t_, pulse_swish(), 0.10)
        t_ += 1 / 30
    add(sfx, T.W("hook", "forever")[0], shimmer(1.4), 0.06)                    # "forever"
    add(sfx, T.T_HURT, snap(), 0.18)                                            # torn tentacles
    add(sfx, T.T_DIE, thump(70, 30, 1.4), 0.75)                                 # "it doesn't die" (hit)
    add(sfx, T.T_MELT, swoosh(1.3, 23, up=False), 0.14)                         # melting down
    add(sfx, T.T_SINK, swoosh(1.1, 24, up=False), 0.10)                         # sinking
    add(sfx, T.T_FLOOR - 0.12, thump(130, 50, 0.6), 0.45)                       # lands on the floor
    add(sfx, T.T_BABY, shimmer(1.2), 0.07)                                      # baby polyp opens
    add(sfx, T.T_BABY, clink(1568, 0.8), 0.07)
    rng_ = np.random.default_rng(30)
    for k_ in range(14):                                                        # cells flipping to new
        add(sfx, T.T_BECOME + 0.08 * k_ + 0.03 * rng_.random(), clink(1800 + 900 * rng_.random(), 0.4), 0.035)
    add(sfx, T.T_RELEASE - 0.05, swoosh(0.7, 25, up=True), 0.16)                # new jellyfish swims off
    add(sfx, T.T_RELEASE, shimmer(1.0), 0.05)
    for k_, ta in enumerate(T.T_AGAIN):                                         # again, again, again
        add(sfx, ta - 0.02, thump(150 + 30 * k_, 50, 0.5), 0.45)
        add(sfx, ta, clink(1175 * (1.26 ** k_), 0.7), 0.08)
    add(sfx, L["loop"][0], swoosh(0.8, 26, up=False), 0.10)                     # the fish arrives
    add(sfx, T.T_EATS, chomp(), 0.35)                                           # "eats"
    sfx = fold(reverb(sfx, 2.2, 0.35, seed=2), n)
    return music, sfx


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- subtitles
def write_srt(path):
    def ts(x):
        h, m = int(x // 3600), int(x % 3600 // 60)
        s = x % 60
        return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    out = []
    wt = TIMING["words"]
    k = 0
    for i, (key, spoken, cap, _p) in enumerate(LINES, 1):
        n = len([w for w in cap.split() if w != "|"])
        a, b = wt[k][0], wt[k + n - 1][1]                 # measured start of first word, end of last word
        k += n
        proper = {"SUN": "Sun", "EARTH": "Earth", "KM": "km"}

        def norm(w):
            m = re.match(r"^(\W*)(.*?)(\W*)$", w)
            pre, core, post_ = m.groups()
            if core.isupper() and len(core) > 1:
                core = proper.get(core, core.lower())
            return pre + core + post_
        words = [norm(w) for w in cap.split() if w != "|"]
        text = " ".join(words)
        text = text[0].upper() + text[1:]
        out.append(f"{i}\n{ts(a)} --> {ts(b)}\n{text}\n")
    open(path, "w").write("\n".join(out))


def main():
    frames, out = sys.argv[1], sys.argv[2]
    if "--preview" in sys.argv:
        for f in [int(v) for v in sys.argv[sys.argv.index("--preview") + 1].split(",")]:
            render_frame(frames, f).save(f"{out}_{f:04d}.png")
        return
    music, sfx = make_music_and_sfx()
    n = len(music)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(HERE, "vo", "vo_raw.wav"), "-ac", "1",
                          "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    voice = fold(np.frombuffer(raw, np.float32).astype(float), n)
    # Mix three loop periods back to back and keep the middle one: echo tails, ducking and compressor
    # state then carry straight across the loop point, exactly as when the Short replays.
    mw, sw, vo = out + ".music.wav", out + ".sfx.wav", out + ".voice.wav"
    write_wav(mw, np.tile(music / (np.abs(music).max() + 1e-9) * 0.8, 3))
    write_wav(sw, np.tile(sfx / (np.abs(sfx).max() + 1e-9) * 0.8, 3))
    write_wav(vo, np.tile(voice / (np.abs(voice).max() + 1e-9) * 0.89, 3))
    filt = (
        # voice: warm documentary chain
        "[1:a]aformat=sample_rates=44100:channel_layouts=mono,highpass=f=75,"
        "equalizer=f=190:t=q:w=1.1:g=2.5,equalizer=f=3000:t=q:w=1.0:g=2,equalizer=f=7500:t=q:w=1.5:g=-1.5,"
        "deesser=i=0.35,acompressor=threshold=-20dB:ratio=3:attack=8:release=140:makeup=2,"
        "aecho=0.85:0.6:28|47:0.07|0.04,alimiter=limit=0.9,asplit=2[v1][v2];"
        # music ~6 dB under the voice and ducked further while he speaks
        "[2:a]volume=0.27[mu];[mu][v1]sidechaincompress=threshold=0.03:ratio=6:attack=25:release=420[md];"
        "[3:a]volume=0.42[fx];"
        "[v2][md][fx]amix=inputs=3:normalize=0,aformat=channel_layouts=stereo,"
        f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100,atrim=start_sample={n}:end_sample={2 * n},asetpts=PTS-STARTPTS[a]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(T.FPS), "-i", "-", "-i", vo, "-i", mw, "-i", sw, "-filter_complex", filt,
           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-ar", "44100", "-c:a", "aac", "-b:a", "192k", "-t", str(T.DUR),
           "-movflags", "+faststart", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(T.NFRAMES):
        ff.stdin.write(render_frame(frames, f).tobytes())
        if f % 100 == 0:
            print(f"post {f}/{T.NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    for p_ in (mw, sw, vo):
        os.remove(p_)
    write_srt(os.path.splitext(out)[0] + ".srt")
    print("done:", out)


if __name__ == "__main__":
    main()
