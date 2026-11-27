"""Narration for the grape-plasma video: Chatterbox (MIT) in the timbre of a reference clip, line by line, then Whisper word timing.

Run in the env that has chatterbox-tts + faster-whisper:
    python voiceover.py <reference.wav> [exaggeration] [cfg_weight]
Writes vo/clips/<key>.wav, vo/vo_raw.wav (44.1 kHz) and vo/timing.json:
  {"lines": {key: [start, end]}, "words": [[start, end, caption_word, hot], ...], "end": t}
The animation timeline is built from these times, so the picture follows the voice.
"""
import difflib
import json
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from script import LINES  # noqa: E402

SR = 44100
LEAD_IN = 0.1
VO = os.path.join(HERE, "vo")
NUM = {"5": "5", "five": "5"}


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def trim(x, thr=0.008):
    idx = np.where(np.abs(x) > thr)[0]
    return x if len(idx) == 0 else x[max(0, idx[0] - int(0.01 * SR)): idx[-1] + int(0.1 * SR)]


def is_hot(w):
    core = "".join(c for c in w if c.isalpha())
    return (len(core) > 1 and core.isupper()) or any(c.isdigit() for c in w)


def norm(w):
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    return NUM.get(w, w)


def main():
    ref = sys.argv[1]
    exag = float(sys.argv[2]) if len(sys.argv) > 2 else 0.55
    cfg = float(sys.argv[3]) if len(sys.argv) > 3 else 0.45
    clips = os.path.join(VO, os.environ.get("VO_CLIPS", "clips"))   # "clips_fast" = the same takes, 7 % faster (atempo)
    os.makedirs(clips, exist_ok=True)
    import torch
    from chatterbox.tts import ChatterboxTTS
    torch.manual_seed(11)
    model = None
    for key, spoken, _c, _p in LINES:
        p = os.path.join(clips, f"{key}.wav")
        if not os.path.exists(p):
            model = model or ChatterboxTTS.from_pretrained(device="cpu")
            wav = model.generate(spoken, audio_prompt_path=ref, exaggeration=exag, cfg_weight=cfg)
            sf.write(p, wav.squeeze(0).numpy(), model.sr)
            print("generated", key, flush=True)

    # assemble with the planned pauses
    t = LEAD_IN
    segs, lines = [], {}
    for key, _s, _c, pause in LINES:
        x = trim(load(os.path.join(clips, f"{key}.wav")))
        segs.append((t, x))
        lines[key] = [round(t, 3), round(t + len(x) / SR, 3)]
        t += len(x) / SR + pause * float(os.environ.get("VO_PAUSE", "1.0"))
    out = np.zeros(int((t + 1.0) * SR), np.float32)
    for s0, x in segs:
        i = int(s0 * SR)
        out[i:i + len(x)] += x
    out = out / (np.abs(out).max() + 1e-9) * 0.89
    sf.write(os.path.join(VO, "vo_raw.wav"), out, SR)

    # real word timings with Whisper, matched to the caption words (and kept inside their own line)
    from faster_whisper import WhisperModel
    wm = WhisperModel("small.en", device="cpu", compute_type="int8")
    words = []
    report = []
    for key, spoken, cap, _p in LINES:
        a, b = lines[key]
        seg, _ = wm.transcribe(os.path.join(clips, f"{key}.wav"), word_timestamps=True, language="en")
        seg = list(seg)
        heard = " ".join(s.text.strip() for s in seg)
        rec = [(w.start, w.end, norm(w.word)) for s in seg for w in s.words]
        # offset: clip time -> timeline time (the clip was trimmed at its start)
        x = load(os.path.join(clips, f"{key}.wav"))
        idx = np.where(np.abs(x) > 0.008)[0]
        off = a - max(0, idx[0] - int(0.01 * SR)) / SR if len(idx) else a
        toks = cap.split()
        cw, brk = [], set()
        for tk in toks:                                   # '|' marks a chunk break after the previous word
            if tk == "|":
                brk.add(len(cw) - 1)
            else:
                cw.append(tk)
        brk.add(len(cw) - 1)
        sm = difflib.SequenceMatcher(None, [norm(w) for w in cw], [r[2] for r in rec], autojunk=False)
        got = [None] * len(cw)
        for i, j, n in sm.get_matching_blocks():
            for k in range(n):
                got[i + k] = rec[j + k]
        for i, w in enumerate(cw):
            if got[i] is None:                         # interpolate unmatched words
                prev = next((got[j] for j in range(i - 1, -1, -1) if got[j]), None)
                nxt = next((got[j] for j in range(i + 1, len(cw)) if got[j]), None)
                s0 = prev[1] if prev else 0.0
                s1 = nxt[0] if nxt else (b - a)
                got[i] = (s0, max(s1, s0 + 0.12), "")
            s0 = min(max(a, got[i][0] + off), b - 0.05)
            s1 = min(max(s0 + 0.08, got[i][1] + off), b)
            words.append([round(s0, 3), round(s1, 3), w, is_hot(w), i in brk])
        ratio = difflib.SequenceMatcher(None, re.sub(r"[^a-z ]", "", spoken.lower()).split(),
                                        re.sub(r"[^a-z ]", "", heard.lower()).split()).ratio()
        report.append(f"{key:9s} {a:5.2f}-{b:5.2f}  match {ratio:.2f} | {heard}")
    json.dump({"voice": "chatterbox (timbre of the reference clip)", "lines": lines, "words": words, "end": round(t, 3)},
              open(os.path.join(VO, "timing.json"), "w"), indent=1)
    print("\n".join(report))
    print(f"narration ends at {t:.2f}s")


if __name__ == "__main__":
    main()
