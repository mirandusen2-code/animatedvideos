# Upload: "This Glass Drop Just Exploded"

## Title (recommended)
**This Glass Drop Just Exploded 💥**

Alternatives (A/B-test after 1–2 days):
1. A Hammer Can't Break It, But Scissors Can
2. The Glass That Explodes at 3,000 MPH
3. Never Snip the Tail of This Glass Drop

## Description
Drip molten glass into cold water and you get a Prince Rupert's drop. The outside cools and hardens first; when the inside cools later it shrinks and pulls on the skin, locking it under enormous compression, around 50 tons per square inch. That's why you can hit the round head with a hammer and nothing happens. But the thin tail has no such armour: snip it and a crack races through the drop at over 3,000 miles per hour, turning the whole thing into powder.

Sources: Chandrasekar & Chaudhri, Philosophical Magazine B (1994), high-speed photography of drop disintegration; Aben, Chaudhri et al., Applied Physics Letters (2016) and the Purdue/Cambridge study (2017) on the surface stress.

#shorts #glass #science

## Tags
prince rupert's drop, prince ruperts drop, glass drop, exploding glass, glass vs hammer, tempered glass, physics, science facts, mind blowing facts, did you know, 3d animation, science explained, shorts, mindblown 3d

## Pinned comment
Would you dare to snip the tail while holding the head? ✂️💥

## Thumbnails (folder `thumbnails/`, 1080×1920)
| File | Text | When to use |
|---|---|---|
| `thumb_exploded.png` | IT JUST EXPLODED | **Recommended** |
| `thumb_hammer.png` | HAMMER PROOF? | Hammer hitting the head |
| `thumb_snip.png` | DON'T SNIP THE TAIL | Rainbow head just before the burst |

## QA passed
- 1080x1920, 30 fps, 570 frames, 19.0 s; H.264 + AAC; loudness −14.1 LUFS integrated; no black frames.
- Every frame checked on contact sheets (cuts at frames 123, 237, 389, 484, 534); captions inside the safe zone and synced word by word.
- Found and fixed in review: the hammer left the frame for 1.3 s and never visibly touched the head (S3 re-rendered with a lower swing and a lower camera); the cutters lingered as a grey slab while the camera dived (they now pull away 0.06 s after the snip).
- Loop seam: picture diff last→first 13.9 (frame 0→1 is 13.7: the powder moves fast); the crack front reaches the head exactly at the seam.
- Whisper across the seam hears one continuous sentence: "…but the tail is its weak spot. Snip it and this glass drop just exploded at over 3,000 miles per hour." (Whisper writes "Snippet and"; the caption shows SNIP IT.)

### Rules checklist (`RULES.md`)
- [x] Frame 0: the rainbow head bursting into powder ≈ 40 % of the frame height, brightest object.
- [x] "3,000+ MPH / SHATTER SPEED" on screen from frame 0, voice and burst sound on frame 0.
- [x] Reads at 180 × 320.
- [x] Named object ≥ 25 % of the frame height in every shot (water shot: the beaker, the gob grows as it falls).
- [x] Every set > 3 s has a clear scale/angle change (S0 pull-back, S1 push, S2 swing to face-on and push-in).
- [x] Labels ≥ 44 px and numbers ≥ 96 px (asserted in post.py).
- [x] Sharp, no motion blur; voice at lightning speed (atempo 1.08); sound from the same event list as the picture.
- [x] Loop in picture and voice; −14 LUFS.
