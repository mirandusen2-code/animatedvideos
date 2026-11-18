# Viral Shorts Playbook: 3D Fact Animations (Blender)

*This is the output of [`research-prompt.md`](research-prompt.md), run on 2026-11-18.*

> **Honesty note:** YouTube publishes almost nothing about hook performance. Most of the numbers below
> come from creator-tool blogs. They are labelled **[data?]** (a claimed statistic with no primary source),
> **[opinion]** (a consensus among creators) or **[official]** (from YouTube itself). The only reliable way
> to know what works is your own *Viewed vs. swiped away* stats in YouTube Studio.

---

## 1. What the algorithm actually looks at

- **[official]** YouTube Studio shows **"Shown in feed"** and **"How many chose to view"**, which is the
  share of viewers who watched your Short instead of swiping away. YouTube does not publish thresholds,
  so that people can't game the system. ([OutlierKit, quoting YouTube Help](https://outlierkit.com/resources/youtube-shorts-algorithm/), [vidIQ](https://vidiq.com/blog/post/youtube-shorts-algorithm/))
- **[official]** Shorts can be up to **3 minutes** long (since Oct 2024). Vertical **9:16**.
  ([Podcastle](https://podcastle.ai/blog/how-long-can-youtube-shorts-be), [Async](https://async.com/blog/how-long-can-youtube-shorts-be/))
- **[opinion]** The algorithm reportedly still works best for Shorts **under 60 s**, and longer ones are "still
  being optimized". This could not be verified. ([Shortimize](https://www.shortimize.com/blog/how-does-youtube-shorts-algorithm-work))
- **[data?]** "A swipe-away rate over 40% in the first 3 s kills distribution." No YouTube source backs this up.
  Use it only as a rough guide. ([Shortimize](https://www.shortimize.com/blog/how-does-youtube-shorts-algorithm-work))
- **[opinion]** **Replays/loops** are seen as one of the strongest signals for distribution.
  ([virvid.ai](https://virvid.ai/blog/looping-structure-shorts-retention-2026), [Subscribr](https://subscribr.ai/p/scripting-youtube-shorts-engagement))
- **[official, policy]** **Monetization risk for faceless channels:** since **July 15, 2025**, YouTube
  demonetizes "inauthentic" content, meaning mass-produced, repetitive or template videos (for example an AI voice
  over stock clips). AI-assisted videos *are* allowed if they add original value.
  ([Plagiarism Today](https://www.plagiarismtoday.com/2025/07/08/youtube-targets-inauthentic-content/), [Windows Central](https://www.windowscentral.com/software-apps/youtube-ramps-up-campaign-against-ai-slop-with-stricter-monetization-caveats-on-inauthentic-and-repetitive-videos), [TheDesk 2026](https://thedesk.net/2026/07/youtube-clamps-down-low-quality-ai-slop/))
  → **This is why making your own 3D scenes in Blender is an advantage, and why you should use your own voice or
  a clearly edited, scripted voiceover.**

## 2. The hook (first 1–3 seconds)

- **[opinion]** The hook must land within **1–2 s**. One guide puts the decision point for Shorts at about 2 s.
  ([dev.to Hook Engineering](https://dev.to/bulkdl/hook-engineering-the-science-of-the-first-3-seconds-in-short-form-video-2026-2jp9), [Opus](https://www.opus.pro/blog/youtube-shorts-hook-formulas))
- **[data?]** Curiosity-gap hooks reportedly had the best 3-second hold (~68%, from one creator's
  own tests). The target is **70%+ still watching after 3 s**. ([Opus](https://www.opus.pro/blog/youtube-shorts-hook-formulas), [Virlo](https://virlo.ai/blog/why-the-first-few-seconds-matter))
- **[opinion]** Show something visual **and** say a line at the same time: the text, the voiceover and the image
  should all deliver the same promise.

### 16 hook templates (most useful first for 3D fact videos)

| # | Type | Template | Example |
|---|------|----------|---------|
| 1 | What-if | "What if you ___?" | "What if you jumped into a hole through the Earth?" |
| 2 | Shock number | "___ is so ___ that ___." | "A neutron star is so dense one teaspoon weighs billions of tonnes." |
| 3 | Curiosity gap | "This is why ___ (and it's not what you think)." | "This is why wombats poop cubes." |
| 4 | Contrarian | "You've been lied to about ___." | "You've been lied to about the color of blood." |
| 5 | Intro + twist | "This is a ___. It can ___." | "This is a tardigrade. It can survive in space." |
| 6 | Timeline | "In ___ seconds/minutes, ___." | "In 38 minutes you'd come out the other side of the Earth." |
| 7 | Question | "Why does ___?" | "Why doesn't a plane fly in a straight line?" |
| 8 | Comparison | "___ is older than ___." | "Sharks are older than trees." |
| 9 | Body/POV | "POV: you are ___." / "This is what happens to your body when ___." | "This is what happens to your body in space." |
| 10 | Impossible-sounding | "___ shouldn't exist, but it does." | "This lake shouldn't exist, but it does." |
| 11 | Stake | "If ___, you'd have ___ seconds." | "If the Sun disappeared, you'd have 8 minutes." |
| 12 | Secret | "Nobody talks about ___." | "Nobody talks about what's inside a banana." |
| 13 | Scale | "If ___ were the size of ___, ___." | "If the Earth were a basketball, the ocean would be thinner than paper." |
| 14 | Countdown | "3 things about ___ that sound fake." | "3 facts about the ocean that sound fake." |
| 15 | Mistake | "Stop ___. Here's why." | "Stop cracking your knuckles... or don't. Here's why." |
| 16 | Visual interrupt | (no words: a striking image in frame 1 + text) | The Earth is sliced open, with a little person on top. |

Sources for the patterns: [Opus](https://www.opus.pro/blog/youtube-shorts-hook-formulas), [faceless.so](https://faceless.so/blog/25-hook-formulas-to-keep-viewers-watching-1), [Nemo Video](https://www.nemovideo.com/blog/best-hook-formulas-video-scripts), [CapCut](https://www.capcut.com/create/short-form-video-hooks-first-3-second-patterns), [Social Media Examiner](https://www.socialmediaexaminer.com/youtube-shorts-hooks-and-curiosity-loops-that-explode-your-views/).

## 3. Video structure (~30–45 s)

The structure that keeps coming back in every source is **hook → context → payoff → loop-back** ([Subscribr](https://subscribr.ai/p/scripting-youtube-shorts-engagement), [faceless.so](https://faceless.so/blog/story-structures-for-short-form-video), [Clippie](https://clippie.ai/blog/viral-storytelling-formats-short-form-video)):

| Time | Part | What happens |
|------|------|--------------|
| 0–3 s | **Hook** | Striking image + promise/question. Don't explain anything yet. |
| 3–7 s | **Setup** | "Here's what happens…" Show the viewer where we're going. |
| 7–18 s | **Escalation** | Every 3–5 s something new happens (new layer, a number, zoom/cut). |
| ~18 s | **Re-hook** | "But here's the crazy part…" Opens a second loop. |
| 18–28 s | **Payoff** | The surprising explanation or the climax. |
| 28–35 s | **Loop ending** | The last sentence flows into the first ("…because if you jumped…"). No "subscribe!" at the end. |

- **[opinion]** Never resolve the topic in the first 5 s. ([Subscribr](https://subscribr.ai/p/scripting-youtube-shorts-engagement))
- **[opinion]** A call to action at the end ("check out my full video") lowers retention. ([virvid.ai](https://virvid.ai/blog/looping-structure-shorts-retention-2026))
- **[opinion]** Test: play your own Short 3× in a row. If the restart feels jarring, the loop needs work.

## 4. Retention checklist

1. Hook within 2 s: image + text + voice all make the same promise.
2. Change something visually every 2–4 s (camera move, cut, new element, zoom punch).
3. Big burned-in captions, 2–5 words at a time, with key words in a color.
4. A **live counter** or meter on screen (timer, speed, temperature). This creates tension.
5. One re-hook in the middle ("But here's the crazy part").
6. Numbers concrete and correct (38 min, 5,200 °C). **Always give US units too** (mph, °F, miles): the US is the biggest English-speaking audience. Credibility gets people to comment and share.
7. Sound design follows the image (whoosh, boom, riser before the twist).
8. Ending flows back into the first sentence, so the video loops.
9. Keep captions out of the bottom ~20% and the right edge (that's where the Shorts UI sits).
10. Keep a recognizable style (the same character, colors and font): that builds a brand, *not* repetitive slop.

## 5. Ten title formulas

1. What If You ___?
2. Why ___ Is Impossible (Almost)
3. This Is What Happens When ___
4. ___ Explained in 30 Seconds
5. The ___ Nobody Talks About
6. You've Been Lied to About ___
7. ___ vs ___: Which Is Worse?
8. How Long Would It Take to ___?
9. ___ Is Older Than ___
10. I Can't Believe ___ Is Real

Rule of thumb **[opinion]**: the title should *add* to the hook rather than repeat it word for word, and stay under ~50 characters.

## 6. Ten video ideas (true, visual, good in 3D)

| # | Idea | Hook | Title |
|---|------|------|-------|
| 1 | ✅ **Hole through the Earth** (made this one) | "If you jumped into a hole through the Earth, you'd come out in 38 minutes." | What If You Jumped Through the Earth? |
| 2 | A day on Venus is longer than its year (243 vs 225 Earth days) | "On Venus, your birthday comes before tomorrow." | The Planet Where a Day Lasts Longer Than a Year |
| 3 | Sharks are older than trees | "Sharks are older than trees." | Sharks Are Older Than Trees |
| 4 | Tardigrades survive the vacuum of space | "This is a tardigrade. It survived open space." | The Animal That Survived Space |
| 5 | Wombats poop cubes | "This animal poops cubes. On purpose." | Why Wombats Poop Cubes |
| 6 | Neutron star teaspoon (billions of tonnes) | "One teaspoon of this weighs more than a mountain." | The Heaviest Teaspoon in the Universe |
| 7 | Bananas are slightly radioactive (potassium-40) | "Your banana is radioactive." | Your Banana Is Radioactive |
| 8 | Sunlight is 8 minutes old, but its energy took thousands of years to leave the core | "The light hitting your face is older than civilization." | How Old Is Sunlight Really? |
| 9 | An octopus has 3 hearts and blue blood | "This animal has 3 hearts and blue blood." | Why Octopuses Have 3 Hearts |
| 10 | Your stomach lining renews itself every few days | "Your stomach is trying to digest itself right now." | Why Your Stomach Doesn't Digest Itself |

## 7. Best idea → full script

**"What If You Jumped Through the Earth?"** is a 35 s, 9:16 3D Short (rendered in Blender, see below).

Facts: in a frictionless tunnel through the center, the fall takes **~38 minutes** with Earth's real density
distribution (Klotz, *American Journal of Physics* 83, 231 (2015); a uniform Earth gives ~42 min). Top speed is
reached at the center (uniform model ≈ 7.9 km/s ≈ 28,400 km/h ≈ 17,600 mph; it's higher with the real density). The inner core
is ~5,200 °C (~9,400 °F), close to the Sun's surface (~5,500 °C / ~9,900 °F). Gravity is zero at the center.

| Time | Voiceover / caption | Shot (Blender) |
|------|---------------------|----------------|
| 0.0 | "If you jumped into a hole through the Earth," | Close-up of the North Pole: a little astronaut stands next to a hole in the cut-open Earth. Hook title on top. |
| 2.7 | "you'd come out the other side in just 38 minutes." | Jump → camera pulls back to the whole Earth with a wedge cut away. TIME/SPEED HUD appears. |
| 5.5 | "Here's what happens on the way." | Wide shot, "YOU" pointer, disclaimer. |
| 7.4 | "You fall faster and faster…" | Camera follows the astronaut down the tunnel. Label: CRUST. |
| 9.6 | "past the mantle, into liquid metal…" | Labels MANTLE / OUTER CORE. The astronaut slowly tumbles. |
| 12.1 | "to a center almost as hot as the Sun's surface." | Glowing inner core, label ~5,200 °C / 9,400 °F. |
| 15.1 | "By now you're going over 28,000 km/h… that's over 17,000 miles per hour!" | Speed meter at max, zoom punch + boom. |
| 18.2 | "But here's the crazy part:" | **Re-hook**: riser + hit. |
| 19.8 | "at the center, gravity pulls from every side…" | Passing the center. |
| 22.7 | "so now it starts slowing you down." | Speed bar drops. |
| 25.2 | "38 minutes later, you reach the other side…" | Camera at the South Pole. |
| 28.1 | "stop for a split second…" | Astronaut's head sticks out of the South Pole, speed 0. |
| 29.8 | "and fall all the way back." | Falls back in. |
| 31.5 | "Forever. Because… if you jumped into a hole through the Earth…" | Pull back to the wide shot → **loops** into the start. |

## 8. How to make it yourself

```bash
pip install bpy pillow numpy kokoro-onnx soundfile        # Blender as a Python module (bpy 5.x) + offline TTS
./render_all.sh frames/ 576x1024 4                        # renders 1050 frames (Cycles), fresh process per batch
# voiceover: a documentary-style male narrator (Kokoro voice "bm_george"); needs kokoro-v1.0.onnx + voices-v1.0.bin
# from https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
python3 voiceover.py models/ vo/                           # -> vo/vo.wav + vo/vo.json (captions follow the speech)
python3 post.py frames/ earth-tunnel-short-vo.mp4 vo/      # captions, HUD, music ducked under the voice -> MP4
```
- `post.py` remaps time so the picture follows the narrator (slows into the arrival, holds the "stop" moment).
- Other male voices to try: `am_michael` (warm, American), `am_fenrir`, `bm_fable`, `bm_lewis` (`python3 voiceover.py models/ vo/ am_michael`).
- For a better final version: render at `--res 1080x1920 --samples 16` on a PC with a GPU, and/or record
  **your own voice** following the captions (good for the monetization rules, see §1).
