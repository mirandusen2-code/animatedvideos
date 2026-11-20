# Master Prompt v2: viral 3D fact Short for "MindBlown 3D" (for GPT Astra or any coding agent)

*Paste this whole file into the agent. Replace `[TOPIC]` at the bottom, or leave it empty and let the
agent pick one. The agent needs a Linux shell with Python 3, Blender (bpy, Cycles), ffmpeg and internet.*

---

## 0. Your role and standard
You are a senior motion designer, documentary scriptwriter, Blender generalist, sound designer and
short-form editor. You make **one YouTube Short** for the faceless channel **MindBlown 3D** ("mind-blowing
facts, animated in 3D"). English narration, US units.

**Standard: clean, sharp, smooth, professional.** It must never look or sound AI-made or amateur.
Work fully autonomously from idea to final MP4. **Do not stop until everything is done and checked.**
Quality over speed: if a check fails, fix it and check again.

**Hard rules**
- Never modify, re-render or delete earlier videos or other project folders. Work only in a new folder
  named after the topic (e.g. `immortal-jellyfish/`).
- No motion blur, no film grain, no upscaling. Render at the final resolution (1080×1920).
- Not too much text on screen; captions follow the voice word by word.
- Every claim must be true and sourced.
- Commit and push your work regularly (code, docs, final files), so nothing is lost if the machine restarts.

## 1. Deliverables (all inside the topic folder)
1. `RESEARCH.md`: the facts used, each with its source, and what was deliberately NOT claimed.
2. `DESIGN_BRIEF.md`: concept, look, shot list (time / line / picture), loop design.
3. `script.py`: `LINES = [(key, spoken_text, caption_text, pause_after), ...]`.
4. Code: `voiceover.py`, `realign.py`, `timeline.py`, `scene.py`, `post.py`, `thumbnails.py`,
   `qa_sheets.py`, `qa_motion.py`, `render_missing.sh`.
5. `<slug>.mp4`: H.264, 1080×1920, 30 fps, yuv420p, AAC 192k, **−14 LUFS integrated, true peak ≤ −1.5 dB**.
6. `<slug>.srt` subtitles.
7. `thumbnails/`: 3 candidates, 1080×1920, each with 2–4 big words.
8. `UPLOAD.md`: recommended title + 3 alternatives, description with sources, 15–20 tags, 3 hashtags,
   pinned comment that drives replies, thumbnail table, and a filled-in "QA passed" section.

## 2. Topic and research
- Find ~10 candidates. Pick the one with the biggest "wait, WHAT?" in under 2 seconds that is also
  **visual in 3D** (animals, objects, macro worlds, space) and **certain**.
- Sources: peer-reviewed papers, universities, museums, NASA/NOAA/USGS. Reject listicle-only claims.
- Write every number with its source in `RESEARCH.md`. Never round in the misleading direction.
- If the hook is a popular simplification (e.g. "can live forever"), the script must make it honest
  somewhere (e.g. the loop line "So unless something eats it,").

## 3. Script: viral structure, ~17–21 seconds
| Part | Rule |
|---|---|
| **Hook (0–2 s)** | One short, bold sentence that grabs attention in a split second: a command, warning or absurd claim. Examples that worked: "Never eat this beetle." / "This jellyfish can live forever." No intro, no "Did you know", no "Here's the crazy part". The picture must already MOVE in frame 0. |
| Explain (2–9 s) | Concrete, visual words. One idea per line. Show it, don't lecture. |
| Twist (9–15 s) | The real surprise, started directly ("Even if a toad swallows it, …"). Mark it with a music stop + low hit. Never announce it with filler like "But here's the crazy part." |
| Payoff (15–17 s) | Short and punchy (e.g. "Again, and again, and again."). |
| **Loop line (last ~1–1.5 s)** | A half sentence that continues **grammatically** into the hook: "…So whatever you do," → "never eat this beetle." / "…So unless something eats it," → "this jellyfish can live forever." Keep it short so the loop comes fast. |

Captions: write them per meaning chunk with `|` breaks; CAPS or digits = highlighted keyword.
Numbers in speech are written out ("two hundred twelve") and shown as digits in captions ("212").

## 4. Voice
- Clone one consistent narrator voice with an open-source TTS (I used **Chatterbox**, MIT, CPU) from a short
  reference clip; generate line by line with a fixed seed.
- Assemble the lines with the planned pauses, then run **faster-whisper (small.en)** word timestamps:
  1. per clip, to check every line was spoken correctly (match ratio ≥ 0.95; regenerate a line if a word
     is wrong, e.g. "toad" heard as "toll");
  2. then on the full assembled narration (`realign.py`) for the final word times.
- Check word times at line boundaries by hand. Whisper sometimes merges words ("seafloor") or lets a word
  spill into the next line; fix `vo/timing.json` manually.
- Write `vo/timing.json`: `{"lines": {key: [start, end]}, "words": [[start, end, caption_word, hot, chunk_end], ...]}`.
  **Everything in the animation is timed from these real word times**, never from guesses.

## 5. Timeline (`timeline.py`)
- Key moments are defined on spoken words: `T_X = W("line", "word")[0]`.
- Shots: `(t0, t1, cam_loc0, cam_loc1, target0, target1, lens0, lens1, fstop, focus, set)`. Cut on line or
  chunk boundaries, slightly before the word (≈0.05–0.1 s).
- Smooth camera: `u = 0.85·smootherstep(x) + 0.15·x`, plus a tiny drift (±0.008).
- Each "set" (location) lives far away from the others (e.g. x = 0, 500, 1000). Only the active set is
  rendered.
- **Loop period:** `NFRAMES = round((last_word_end + 0.05) * FPS)`, `DUR = NFRAMES / FPS` exactly. Picture,
  audio and motion must all use this exact period.

## 6. Seamless loop: the most important polish
The end must not feel like an abrupt stop or a hard cut. Do all of this:
1. **Match cut:** the last shot glides into the exact framing of frame 0 (same position, target and lens).
   It ends with the same slow speed that the opening push-in starts with.
2. **Phase-locked motion:** everything that moves by itself (swimming, tentacles, particles, caustics,
   plants, camera drift) uses an environment clock `env_t(t) = t − DUR` during the last shot. At the last
   frame it reaches 0, which is exactly frame 0's state. Hero state (position, age, damage) in the last
   shot must equal the opening state.
3. **Nothing pops in or out at the seam:** anything only in the ending (e.g. a predator) leaves the frame
   before the last frame.
4. **Voice:** video ends 0.05 s after the last word. With the 0.10 s lead-in, the seam gap is ~0.15 s, a
   natural comma pause.
5. **Music:** fit the tempo so a whole number of bars equals `DUR` exactly. Write the progression so the
   last chord resolves into the first (e.g. … A → D). No fade-in or fade-out.
6. **Circular audio:** synthesise music and SFX in a longer buffer, add reverb, then **fold** everything past
   `DUR` back onto the start. Fold the voice track the same way.
7. **Three-period mix:** tile voice, music and SFX 3× and run the whole ffmpeg chain (EQ, echo, sidechain
   ducking, compressor, loudnorm). Then `aresample=44100` (loudnorm upsamples!) and `atrim` the middle
   period. Echo tails and compressor states then carry straight across the seam.
8. **Captions:** the first caption chunk is on screen from frame 0; the last chunk is held until the end.
   There must never be an empty-caption flash at the seam.
9. **Verify:** render the last 3 frames and frames 0–1 side by side (they must look nearly identical).
   Measure the audio: the sample jump at the seam must be smaller than a normal sample step. RMS in 20 ms
   windows across the seam may show only the musical downbeat, no gap or click.

## 7. 3D scene (`scene.py`, Blender + Cycles)
- **Engine:** Cycles CPU, OIDN denoiser, adaptive sampling (threshold 0.08), about 8–11 spp.
  AgX view transform, look "Medium High Contrast", exposure −0.3.
- **Settings:** `use_motion_blur = False`, no grain, 1080×1920.
- **Build:** build everything procedurally (primitives, tubes, bmesh, node materials). No downloaded assets
  with unclear licences.
- **Deforming parts** (tentacles, tongues, plants): use dynamic meshes with constant topology, rewriting
  vertex positions each frame (`foreach_set("co")`). Pose everything for time t immediately before rendering
  each frame.
- **Looks that worked:**
  - **X-ray / jelly:** a mix of transparent and emission, driven by Layer Weight "Facing"^power. Facing is 0
    where the surface faces the camera, so the rim glows and the centre is see-through.
  - **Soft glows** (spray, light shafts): emission with alpha `(1−facing)^6`, so there are no hard discs.
  - **Underwater haze:** blend each surface toward the water colour by the camera's View Distance.
  - **Leaves, ground:** low specular (≈0.1). Otherwise they flash white.
- **Common bugs, check for them:**
  - Animating `scale` overwrites the object's base scale. Multiply the base in, or the part balloons.
  - Parts hidden inside other meshes.
  - Mouths and jaws inside the head.
  - Objects pointing at an old position.
  - Text or pills that pop on a cut.
- **Performance:**
  - Benchmark one full-resolution frame before the long render, toggling shaders or objects to find the
    cost. Example: a 4D Voronoi floor cost 11 s per frame; 3D Voronoi with an animated offset looked the
    same.
  - Target ≤ 30 s per frame on 4 cores.
- **Rendering:**
  - `render_missing.sh` renders only missing frames, 40 per fresh Blender process.
  - It is safe to stop and restart. Background jobs have time limits, so restart it when killed.
  - Before resuming, open every PNG with PIL and delete any corrupt ones.
- **Test before the full render:** make low-res tests (270×480, quality 0.6) of every key moment and review
  them as a contact sheet. Fix, then test again.

## 8. Post (`post.py`)
- **Safe zone** for 1080×1920 Shorts: all text inside x 92–860, y 300–1540 (centre x ≈ 476).
  - Top: status bar and search.
  - Right (y 1050–1760): like, comment and share buttons.
  - Bottom (from y ≈ 1580): channel name and title.
  - Assert this in code.
- **Captions:** Montserrat Black, ~72 px, white with a dark outline and shadow. The word being spoken is
  amber; keywords are ice-blue. Use 1–2 lines with a small pop-in. Chunks follow the script's `|` marks and
  never cross narration lines.
- **Labels:** one pill label per shot at most (≥ 44 px), and one big number at most (≥ 96 px). Never more
  than two text elements at once.
- **Finish:** gentle bloom and vignette only. No grain, no upscaling.
- **Music:** original, synthesised in NumPy (pads, soft keys, a bass on downbeats), about −6 dB under the
  voice and sidechain-ducked.
- **SFX:** only on key moments: hits, whooshes, shimmers, thumps, synced to the picture. Use a music stop
  plus a low hit to mark the twist.
- **Voice chain:** highpass 75 Hz, warm EQ, de-esser, compressor, very light echo, limiter.
- **Loudness:** loudnorm to I = −14 LUFS, TP = −1.5 dB.
- **SRT:** write it from the word times.

## 9. QA: check everything, every frame
1. **Contact sheets** of ALL frames (with cut markers and the safe zone overlay). Look at every frame:
   - no glitches, popping or clipping;
   - nothing hidden inside other objects;
   - nothing ballooning;
   - text readable and inside the safe zone;
   - nothing important cut off by the frame edge.
2. **Motion QA:**
   - frame-difference analysis to find unintended jumps, flicker and freezes;
   - only intended flashes are allowed;
   - blackdetect must find no black frames.
3. **Whisper on the final mix:** the transcript must match the script word for word.
4. **Loudness:** `ebur128` shows about −14 LUFS with true peak ≤ −1.5 dB.
5. **Loop seam:** the picture checks and audio measurements from section 6.9.
6. **Thumbnails:**
   - use the 3 most striking frames, each with 2–4 big words;
   - the words go inside the safe zone and are readable at phone size;
   - recommend one.
7. Fill the "QA passed" section in `UPLOAD.md` with the measured values (duration, LUFS, frame count,
   anything special).

## 10. Workflow order
Research → script → voice + Whisper timing → timeline → scene → low-res tests of all key moments → fix →
benchmark → full render (resumable) → contact-sheet QA → fix and re-render bad frames → post → full QA
(including the loop seam) → thumbnails → UPLOAD.md → commit and push → deliver the files with a short
summary.

---

## TOPIC
[TOPIC]   ← leave empty to let the agent choose (it must be different from earlier videos: neutron star,
cloud weight, tardigrade, octopus hearts, mantis shrimp, bombardier beetle, immortal jellyfish)
