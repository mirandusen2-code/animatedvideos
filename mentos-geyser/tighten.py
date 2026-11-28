"""Shorten long silences inside the narration clips (TTS sometimes pauses ~1 s after "Why?").
Usage: python3 tighten.py vo/clips_fast [max_gap_s]   (rewrites the clips in place; keeps a backup folder)"""
import os
import shutil
import sys

import numpy as np
import soundfile as sf

d = sys.argv[1]
MAXG = float(sys.argv[2]) if len(sys.argv) > 2 else 0.38
bak = d.rstrip("/") + "_untrimmed"
if not os.path.exists(bak):
    shutil.copytree(d, bak)
for fn in sorted(os.listdir(bak)):
    x, sr = sf.read(os.path.join(bak, fn))
    mono = x if x.ndim == 1 else x.mean(1)
    hop = int(sr * 0.01)
    env = np.array([np.sqrt(np.mean(mono[i:i + hop] ** 2)) for i in range(0, len(mono), hop)])
    thr = max(env.max() * 0.025, 1e-4)
    quiet = env < thr
    keep = np.ones(len(mono), bool)
    i, n = 0, len(env)
    # find interior quiet runs (not the lead-in / tail)
    first = np.argmax(~quiet)
    last = n - 1 - np.argmax(~quiet[::-1])
    removed = 0.0
    while i < n:
        if quiet[i] and first < i < last:
            j = i
            while j < n and quiet[j]:
                j += 1
            run = (j - i) * 0.01
            if run > MAXG:
                cut = run - MAXG
                a = int((i * 0.01 + MAXG / 2) * sr)
                keep[a:a + int(cut * sr)] = False
                removed += cut
            i = j
        else:
            i += 1
    sf.write(os.path.join(d, fn), x[keep], sr)
    print(f"{fn}: removed {removed:.2f}s")
