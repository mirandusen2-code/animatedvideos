# Production Prompt: "This Fluffy Cloud Weighs Half a Million Kilos"

Same quality bar and rules as `neutron-star/PROMPT.md` (safe zone x 92–860 / y 300–1540, full 1080×1920
render, no upscaling, no grain, ≤3 s shots with a new angle each cut, captions 1–3 words ~72 px aligned to
the real speech with Whisper, music ~6 dB under the voice, SFX only on key moments, loop ending).

## Look (deliberately different from the dark space videos)
Bright daytime: deep-blue sky fading to a pale horizon, warm low sun, rolling green hills. One hero cumulus
cloud, soft and white with sunlit tops and slightly blue-grey shadowed bottoms. Props in clean "toy
museum" style: a giant brass crane scale, grey porcelain elephants (same porcelain as the figurines in the
neutron-star video: channel continuity). Palette: sky blue #2E6FD8, cloud white, sun amber #FFB547,
grass green #3E8E41, porcelain grey.

## Script (facts in RESEARCH.md)
| line | voice | picture |
|---|---|---|
| hook | "This fluffy cloud weighs half a million kilos." | Low angle: the cloud hangs from a giant crane scale; the needle swings to 500,000 kg. |
| pounds | "That's over a million pounds." | Close-up of the dial; counter `1,100,000 LB`. |
| elephants | "As heavy as nearly a hundred elephants." | Ground level across a herd of 100 porcelain elephants under the cloud → aerial grid. |
| why | "So why doesn't it fall?" | Push into the cloud (zoom-through). |
| droplets | "Its water is split into trillions of tiny droplets." | Inside the cloud: glittering droplets, shallow depth of field. |
| light | "Each one is so light that rising warm air holds it up." | Droplets bobbing on rising streaks of warm air. |
| crazy | "But here's the crazy part." | Music stops → low hit → wide sky, push-in with roll. |
| air | "The air in the same space weighs over a thousand times more." | A glowing glass cube draws itself around the cloud; bar comparison cloud vs air. |
| feather | "So next time a cloud looks as light as a feather..." | A feather drifts past the cloud → back to the hook frame (loop). |

## QA (all must pass)
Facts vs RESEARCH.md · Whisper: voice = script · captions aligned (0.00 s) · safe zone overlay ·
1:1 sharpness · `qa_motion.py` (no unplanned jumps/freezes) · −14 LUFS, no hiss · loop feels natural ·
"would I swipe at second 1? at second 10?"
