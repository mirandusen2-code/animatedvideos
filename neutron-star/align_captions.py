"""Align caption words to the real speech with Whisper word timestamps (run in an env with faster-whisper).

Usage: python align_captions.py [--apply]
Reports, per caption word, the estimated vs. measured start time. With --apply, writes the measured
timings into vo/timing.json (line times stay unchanged, so the edit is not affected).
"""
import difflib
import json
import os
import re
import sys

from faster_whisper import WhisperModel

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from script import LINES  # noqa: E402

NUM = {"twenty": "20", "twelve": "12", "seven": "7", "hundred": "00", "thousand": "000",
       "kilometers": "km", "kilometres": "km", "miles": "miles"}


def norm(w):
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    return NUM.get(w, w)


timing = json.load(open(os.path.join(HERE, "vo", "timing.json")))
model = WhisperModel("small.en", device="cpu", compute_type="int8")
segs, _ = model.transcribe(os.path.join(HERE, "vo", "vo_raw.wav"), word_timestamps=True, beam_size=5,
                           language="en")
spoken = [(w.start, w.end, norm(w.word)) for s in segs for w in s.words]

cap = timing["words"]                               # [start, end, word, hot]
cap_n = [norm(w[2]) for w in cap]
sm = difflib.SequenceMatcher(None, cap_n, [w[2] for w in spoken], autojunk=False)
measured = [None] * len(cap)
for a, b, n in sm.get_matching_blocks():
    for k in range(n):
        measured[a + k] = spoken[b + k]
# fill gaps (e.g. "700" spoken as "seven hundred") by interpolating between matched neighbours
for i in range(len(cap)):
    if measured[i] is None:
        prev = next((measured[j] for j in range(i - 1, -1, -1) if measured[j]), None)
        nxt = next((measured[j] for j in range(i + 1, len(cap)) if measured[j]), None)
        s0 = prev[1] if prev else cap[i][0]
        s1 = nxt[0] if nxt else cap[i][1]
        measured[i] = (s0, max(s1, s0 + 0.15), cap_n[i])

# keep every measured time inside its own narration line (Whisper can smear words across pauses)
line_ranges = list(timing["lines"].values())


def line_window(t):
    for a, b in line_ranges:
        if a - 0.05 <= t <= b + 0.05:
            return a, b
    return None


for i, (c, m) in enumerate(zip(cap, measured)):
    win = line_window(c[0])
    if win and not (win[0] - 0.08 <= m[0] <= win[1]):
        s0 = min(max(m[0], win[0]), win[1] - 0.1)
        measured[i] = (s0, max(s0 + 0.12, min(m[1], win[1])), m[2])
offs = []
for c, m in zip(cap, measured):
    offs.append(m[0] - c[0])
    flag = "  <-- off" if abs(m[0] - c[0]) > 0.25 else ""
    print(f"{c[2]:>14s}  estimated {c[0]:6.2f}  spoken {m[0]:6.2f}  diff {m[0] - c[0]:+.2f}{flag}")
offs = [abs(o) for o in offs]
print(f"\nmatched {sum(1 for b in sm.get_matching_blocks() for _ in range(b[2]))}/{len(cap)} words; "
      f"mean |diff| {sum(offs) / len(offs):.2f}s, max {max(offs):.2f}s")
if "--apply" in sys.argv:
    timing["words"] = [[round(m[0], 3), round(m[1], 3), c[2], c[3]] for c, m in zip(cap, measured)]
    timing["words_aligned"] = "whisper"
    json.dump(timing, open(os.path.join(HERE, "vo", "timing.json"), "w"), indent=1)
    print("applied measured timings to vo/timing.json")
