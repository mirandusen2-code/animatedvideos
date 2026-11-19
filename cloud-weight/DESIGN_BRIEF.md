# Design Brief: "This Fluffy Cloud Weighs Half a Million Kilos"
*Written as the art director / senior motion designer for MindBlown 3D. This brief is the single source
of truth for the look, the motion and the quality control of the video. Everything on screen must be
deliberate; if an element has no job, it is removed.*

---

## 1. Creative concept
**"The heaviest light thing you know."** We stage the cloud like a museum exhibit being weighed: a giant
brass crane scale, a herd of porcelain elephants as the unit of comparison, and a glass cube that reveals
the invisible air around it. The tone is *wonder*, not *lecture*: calm camera, bright daylight, a warm voice.

**One idea per shot.** The viewer should be able to describe each shot in five words.

## 1b. Pacing (viewer feedback)
- Target **20–25 s**: a tighter cut raises the average % viewed and makes rewatches more likely.
  Pauses 0.2–0.3 s; only a short breath after the question and before the twist.
- If a video runs 30 s or longer, it needs an **extra mid-video hook** (a comparison, plot twist or big
  visual change) so the middle never sags. In this video: open question + dive into the cloud (~6 s),
  new information inside the cloud (~9–13 s), the twist with the cube and the bars (~14 s), loop (end).

## 2. Visual language
| Element | Rule |
|---|---|
| World | Bright daytime, deep-blue zenith fading to a pale horizon, warm low sun from camera-left, rolling green hills. |
| Hero | One cumulus cloud: cauliflower top, flat base, sunlit white top, cool blue-grey underside. |
| Props | "Toy-museum" materials only: polished brass, porcelain, glass. No plastic look, no pure black. |
| Palette | Sky `#2E6FD8` → `#CFDDF0` · Cloud `#F4F6FA` / shade `#AEB9CC` · Brass `#D19A42` · Grass `#3E8E41` · Porcelain `#5C5C63` · Accent amber `#FFB547` · Accent ice `#7FD8FF`. |
| Contrast | The subject is always the brightest or most saturated thing in the frame. |

## 3. Composition (9:16, 1080×1920)
- **Phone-safe column:** essential content inside **x 92–860, y 300–1540** (measured on a real phone screenshot).
- **Thirds:** the subject sits on the upper or middle third; the lower third is reserved for captions.
- **Headroom:** the scale's cable leaves the frame at the top. Never cut the dial or the cloud at an edge.
- **Depth:** every shot has a foreground, middle and background layer (hills, herd, sky) for parallax.

## 4. Typography system
| Role | Font | Size | Style |
|---|---|---|---|
| Captions | Montserrat Black, UPPERCASE | 72 px | white, 9 px dark outline, soft drop shadow; spoken word amber, key words ice |
| Big numbers | Montserrat Black | 100 px | **fixed-width digits** (no horizontal jitter while counting), amber |
| Labels / pills | Montserrat ExtraBold | 36–46 px | rounded pill, dark glass background, 3 px accent outline, ≥ 56 px tall, ≤ 4 words |

Rules: max **2 text elements** at once · captions 1–3 words, never split a number from its unit, never end
on a small word · line breaks fixed at final size (no reflow while popping in) · numbers ease out
(fast start, gentle landing).

## 5. Motion principles
- **Easing:** every move uses ease-in-out (smootherstep); nothing starts or stops abruptly.
- **Camera:** always creeping (slow push or orbit), never static, never handheld jitter. No motion blur:
  every frame must be a clean, sharp still.
- **Cuts:** a new angle on every cut, max ~3 s per shot. One hero object carries across the cut.
- **Transitions:** hard cuts on narration beats; **one** soft "through the cloud" white dissolve when
  the camera enters the cloud (the only dissolve in the video, so it stays special).
- **Overshoot:** the dial needle overshoots and settles (a physical, believable motion).
- **Twist beat** ("But here's the crazy part"): music drops out, low impact, wide shot with a slow roll.

## 6. Shot design
| # | Line | Shot | Purpose |
|---|---|---|---|
| 1 | hook | Low hero angle: cloud on the crane scale, needle swings to 500 | Stop the scroll: absurd claim + visual proof |
| 2 | hook/pounds | Dial close-up, 0–600 ×1000 kg, needle at 500 | Readable proof, US units |
| 3 | elephants | Ground level among 100 porcelain elephants, cloud above | Scale comparison you feel |
| 4 | elephants | Aerial: 10×10 herd under the cloud | Count it: 100 |
| 5 | why | Push into the cloud → white dissolve | Open loop, enter the mystery |
| 6–9 | droplets/light | Inside the cloud: droplets (shallow DOF), warm air streaks rising | Show the mechanism |
| 10 | crazy | Wide sky, slow roll | Re-hook |
| 11–12 | air | Glass cube draws around the cloud; water vs air bars | The twist made visible |
| 13 | feather | Feather drifts down past the cloud, camera returns to the hook frame | Loop |

## 7. Lighting
Sun 4.0 warm (1.0, 0.93, 0.82) from camera-left-back for rim light on the cloud; sky dome fills the
shadows blue. Inside the cloud: warm key light (small, crisp) so droplets sparkle; gradient fog from
warm top to cool bottom. No blown-out whites on the subject.

## 8. Sound
Warm major-key bed (C–G–Am–F, 96 bpm), soft keys, ~6 dB under the voice and ducked further while she
speaks. SFX only on: scale takes the weight, herd reveal, entering the cloud, twist hit, cube appears.
No constant noise, no clicks, every sound fades out. Final mix −14 LUFS, peak ≤ −1 dB.

## 9. Quality control (every frame)
**Automated, on the final MP4:**
1. Unplanned jumps / freezes / black frames (`qa_motion.py`, `blackdetect`, `freezedetect`).
2. **Cut frames:** the first frame of every shot must already belong to the new shot.
3. **Flicker:** frame-to-frame brightness spikes inside a shot.
4. **Pops:** an object appearing/disappearing mid-shot shows up as a one-frame spike.
5. Loudness and peak; Whisper transcript of the final mix = script.

**Manual:** contact sheets of **every frame** (804 frames, 100 per sheet), reviewed one by one for:
popping objects, wrong visibility, clipping through geometry, text overlapping, unreadable text,
blown highlights, wrong colors, anything that would look "AI" or amateur. Plus 1:1 crops for sharpness.

## 10. Deliverables
MP4 (H.264, 1080×1920, 30 fps, AAC 192 k) · SRT · 3 thumbnails · title, alternatives, description,
tags, hashtags · QA report.
