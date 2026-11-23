# Rules ledger

Every new Short must pass every rule here. `CRITIQUE_PROMPT.md` adds rules after each video; the source
video is in brackets. Check them off in the video's `UPLOAD.md` QA section.

## First second
- [ ] Frame 0: the hero fills at least 40 % of the frame height (or 80 % of the width for a wide object), is the brightest thing on screen, and is already in action (fire, impact, burst). (Everest: the mountain was small and grey in a dark frame)
- [ ] Frame 0 has near-white next to near-black and one saturated hero colour. (Everest, cloud)
- [ ] One big number or claim on screen from frame 0, at most 2 short lines. (moon)
- [ ] Voice starts by frame 3; a sound hit on frame 0. (moon)
- [ ] Frame 0 downscaled to 180 × 320 still reads instantly. (Everest)

## Retention
- [ ] A cut or a big visible change at least every 2.5 s; no set longer than ~4 s. (cloud, Everest: the pillar waited 2 s for the weight)
- [ ] No dark-on-dark shots: every shot has a clear bright area. (Everest: the "sunlight runs out" shot was dark blue on black)
- [ ] Each shot shows the thing the voice says *at that moment*. (cloud)

## Picture
- [ ] Sharp: no motion blur, grain or upscaling. (moon)
- [ ] The hero never leaves the frame by accident; frame big impacts so the object stays whole. (Everest: the 8-ton weight filled the frame)
- [ ] Particles (dust, smoke) stay subtle: alpha ≤ 0.15, never solid blobs. (Everest)
- [ ] Labels ≥ 44 px, numbers ≥ 96 px, inside the safe zone. (cloud)

## Words and sound
- [ ] Captions chunked by meaning (`|` in the script), synced to the words. (cloud)
- [ ] Every number on screen matches the voice and the research exactly (no 35,880 for 35,876). (Everest)
- [ ] Voice ~8 % faster than default; no repeated phrases. (moon)
- [ ] Loop in picture and voice: the last line flows grammatically into the first, checked with Whisper on two looped plays. (moon)
- [ ] Loudness −14 LUFS; no clicks at the seam. (moon)

## Habits (passed five videos in a row)
- Facts from two sources in `RESEARCH.md`; US units.
- Deliver mp4 + srt + 3 thumbnails + UPLOAD.md.

## Added after user feedback (diamond video)
- [ ] Voice speed like the lightning video (atempo 1.08); never speed up further to fit a length: cut words instead. (user)
- [ ] Sound follows the picture: every visible event (impact, spark, molecule, pencil stroke, light sweep) gets its own sound at its exact time, driven by the same event list in `timeline.py` as the scene; ambience beds follow the set on screen. (user, lightning video)

## Added after the diamond video
- [ ] A glowing/burning hero keeps a saturated rim (clearly orange/red) with only the core near-white; check the hue at 180 × 320. (diamond: the hot gem read peach)
- [ ] In every shot the object the voice names fills ≥ 25 % of the frame height. (diamond: the ring's stone was ~8 %)
- [ ] A set longer than 3 s gets a clear change of scale or angle halfway. (diamond: the CO2 shot)
- [ ] Emissive heroes keep surface detail (facet edges, normal-based variation). (diamond)
- [ ] post.py asserts label ≥ 44 px and number ≥ 96 px font sizes. (diamond)
