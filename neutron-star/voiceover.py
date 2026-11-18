"""Generate the narration with Kokoro (open-source neural TTS), line by line.

Usage: python3 voiceover.py <kokoro_model_dir> <out_dir> [voice] [speed]
  model dir: kokoro-v1.0.onnx + voices-v1.0.bin
  (https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0)
Writes out_dir/vo_raw.wav (dry, 44.1 kHz) and out_dir/timing.json:
  {"lines": {key: [start, end]}, "words": [[start, end, word, hot], ...], "end": t}
The animation timeline is built from timing.json, so picture follows the voice.
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script import LINES  # noqa: E402

SR = 44100
LEAD_IN = 0.15


def trim(x, thr=0.006):
    idx = np.where(np.abs(x) > thr)[0]
    return x if len(idx) == 0 else x[max(0, idx[0] - 200): idx[-1] + 400]


def resample(x, sr_in):
    n = int(len(x) * SR / sr_in)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def is_hot(w):
    core = "".join(c for c in w if c.isalpha())
    return (len(core) > 1 and core.isupper()) or any(c.isdigit() for c in w)


def main():
    model_dir, out_dir = sys.argv[1], sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else "am_michael"
    speed = float(sys.argv[4]) if len(sys.argv) > 4 else 0.95
    os.makedirs(out_dir, exist_ok=True)
    k = Kokoro(os.path.join(model_dir, "kokoro-v1.0.onnx"), os.path.join(model_dir, "voices-v1.0.bin"))
    lang = "en-gb" if voice.startswith("b") else "en-us"

    t = LEAD_IN
    segs, lines, words = [], {}, []
    for key, spoken, cap, pause in LINES:
        audio, sr = k.create(spoken, voice=voice, speed=speed, lang=lang)
        a = resample(trim(np.asarray(audio, np.float32)), sr)
        dur = len(a) / SR
        segs.append((t, a))
        lines[key] = [round(t, 3), round(t + dur, 3)]
        # caption words timed by length (syllable proxy) across the spoken line
        ws = cap.split()
        wts = [len(w.strip(".,!?()")) + 2 for w in ws]
        acc = t
        for w, wt in zip(ws, wts):
            d = dur * wt / sum(wts)
            words.append([round(acc, 3), round(acc + d, 3), w, is_hot(w)])
            acc += d
        print(f"{t:6.2f}-{t + dur:6.2f}  {spoken}")
        t += dur + pause

    out = np.zeros(int((t + 1.0) * SR), np.float32)
    for s, a in segs:
        i = int(s * SR)
        out[i:i + len(a)] += a
    sf.write(os.path.join(out_dir, "vo_raw.wav"), out, SR)
    json.dump({"voice": voice, "speed": speed, "lines": lines, "words": words, "end": round(t, 3)},
              open(os.path.join(out_dir, "timing.json"), "w"), indent=1)
    print(f"narration ends at {t:.2f}s")


if __name__ == "__main__":
    main()
