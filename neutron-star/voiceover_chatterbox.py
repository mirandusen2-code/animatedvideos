"""Expressive narration with Chatterbox TTS (Resemble AI, MIT license), keeping the timing of the edit.

Step 1 (Python env with chatterbox-tts installed):
    python voiceover_chatterbox.py generate <reference.wav> <clips_dir> [exaggeration] [cfg_weight]
  Renders every script line as its own clip, in the timbre of the reference voice (zero-shot cloning).
Step 2 (main env):
    python3 voiceover_chatterbox.py fit <clips_dir>
  Places each clip at the start time of the original line (the animation is cut to those times),
  time-stretches a clip only if it would run into the next line (max 15 %), rewrites vo/vo_raw.wav and
  the caption word timings in vo/timing.json (line times stay the same).
"""
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from script import LINES  # noqa: E402

SR = 44100


def generate(ref, out_dir, exaggeration=0.55, cfg=0.45):
    import torch
    from chatterbox.tts import ChatterboxTTS
    torch.manual_seed(7)
    os.makedirs(out_dir, exist_ok=True)
    model = ChatterboxTTS.from_pretrained(device="cpu")
    for key, spoken, _cap, _p in LINES:
        path = os.path.join(out_dir, f"{key}.wav")
        if os.path.exists(path):
            continue
        wav = model.generate(spoken, audio_prompt_path=ref, exaggeration=exaggeration, cfg_weight=cfg)
        sf.write(path, wav.squeeze(0).numpy(), model.sr)
        print("generated", key, flush=True)


def trim(x, sr, thr=0.008):
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    return x[max(0, idx[0] - int(0.01 * sr)): idx[-1] + int(0.1 * sr)]


def load(path):
    """Load, convert to 44.1 kHz mono via ffmpeg (optionally time-stretched later)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def stretch(x, factor):
    p = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                        "-af", f"atempo={factor:.4f}", "-f", "f32le", "-"], input=x.tobytes(),
                       capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.float32).copy()


def is_hot(w):
    core = "".join(c for c in w if c.isalpha())
    return (len(core) > 1 and core.isupper()) or any(c.isdigit() for c in w)


def fit(clips_dir):
    tpath = os.path.join(HERE, "vo", "timing.json")
    timing = json.load(open(tpath))
    lines = timing["lines"]
    keys = [k for k, *_ in LINES]
    total = timing["end"] + 1.0
    out = np.zeros(int(total * SR), np.float32)
    words = []
    report = []
    for i, (key, spoken, cap, _p) in enumerate(LINES):
        x = trim(load(os.path.join(clips_dir, f"{key}.wav")), SR)
        start = lines[key][0]
        slot = (lines[keys[i + 1]][0] - 0.12 - start) if i + 1 < len(keys) else (lines[key][1] - start + 0.6)
        dur = len(x) / SR
        factor = 1.0
        if dur > slot:
            factor = min(1.15, dur / slot)
            x = stretch(x, factor)
            dur = len(x) / SR
        i0 = int(start * SR)
        out[i0:i0 + len(x)] += x[: len(out) - i0]
        ws = cap.split()
        wts = [len(w.strip(".,!?()")) + 2 for w in ws]
        acc = start
        for w, wt in zip(ws, wts):
            d = dur * wt / sum(wts)
            words.append([round(acc, 3), round(acc + d, 3), w, is_hot(w)])
            acc += d
        report.append(f"{key:9s} start {start:5.2f}  {dur:4.2f}s  slot {slot:4.2f}s  stretch {factor:.2f}")
    peak = np.abs(out).max()
    out = out / peak * 0.89 if peak > 0 else out
    sf.write(os.path.join(HERE, "vo", "vo_raw.wav"), out, SR)
    timing["words"] = words
    timing["engine"] = "chatterbox"
    json.dump(timing, open(tpath, "w"), indent=1)
    print("\n".join(report))


if __name__ == "__main__":
    if sys.argv[1] == "generate":
        generate(sys.argv[2], sys.argv[3], *[float(v) for v in sys.argv[4:6]])
    else:
        fit(sys.argv[2])
