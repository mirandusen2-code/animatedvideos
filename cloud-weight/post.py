"""Post-production for the neutron-star Short: grade + bloom + grain, captions & counters in the Shorts
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
    words = TIMING["words"]
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        pause = i + 1 < len(words) and line_of(words[i + 1][0]) != line_of(w[0])   # never across lines
        ends = w[2][-1] in ".,!?" or len(cur) == 3 or pause
        # never end a group on a bare number: keep "1 MILLION" together
        if ends and len(cur) > 1 and not pause and w[2][-1] not in ".,!?" and any(ch.isdigit() for ch in w[2]):
            nxt = cur.pop()
            groups.append(cur)
            cur = [nxt]
            continue
        if ends:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    out = []
    for i, g in enumerate(groups):
        t0 = g[0][0]
        t1 = g[-1][1]
        if i + 1 < len(groups):
            t1 = max(t1, min(groups[i + 1][0][0], t1 + 0.5))
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
    """At most one number/label at a time, always inside the safe column."""
    # dial reading: 500,000 KG, then 1,100,000 LB under it
    s1 = T.SHOTS[1][1]
    a = window(t, 0.55, s1, 0.2)
    if a > 0:
        u = clamp((t - 0.55) / 1.3)
        n = 500000 * (1 - (1 - u) ** 3)
        text_block(img, [[fmt(round(n, -3)), "KG"]], CX, 400, 100, alpha=a, colors={0: AMBER})
        lb = window(t, L["pounds"][0], s1, 0.2)
        if lb > 0:
            pill(img, "= 1,100,000 LB", CX, 500, 36, alpha=lb, accent=AMBER)
    # droplet size label (new information, not said in the voice)
    d0, d1 = L["droplets"]
    pill(img, "EACH DROP  ≈ 0.02 MM", CX, 400, 36, alpha=window(t, d0 + 0.6, T.SHOTS[6][1], 0.2))
    # bar comparison: water in the cloud vs air in the same space
    a0 = L["air"][0] + 1.0
    a = window(t, a0, L["feather"][0], 0.25)
    if a > 0:
        grow = clamp((t - a0) / 0.9)
        d = ImageDraw.Draw(img, "RGBA")
        x0, x1 = SAFE[0] + 40, SAFE[2] - 40
        for y, lab, frac, col in ((360, "WATER: 500 T", 0.0005, WHITE), (490, "AIR: 1,000,000 T", 1.0, ICE)):
            wbar = max(16, (x1 - x0) * frac * (1 - (1 - grow) ** 3))
            d.rounded_rectangle([x0, y + 34, x0 + wbar, y + 72], radius=19, fill=col + (int(235 * a),),
                                outline=INK + (int(200 * a),), width=3)
            f = font(46, "ExtraBold")
            d.text((x0, y), lab, font=f, fill=WHITE + (int(255 * a),), anchor="lm", stroke_width=4,
                   stroke_fill=INK + (int(255 * a),))


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


def make_music_and_sfx():
    n = int(T.DUR * SR)
    music = np.zeros(n)
    sfx = np.zeros(n)

    def add(buf, t0, sig, g=1.0):
        i = int(t0 * SR)
        if i >= n:
            return
        j = min(n, i + len(sig))
        buf[i:j] += g * sig[: j - i]

    # bright, warm major-key bed: C  G  Am  F (96 bpm), soft keys in 8ths
    chords = [[48, 55, 60, 64], [43, 50, 55, 59], [45, 52, 57, 60], [41, 48, 53, 57]]
    bpm = 96
    bar = 60 / bpm * 4
    k = 0
    t0 = 0.0
    stop0, stop1 = L["crazy"][0] - 0.55, L["crazy"][0]      # the music stops before the twist line
    while t0 < T.DUR:
        ch = chords[k % 4]
        dur = bar + 1.2
        for m in ch:
            v = pad_voice(note_hz(m), dur, bright=4.5)
            add(music, t0, v * env(len(v), 0.7, 1.1), 0.045)
        step = 60 / bpm / 2
        arp = ch[1:] + [ch[1] + 12, ch[2] + 12]
        tt = t0
        i = 0
        while tt < t0 + bar - 1e-6:
            add(music, tt, keys(note_hz(arp[i % len(arp)] + 12)), 0.055)
            tt += step
            i += 1
        st = np.arange(int(0.4 * SR)) / SR                          # soft bass on the downbeat
        add(music, t0, np.sin(2 * np.pi * note_hz(ch[0] - 12) * st) * np.exp(-st * 5), 0.18)
        k += 1
        t0 += bar
    # music stop before the twist: hard dip to silence, back in on the hit
    tt = np.arange(n) / SR
    gate = np.ones(n)
    gate[(tt >= stop0) & (tt < stop1)] = 0.0
    edge = int(0.05 * SR)
    i0 = int(stop0 * SR)
    gate[i0 - edge:i0] = np.linspace(1, 0, edge)
    music *= gate
    # gentle fade in/out so the loop restart is smooth
    music *= np.clip(tt / 0.4, 0, 1) * np.clip((T.DUR - tt) / 0.5, 0, 1)
    music = reverb(music, 2.6, 0.4, seed=1)

    # --- sound effects (only key moments)
    def thump(f0=110, f1=38, d=1.1, g=1.0):
        st = np.arange(int(d * SR)) / SR
        f = f1 + (f0 - f1) * np.exp(-st * 8)
        return g * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-st * 4.5) * env(len(st), 0.002, 0.2)

    def clink(d=0.9):
        st = np.arange(int(d * SR)) / SR
        x = sum(a * np.sin(2 * np.pi * f * st) * np.exp(-st * dk) for f, a, dk in
                ((1180, 0.5, 7), (2710, 0.35, 9), (4230, 0.2, 12), (6020, 0.1, 16)))
        return x * env(len(st), 0.001, 0.1)

    def shimmer(d=2.2):
        st = np.arange(int(d * SR)) / SR
        x = sum(np.sin(2 * np.pi * f * st + p) for f, p in ((1568, 0), (2093, 1), (2637, 2), (3136, 3)))
        return x / 4 * np.sin(np.pi * st / d) ** 2

    def rumble(d=2.6, seed=3):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        for _ in range(4):
            x = np.convolve(x, np.ones(60) / 60, mode="same")     # keep only the low end
        st = np.arange(len(x)) / SR
        return x / (np.abs(x).max() + 1e-9) * (st / d) ** 1.5 * env(len(x), 0.01, 0.15)

    add(sfx, 0.2, clink(), 0.35)                                       # the scale takes the weight
    add(sfx, 0.2, thump(90, 40, 1.0), 0.35)
    add(sfx, T.SHOTS[2][0], thump(70, 32, 1.4), 0.3)                   # herd reveal
    add(sfx, L["droplets"][0], shimmer(2.0), 0.08)                     # inside the cloud
    add(sfx, L["crazy"][0], thump(80, 28, 2.0), 0.85)                  # twist hit
    add(sfx, L["air"][0], shimmer(1.6), 0.07)                          # the glass cube draws itself
    sfx = reverb(sfx, 1.8, 0.3, seed=2)
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
        n = len(cap.split())
        a, b = wt[k][0], wt[k + n - 1][1]                 # measured start of first word, end of last word
        k += n
        proper = {"SUN": "Sun", "EARTH": "Earth", "KM": "km"}

        def norm(w):
            m = re.match(r"^(\W*)(.*?)(\W*)$", w)
            pre, core, post_ = m.groups()
            if core.isupper() and len(core) > 1:
                core = proper.get(core, core.lower())
            return pre + core + post_
        words = [norm(w) for w in cap.split()]
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
    mw, sw = out + ".music.wav", out + ".sfx.wav"
    write_wav(mw, music / (np.abs(music).max() + 1e-9) * 0.8)
    write_wav(sw, sfx / (np.abs(sfx).max() + 1e-9) * 0.8)
    vo = os.path.join(HERE, "vo", "vo_raw.wav")
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
        "loudnorm=I=-14:TP=-1.5:LRA=11[a]")
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
    os.remove(mw)
    os.remove(sw)
    write_srt(os.path.splitext(out)[0] + ".srt")
    print("done:", out)


if __name__ == "__main__":
    main()
