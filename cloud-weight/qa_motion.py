"""QA: is the video smooth? Measures the change between consecutive frames of the final MP4.

Flags (1) jumps: a big change that is NOT on a planned cut, (2) freezes: runs of identical frames,
(3) uneven motion: a frame whose change is far above its neighbours inside a shot.
Usage: python3 qa_motion.py <video.mp4>
"""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeline as T  # noqa: E402

W, H = 135, 240
video = sys.argv[1]
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={W}:{H}", "-f", "rawvideo",
                      "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
diff = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))          # diff[i] = change from frame i to i+1
cuts = {int(round(s[0] * T.FPS)) for s in T.SHOTS[1:]}
if hasattr(T, "T_COLLAPSE"):                              # neutron-star video: planned 6-frame white flash
    flash = int(round((T.T_COLLAPSE + 0.25) * T.FPS))
    cuts |= set(range(flash - 1, flash + 8))
if hasattr(T, "CLOUD"):                                   # cloud video: planned white dissolve into the cloud
    dz = int(round(T.SHOTS[5][0] * T.FPS))
    cuts |= set(range(dz - 9, dz + 10))
problems = []
for i, d in enumerate(diff):
    f = i + 1
    near_cut = any(abs(f - c) <= 1 for c in cuts)
    lo, hi = max(0, i - 4), min(len(diff), i + 5)
    local = np.median(np.concatenate([diff[lo:i], diff[i + 1:hi]])) if hi - lo > 1 else d
    if not near_cut and d > 12 and d > 4 * local + 2:
        problems.append(f"jump at frame {f} ({f / T.FPS:.2f}s): change {d:.1f} vs typical {local:.1f}")
run = 0
for i, d in enumerate(diff):
    run = run + 1 if d < 0.05 else 0
    if run == 12:
        problems.append(f"freeze from {(i - 11) / T.FPS:.2f}s (>= 0.4 s identical frames)")
# a cut frame must already belong to the new shot: its change into the next frame must look like normal motion
for sh in T.SHOTS[1:]:
    c = int(round(sh[0] * T.FPS + 0.4999))
    if c + 3 < len(diff):
        inside = np.median(diff[c + 1:c + 6])
        if diff[c] > 3 * inside + 3:
            problems.append(f"half-mixed frame at cut {c} ({c / T.FPS:.2f}s): change into next frame {diff[c]:.1f} "
                            f"vs {inside:.1f} inside the shot")
# one-frame anomalies (an object popping in/out, a wrong frame): frame f differs from BOTH neighbours
for f in range(2, len(diff) - 2):
    if any(abs(f - c) <= 2 for c in cuts):
        continue
    around = np.median(np.r_[diff[f - 3:f - 1], diff[f + 1:f + 3]])
    if diff[f - 1] > 3 * around + 1.5 and diff[f] > 3 * around + 1.5:
        problems.append(f"one-frame anomaly at frame {f} ({f / T.FPS:.2f}s)")
# flicker: brightness jumps inside a shot
lum = frames.mean(axis=(1, 2))
for f in range(1, len(lum) - 1):
    if any(abs(f - c) <= 2 for c in cuts):
        continue
    if abs(lum[f] - (lum[f - 1] + lum[f + 1]) / 2) > 2.5:
        problems.append(f"flicker at frame {f} ({f / T.FPS:.2f}s): brightness {lum[f]:.1f} vs {lum[f-1]:.1f}/{lum[f+1]:.1f}")
print(f"{len(frames)} frames, {len(cuts)} planned cuts, mean change {diff.mean():.2f}")
print("\n".join(problems) if problems else "OK: no unplanned jumps, no freezes")
