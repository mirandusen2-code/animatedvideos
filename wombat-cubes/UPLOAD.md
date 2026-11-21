# Upload: "Wombats Poop Cubes"

## Title (recommended)
**Wombats Poop Cubes (Yes, Really) 🟫**

Alternatives (A/B-test after 1–2 days if "viewed vs. swiped" is low):
1. Why Wombat Poop Is Square
2. The Only Animal That Poops Cubes
3. How Do Wombats Poop Cubes? 🤯

## Description
Bare-nosed wombats are the only animals known to make cube-shaped poop. The secret is in the last part of their intestine: its wall has stiff and stretchy regions, and as the poop dries out and gets squeezed, the stiff parts shape flat sides and sharp corners. One wombat can leave up to 100 cubes a night, often on rocks and logs to mark its territory, and scientists think the shape helps them stay put instead of rolling away.

Sources: Yang et al., "Intestines of non-uniform stiffness mold the corners of wombat feces", Soft Matter (2021); University of Tasmania & Georgia Tech (2021).

#shorts #science #wombat

## Tags (YouTube Studio → More options → Tags)
wombat, wombat poop, cube poop, square poop, wombat cubes, why do wombats poop cubes, australian animals, animal facts, weird animal facts, science facts, mind blowing facts, biology, nature, did you know, 3d animation, science explained, shorts, mindblown 3d

## Pinned comment (drives comments)
Which animal should we x-ray next? 🩻

## Thumbnails (folder `thumbnails/`, 1080×1920)
| File | Text | When to use |
|---|---|---|
| `thumb_cube.png` | WOMBATS POOP CUBES | **Recommended**: the cube macro + the claim |
| `thumb_xray.png` | HOW POOP GETS SQUARE | The x-ray mechanism |
| `thumb_why.png` | WHY CUBES? | Curiosity: cubes on the rock, the round one rolling off |

## QA passed
- **Video:** 1080×1920, 30 fps, 645 frames, 21.5 s, H.264 + AAC 44.1 kHz. Rendered at full resolution with no upscaling, no motion blur and no grain.
- **Frame check:** I reviewed every frame on contact sheets, both the raw renders and the final mp4. Two bugs were found and fixed before the final render:
  - Round poop left the gut before it was squeezed. The log is now shorter and faster, so only square cubes come out.
  - The fur disappeared in a single frame when the x-ray turned on. The hair now fades out with the x-ray.
  - After these fixes: no glitches, no parts intersecting, no blown-out areas.
- **Motion (qa_motion):** 8 planned cuts, no unplanned jumps, no frozen frames. blackdetect found no black frames.
- **Captions:**
  - Every caption stays inside the safe zone (asserted in code) and is synced word by word to the voice.
  - Line breaks are fixed per caption group.
  - Labels: BARE-NOSED WOMBAT, REAL SIZE: ABOUT 0.8 IN, X-RAY, STIFF / STRETCHY, WATER SQUEEZED OUT, a counter from 1 to 100 cubes in one night, TERRITORY MARKER, CUBES STAY PUT.
- **Loudness:** −14.0 LUFS integrated, LRA 2.0 LU.
- **Speech (Whisper small.en on the final mix, played twice in a row):** every line matches the script. Whisper writes "Wombats" as "Wombat's", which sounds the same.
- **Loop seam, picture:** the change from the last frame to the first frame is 1.82, about the same as a normal frame step (median 1.67). The last shot glides back into the exact opening framing, and the wombat's walk is phase-locked across the seam.
- **Loop seam, sound:**
  - The music is exactly 8 bars per loop and resolves G → C on the seam.
  - The audio is circular (folded tail), with no click: the sample jump at the seam (0.005) is smaller than a typical sample step (0.008).
  - "…that's why" was cut from the full sentence "that's why wombats poop cubes", so the voice keeps its continuing intonation into "wombats poop cubes." The gap between the two is about 0.16 s.
- **Thumbnails:** "WOMBATS POOP CUBES" (frame 155), "HOW POOP GETS SQUARE" (frame 353), "WHY CUBES?" (frame 540). All text is inside the safe zone.
