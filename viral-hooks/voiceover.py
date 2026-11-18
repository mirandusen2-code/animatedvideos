"""Documentary-style voiceover with Kokoro TTS (offline, open-source).

Usage:  python3 voiceover.py <model_dir> <out_dir> [voice] [speed]
  model_dir must contain kokoro-v1.0.onnx and voices-v1.0.bin
  (download from https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0)
Writes <out_dir>/vo.wav (44.1 kHz mono) and <out_dir>/vo.json (caption timings that follow the speech).
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

SR_OUT = 44100
GAP = 0.14

# (earliest start in s or None, spoken text, on-screen caption chunks)
LINES = [
    (0.05, "If you jumped into a hole through the Earth,",
     ["If you jumped into", "a hole through the EARTH,"]),
    (None, "you'd come out the other side in thirty-eight minutes.",
     ["you'd come out the other side", "in 38 MINUTES."]),
    (None, "Here's the ride.", ["Here's the ride."]),
    (6.8, "You fall faster, and faster,", ["You fall FASTER and faster..."]),
    (None, "past the mantle, into liquid metal,", ["past the mantle, into liquid metal..."]),
    (None, "to a core nearly as hot as the surface of the Sun.",
     ["to a core nearly as HOT", "as the Sun's surface."]),
    (None, "Now you're doing twenty-eight thousand kilometers an hour.",
     ["Now you're doing", "28,000 KM/H..."]),
    (None, "Seventeen thousand miles per hour.", ["that's 17,000 MPH!"]),
    (None, "But here's the crazy part.", ["But here's the CRAZY part:"]),
    (None, "At the center, gravity pulls from every side,", ["at the center, gravity pulls", "from EVERY side..."]),
    (None, "so now, it slows you down.", ["so now it", "SLOWS you down."]),
    (24.8, "Thirty-eight minutes later, you reach the other side,",
     ["38 minutes later,", "you reach the other side..."]),
    (28.0, "stop, for a split second,", ["STOP for a split second..."]),
    (None, "and fall all the way back. Forever.", ["and fall ALL the way back.", "FOREVER."]),
]


def trim(x, thr=0.008):
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    return x[max(0, idx[0] - 240): idx[-1] + 240]  # keep ~10 ms padding


def resample(x, sr_in, sr_out):
    n = int(len(x) * sr_out / sr_in)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def main():
    model_dir, out_dir = sys.argv[1], sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else "bm_george"
    speed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.08
    lang = "en-gb" if voice.startswith("b") else "en-us"
    os.makedirs(out_dir, exist_ok=True)
    k = Kokoro(os.path.join(model_dir, "kokoro-v1.0.onnx"), os.path.join(model_dir, "voices-v1.0.bin"))

    segs, captions = [], []
    t = 0.0
    for target, text, chunks in LINES:
        audio, sr = k.create(text, voice=voice, speed=speed, lang=lang)
        audio = resample(trim(np.asarray(audio, np.float32)), sr, SR_OUT)
        start = max(target if target is not None else 0.0, t + GAP)
        dur = len(audio) / SR_OUT
        segs.append((start, audio))
        # captions follow the words: split the line's duration by word count
        words = [len(c.split()) for c in chunks]
        c0 = start
        for c, w in zip(chunks, words):
            c1 = c0 + dur * w / sum(words)
            captions.append([round(c0, 3), round(c1, 3), c])
            c0 = c1
        print(f"{start:6.2f}-{start + dur:6.2f}  {text}")
        t = start + dur

    total = max(s + len(a) / SR_OUT for s, a in segs) + 0.6
    out = np.zeros(int(total * SR_OUT), np.float32)
    for s, a in segs:
        i = int(s * SR_OUT)
        out[i:i + len(a)] += a
    # captions stay up until the next one starts (no flicker in between)
    for a, b in zip(captions, captions[1:]):
        a[1] = max(a[1], min(b[0], a[1] + 0.6))
    sf.write(os.path.join(out_dir, "vo.wav"), out, SR_OUT)
    json.dump({"voice": voice, "speed": speed, "end": round(t, 3), "captions": captions},
              open(os.path.join(out_dir, "vo.json"), "w"), indent=1)
    print(f"voiceover ends at {t:.2f}s")


if __name__ == "__main__":
    main()
