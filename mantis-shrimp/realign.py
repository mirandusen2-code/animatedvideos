"""Re-time caption words from Whisper on the full narration (vo_raw.wav), which is more reliable than the
isolated clips. Words keep their own line window. Usage (Whisper env): python realign.py"""
import difflib
import json
import os
import re

from faster_whisper import WhisperModel

HERE = os.path.dirname(os.path.abspath(__file__))
TJ = os.path.join(HERE, "vo", "timing.json")
NUM = {"fifty": "50", "seven": "7000", "thousand": "7000"}


def norm(w):
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    return NUM.get(w, w)


tj = json.load(open(TJ))
m = WhisperModel("small.en", device="cpu", compute_type="int8")
seg, _ = m.transcribe(os.path.join(HERE, "vo", "vo_raw.wav"), word_timestamps=True, language="en")
rec = [(w.start, w.end, norm(w.word)) for s in seg for w in s.words]
words = tj["words"]
sm = difflib.SequenceMatcher(None, [norm(w[2]) for w in words], [r[2] for r in rec], autojunk=False)
n = 0
for i, j, k in sm.get_matching_blocks():
    for d in range(k):
        w, r = words[i + d], rec[j + d]
        line = next(v for v in tj["lines"].values() if v[0] - 0.05 <= w[0] <= v[1] + 0.05)
        s0 = min(max(line[0], r[0]), line[1] - 0.05)
        w[0], w[1] = round(s0, 3), round(min(max(s0 + 0.08, r[1]), line[1]), 3)
        n += 1
for a, b in zip(words, words[1:]):                  # keep order, no overlaps
    if b[0] < a[0]:
        b[0] = a[0] + 0.05
json.dump(tj, open(TJ, "w"), indent=1)
print(f"re-timed {n}/{len(words)} words")
print(" ".join(f"{w[2]}@{w[0]:.2f}" for w in words))
