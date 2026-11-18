# Production Prompt: "This Sugar Cube Weighs More Than Every Human on Earth"

> A full brief for a professional, viral 3D Short. Hand it to any 3D artist / AI agent; every decision is
> written down so the result is consistent, smooth and **does not look or sound AI-generated**.

---

## 0. Role & goal
You are a senior motion designer + documentary scriptwriter producing a **YouTube Short for the channel
MindBlown 3D** (mind-blowing facts, animated in 3D). Goal: maximum *viewed vs. swiped* and average % viewed,
with a loop that makes people watch twice. Quality bar: Kurzgesagt-level clarity, Apple-keynote-level
lighting, documentary narration. No clip-art, no stock look, no robotic voice.

## 1. The fact (must be 100% correct, with US + metric units)
| Claim | Value | Source |
|---|---|---|
| A sugar cube of neutron-star matter on Earth | ≈ **1 billion tons** (1 trillion kg) | NASA Imagine the Universe |
| Mass of all humans combined | ≈ **0.4–0.5 billion tons** | physicsworld / mass estimates (390–520 Mt) |
| Neutron star size | ≈ **20 km (12 miles)** across | NASA |
| Neutron star mass | up to **~2× the Sun** (typically ~1.4) | NASA / McGill |
| Fastest known spin | **716 times per second** (PSR J1748−2446ad) | McGill / NRAO |

→ "A sugar cube of it weighs **more than every human on Earth, combined**" is true with a 2× margin.
Never round in the wrong direction; never add unverified numbers (no "gravity is X billion times").

## 2. Hook (0–2 s): the one frame that stops the scroll
- **Visual:** a brass balance scale in a dark studio. On one pan: a single sugar cube. On the other: a
  **mountain of tiny human figurines**. The cube's side **slams down**. Cause and effect in 1 second.
- **Voice (first words, no intro):** "This sugar cube weighs more than every human on Earth… combined."
- **On-screen hook text (top):** `1 SUGAR CUBE > 8 BILLION PEOPLE`

## 3. Script (documentary voice, ~33 s, loops)
| t | Voice-over | Picture |
|---|---|---|
| 0.0 | "This sugar cube weighs more than every human on Earth… combined." | Scale slams down; slow push-in. |
| 4.0 | "Because it isn't sugar." | Macro of the cube, shallow depth of field. |
| 5.5 | "It's a piece of a neutron star." | The cube starts glowing ice-blue from within. |
| 7.5 | "When a giant star dies, its core collapses…" | Huge red star in space, shudders, implodes. |
| 11.0 | "…squeezing more mass than our Sun into a ball just twenty kilometers wide." | Supernova flash + shockwave → tiny blue-white neutron star. Label `20 KM · 12 MI`. |
| 16.5 | "About the size of a city." | Slow orbit around the neutron star. |
| 18.5 | **Re-hook:** "But here's the crazy part." | Beat of silence + low impact. |
| 20.0 | "Some of them spin over seven hundred times… every second." | Pulsar beams sweep, spin accelerates. Counter `716× / SECOND`. |
| 25.0 | "So one sugar cube of it, here on Earth, would weigh a billion tons." | Back in the studio, counter rolls to `1,000,000,000 TONS`. |
| 30.0 | "And that's why…" | The cube drops toward the empty scale pan → **cut to frame 0** (loop). |

Writing rules: short sentences, natural pauses ("…"), one idea per line, no filler ("Did you know"),
no "subscribe" at the end. The last line must flow into the first.

## 4. Art direction (anti-AI look)
- **One consistent world:** dark charcoal studio, warm key light, cool rim light; space shots in the same
  palette (warm red star → ice-blue neutron star). Accent colours: **amber #FFB547** and **ice blue #7FD8FF**.
- **Real materials:** brushed brass (metallic, roughness 0.3), sugar (subsurface + grain bump), porcelain
  figurines, glossy dark floor with soft reflections.
- **Cinematography:** every camera move eased (no linear moves), subtle hand-held drift, shallow depth of
  field on macro shots, motion-blur-like smoothness, cuts on narration beats.
- **Finish:** bloom on hot pixels, mild vignette, fine film grain, AgX colour management. No lens-flare spam.

## 5. Text & safe zones (YouTube Shorts, 1080×1920)
- Keep all text inside **x 64–880, y 250–1500**: top 250 px = search bar, bottom 420 px = title/channel/
  subscribe, right ~200 px = like/comment/share buttons. Verified against an overlay before export.
- Captions: **Montserrat Black, UPPERCASE, 1–3 words**, active word highlighted (amber), thick dark outline
  + soft shadow, centred at x≈472, just above the bottom safe zone. Groups never cross a pause.
- Labels as pill chips (≥ 56 px tall, ≤ 4 words). Key numbers as big animated counters, not paragraphs.
- Max 2 text elements on screen at once. Clean > busy.

## 6. Voice (must not sound robotic)
- Warm male documentary narrator (Kokoro TTS `am_michael`), pace ~150 wpm, real pauses at "…".
- Processing chain: high-pass 70 Hz → warmth +2.5 dB @ 180 Hz → presence +2 dB @ 3 kHz → de-esser →
  gentle compression (3:1) → short room reverb (very subtle) → limiter. Loudness **−14 LUFS**.
- Generate sentence by sentence so pauses and timing are controlled; captions follow the real audio.

## 7. Sound design & music
- Cinematic ambient bed (slow pad chords, sub pulse), **ducked under the voice**.
- Impacts on: scale slam, "neutron star" reveal, supernova, re-hook. Short whooshes on cuts only.
- **No constant noise/hiss**, no clicks, every sound fades out cleanly.

## 7b. Editing rhythm (from the Animation Master Engine guide, adapted)
- No shot longer than ~3 s; a new camera angle on every cut; the camera always creeps (never static).
- 3–5° roll on dramatic beats, 7-frame shake on impacts, 6-frame white flash on the time jump (supernova).
- The twist line ("But here's the crazy part") gets: music stops → low hit → push-in with roll.
- Sound effects only on key moments (landing, reveal, collapse, twist), music ~6 dB under the voice.
- QA: contact sheet of every shot's middle frame, safe-zone overlay, no frozen/black frames; deliver SRT.

## 8. Tools
- **Blender 5 (Cycles + OpenImageDenoise, AgX)** for all 3D; procedural modelling via Python (`bpy`).
- **Kokoro** (open-source neural TTS) for the voice; **ffmpeg** for voice processing, ducking & loudness.
- **Pillow/NumPy** post: captions, counters, bloom, grain; **H.264 1080×1920 30 fps**.

## 9. QA checklist before export
- [ ] Every fact matches §1 (metric + US units).
- [ ] No text in the button/caption dead zones (checked against a safe-zone overlay).
- [ ] Captions in sync with the voice; no caption longer than 3 words.
- [ ] Voice is clear above the music; no hiss/clicks; −14 LUFS.
- [ ] The loop is seamless (end → start).
- [ ] Watched as a viewer: would I swipe at second 1? At second 10? If yes, fix it.
