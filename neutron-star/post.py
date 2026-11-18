"""Post-production for the neutron-star Short: grade + bloom + grain, captions & counters in the Shorts
safe zone, original music + sound effects + processed voice, loudness -14 LUFS, H.264 1080x1920.

Usage: python3 post.py <frames_dir> <out.mp4> [--preview f1,f2,...]   (preview writes PNGs only)
Also writes <out>.srt (subtitles).
"""
import json
import math
import os
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
SAFE = (64, 250, 880, H - 420)
CX = (SAFE[0] + SAFE[2]) / 2                         # 472: centre of the safe column
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
    img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


# ---------------------------------------------------------------- captions (1-3 words, active word amber)
def caption_groups():
    words = TIMING["words"]
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        pause = i + 1 < len(words) and words[i + 1][0] - w[1] > 0.12      # never group across a pause
        ends = w[2][-1] in ".,!?" or len(cur) == 3 or pause
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
            f = font(int(92 * s))
            lines = [words] if f.getlength(" ".join(words)) <= 760 else [words[:2], words[2:]]
            text_block(img, lines, CX, SAFE[3] - 120, 92, scale=s, colors=colors, maxw=760)
            return


# ---------------------------------------------------------------- counters / labels
def fmt(n):
    return f"{int(n):,}"


def overlays(img, t):
    # hook (first ~2.4 s): the claim, big, under the top safe line
    a = 1.0 if t < 2.2 else clamp((2.5 - t) / 0.3)
    if a > 0:
        s = 0.92 + 0.08 * back_out(t / 0.25)
        text_block(img, [["1", "SUGAR", "CUBE"]], CX, 340, 84, alpha=a, scale=s, colors={0: AMBER})
        text_block(img, [[">", "8", "BILLION"], ["PEOPLE"]], CX, 500, 84, alpha=a, scale=s, colors={1: AMBER, 2: AMBER})
    # 20 km label while the narrator says it
    sq0, sq1 = L["squeeze"]
    pill(img, "20 KM  ·  12 MILES", CX, 330, 44, alpha=window(t, sq0 + 2.2, sq1 + 1.6, 0.2))
    # 716 / second counter
    s0, s1 = L["spin"][0], L["second"][1]
    a = window(t, s0, T.T_BACK, 0.2)
    if a > 0:
        n = 716 * clamp((t - s0) / (s1 - s0 - 0.3)) ** 0.7
        text_block(img, [[fmt(n) + "×"]], CX, 360, 150, alpha=a, colors={0: ICE})
        pill(img, "SPINS PER SECOND", CX, 480, 40, alpha=a)
    # one billion tons counter
    b0, b1 = L["billion"]
    a = window(t, b0 + 1.0, T.T_END, 0.2)
    if a > 0:
        u = clamp((t - (b0 + 1.0)) / (b1 - b0 - 1.2))
        n = 1e9 * (1 - (1 - u) ** 3)
        text_block(img, [[fmt(round(n, -6) if u < 1 else 1e9)]], CX, 360, 110, alpha=a, colors={0: AMBER})
        pill(img, "TONS  ·  ONE SUGAR CUBE", CX, 470, 38, alpha=a, accent=AMBER)


# ---------------------------------------------------------------- image finishing
RNG = np.random.default_rng(5)
YY, XX = np.mgrid[0:H, 0:W]
VIGNETTE = (1 - 0.32 * np.clip(((XX - W / 2) / (W * 0.62)) ** 2 + ((YY - H / 2) / (H * 0.62)) ** 2, 0, 1) ** 1.3)[..., None]


def finish(src, t):
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
    # white flash on the supernova (6 frames)
    tf = T.T_COLLAPSE + 0.25
    if tf <= t < tf + 6 / T.FPS:
        k = 1 - (t - tf) / (6 / T.FPS)
        a = a + (1 - a) * (0.92 * k)
    # film grain
    a = a + RNG.normal(0, 0.012, (H, W, 1)).astype(np.float32)
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("RGBA")


def render_frame(frames, f):
    t = f / T.FPS
    img = finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), t)
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

    # chords (D minor): Dm  Bb  F  C, 2.67 s each (90 bpm, one bar)
    chords = [[50, 57, 62, 65], [46, 53, 58, 62], [41, 48, 53, 57], [48, 55, 60, 64]]
    bar = 60 / 90 * 4
    k = 0
    t0 = 0.0
    stop0, stop1 = T.T_PULSAR - 0.55, T.T_PULSAR      # the music stops before the twist line
    while t0 < T.DUR:
        ch = chords[k % 4]
        dur = bar + 1.2
        darker = T.T_SPACE <= t0 < T.T_PULSAR
        for m in ch:
            v = pad_voice(note_hz(m - (12 if darker and m > 55 else 0)), dur, bright=3.0 if darker else 4.5)
            add(music, t0, v * env(len(v), 0.9, 1.1), 0.05)
        # soft keys arpeggio (8ths, 16ths during the pulsar)
        step = 60 / 90 / (4 if T.T_PULSAR <= t0 < T.T_BACK else 2)
        arp = ch[1:] + [ch[1] + 12]
        tt = t0
        i = 0
        while tt < t0 + bar - 1e-6:
            if not (T.T_SPACE <= tt < T.T_PULSAR):          # no plucks in the dark collapse section
                add(music, tt, keys(note_hz(arp[i % len(arp)] + 12)), 0.06)
            tt += step
            i += 1
        k += 1
        t0 += bar
    # sub pulse while the pulsar spins
    for i in range(200):
        tp = T.T_PULSAR + i * 60 / 90 / 2
        if tp >= T.T_BACK:
            break
        st = np.arange(int(0.35 * SR)) / SR
        add(music, tp, np.sin(2 * np.pi * 36.7 * st) * np.exp(-st * 9), 0.35)
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

    add(sfx, 0.0, thump(95, 40, 1.0) + clink(), 0.55)                  # scale slams down
    add(sfx, L["neutron"][0] + 0.3, shimmer(), 0.10)                   # it starts to glow
    add(sfx, T.T_COLLAPSE - 2.3, rumble(2.5), 0.45)                    # star shudders
    add(sfx, T.T_COLLAPSE + 0.25, thump(140, 30, 2.4), 0.9)            # collapse / supernova
    add(sfx, T.T_PULSAR, thump(80, 28, 2.0), 0.85)                     # twist hit
    add(sfx, L["billion"][1] - 0.6, shimmer(1.6), 0.07)                # billion tons
    land = T.DUR - 0.02
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
    for i, (key, spoken, cap, _p) in enumerate(LINES, 1):
        a, b = L[key]
        out.append(f"{i}\n{ts(a)} --> {ts(b)}\n{cap.replace('(', '').replace(')', '')}\n")
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
        "[2:a]volume=0.32[mu];[mu][v1]sidechaincompress=threshold=0.03:ratio=6:attack=25:release=420[md];"
        "[3:a]volume=0.42[fx];"
        "[v2][md][fx]amix=inputs=3:normalize=0,aformat=channel_layouts=stereo,"
        "loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(T.FPS), "-i", "-", "-i", vo, "-i", mw, "-i", sw, "-filter_complex", filt,
           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
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
