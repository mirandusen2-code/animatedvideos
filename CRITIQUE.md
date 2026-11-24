# Critique of "This Glass Drop Just Exploded" (run of CRITIQUE_PROMPT.md)

**First-second test: PASS.** Frame 0: the photoelastic rainbow head is mid-burst, glitter flying up, "3,000+ MPH"
on screen and a whoomp + crackle on frame 0. At 180 × 320 it reads as "a glass bubble exploding".

| # | Axis | Score | Evidence |
|---|---|---|---|
| 1 | Hook | 9 | Climax on frame 0, saturated rainbow on navy. |
| 2 | Retention | 7 | Cuts every 1.7–5 s; S2 (section, 5.1 s) is long but keeps changing (swing, arrows pulsing, 50 TONS). S0 ends on 1.5 s of settling powder with an empty top half (frames 70–122). |
| 3 | Clarity | 9 | Drip → skin vs core → hammer → snip tells the mechanism in order. |
| 4 | Visual quality | 8 | Glass and powder look premium; the section is clean but flat (peach core, no depth). |
| 5 | Motion design | 7 | First render: the hammer left the frame and never touched; the cutters crossed the camera as a grey slab. Both fixed by re-rendering 122 frames. |
| 6 | Typography | 8 | Big counters read well; the head label sits close to the caption in S3. |
| 7 | Voice and sound | 8 | Event-synced (splash, sizzle, squeeze thumps, clang, warning beeps); "Snip it" sounds close to "snippet". |
| 8 | Story | 9 | Strong paradox (hammer-proof vs. one snip) and a natural loop line. |
| 9 | Accuracy | 9 | Crack speed and stress from peer-reviewed sources, US units. |
| 10 | Packaging | 8 | "IT JUST EXPLODED" thumbnail is bright and clear. |

## Top 5 problems → fixes
1. **A prop that swings leaves the frame** (hammer, frames 394–428 in render 1). → Rule: compute the arc of every
   swinging/moving prop against the camera frustum before rendering; the prop stays fully in frame while the
   voice talks about it.
2. **An impact that never visibly makes contact** (hammer stopped above the head). → Rule: an impact holds
   visible contact for ≥ 2 frames and rebounds less than its own size.
3. **Props crossing the lens during a fast camera move** (cutter slab, frames 542–546). → Rule: when the
   camera dives or whips, props that are done get moved out of the way first.
4. **Dead time after the hook** (frames 70–122: powder settling, top half empty). → Rule: the hook shot ends
   within 0.5 s after its action is over, or the camera re-frames on what is left.
5. **Homophone at the loop line** ("Snip it" ≈ "snippet"). → Rule: check the loop line with Whisper alone and
   in the seam; rephrase words that ASR merges.

**Keep:** low-res preview renders of the risky frames before a full re-render (cheap, caught both fixes);
event-synced sound; frame 0 = the climax.

---

# Critique of "This Diamond Is Burning Into Thin Air" (run of CRITIQUE_PROMPT.md)

**First-second test: PASS.** Frame 0: the white-hot diamond fills ~45 % of the frame height, it is the
brightest object, sparks are flying, "1,500°F" is on screen and a flame burst hits on frame 0. At 180 × 320
it still reads as "a glowing gem on fire". Weak point: the hot diamond reads peach/beige rather than
blazing orange, so it looks more "lit" than "burning".

| # | Axis | Score | Evidence |
|---|---|---|---|
| 1 | Hook | 8 | Passes the test; colour is a little pastel (frames 0–100). |
| 2 | Retention | 7 | Cuts every 1–4 s. S4 (frames 336–459, 4.1 s) is one set with slow molecules; S5 ring (459–544) is a slow push-in. |
| 3 | Clarity | 8 | Burn → atoms → CO2 is clear; "slowly turning into pencil lead" needs the pencil shot to land (it does). |
| 4 | Visual quality | 7 | Atoms and ring look premium; the hot diamond's faceting is flat (frames 250–330), the dish reads as a white plate. |
| 5 | Motion design | 7 | Clean easing; the ring shot is centred and static; the time-lapse light sweep is subtle. |
| 6 | Typography | 8 | Big counters read well; "100% CARBON ATOMS" and the pill labels are on the small side. |
| 7 | Voice and sound | 9 | Lightning-speed voice and event-synced SFX (torch, sizzle, molecule plops, pencil scratch, day sweeps). |
| 8 | Story | 9 | Strong twist ("diamonds aren't forever"), natural loop line. |
| 9 | Accuracy | 8 | Honest, but "1,500 degrees" is near the top of the ignition range; the years counter is illustrative. |
| 10 | Packaging | 8 | "THIS DIAMOND IS BURNING" thumbnail is bright and clear. |

## Top 5 problems → fixes
1. **Hot hero reads pastel, not fiery** (frames 0–100, 280–335). Root cause: emission mixed toward white over
   the whole surface. → Rule: a burning/glowing hero keeps a saturated rim (hue clearly orange/red) and only
   its core goes white; check the hue in a 180 × 320 downscale.
2. **Ring shot: hero too small** (frames 459–544: the diamond is ~8 % of the frame). → Rule: in every shot
   the object the voice names is ≥ 25 % of the frame height.
3. **One set for 4 s** (S4). → Rule: a set longer than 3 s needs a camera move with a clear change of
   scale or angle halfway.
4. **Flat faceting when hot** (frames 250–330). → Rule: emissive heroes keep surface detail (facet edges,
   normal-based variation); no flat-shaded glow.
5. **Small pill labels** (S1, S2). → Rule from the cloud video still applies (labels ≥ 44 px) — enforce it
   in post.py with an assert, not by eye.

**Keep:** event-synced sound design from one shared event list; frame 0 = the climax of the story; a twist
that reframes something the viewer owns (their ring).

---

# Critique of "Mount Everest Would Vanish in the Ocean" (run of CRITIQUE_PROMPT.md)

**First-second test: FAIL.** Frame 0 shows a small grey mountain (about 15 % of the frame height) in a dark
blue scene; the brightest thing is the "29,032 FT" text, not the hero. Something is happening (the
splash), but at thumbnail size it reads as "a small rock on a table".

| # | Axis | Score | Evidence |
|---|---|---|---|
| 1 | Hook | 5 | See above. The splash is small and white-on-teal, low contrast. |
| 2 | Retention | 6 | 6.2–10.0 s (frames 186–300): Everest sits still on the floor for almost 4 s; 12.6–14.7 s: the pillar waits 2 s for the weight. |
| 3 | Clarity | 9 | The comparison is instantly clear: mountain in the trench, mile of water above. |
| 4 | Visual quality | 6 | Real terrain is great, but 10.0–12.6 s is dark blue on black; the sunbeams barely read. Red cut faces look odd on a phone. |
| 5 | Motion design | 7 | Smooth, but every shot is a slow creep; the weight impact first filled the whole frame (fixed). |
| 6 | Typography | 8 | Big numbers read well; the depth counter was 4 ft off (fixed). |
| 7 | Voice and sound | 8 | Clear and energetic; the falling swoosh into the loop works. |
| 8 | Story | 8 | Good escalation (depth → darkness → pressure); the loop line is natural. |
| 9 | Accuracy | 9 | Real DEM data, sourced numbers. |
| 10 | Packaging | 7 | Thumbnails are dark; "7 MILES DEEP" is the strongest. |

## Top 5 problems → fixes
1. **Weak frame 0** (hero small, grey, dark). Root cause: the topic's most dramatic moment (the drop) was
   framed wide to show scale. → Rule: hero ≥ 40 % of frame height, brightest object, already in action.
2. **Dark-on-dark shot** (frames 300–378). Root cause: "darkness" was shown literally. → Rule: every shot
   keeps a bright area; show darkness by contrast, never by an all-dark frame.
3. **Static stretches** (frames 186–300, 378–440). → Rule: a visible change every 2.5 s.
4. **The impact framing** (frames 442–450). Root cause: the camera was set on the resting pose, not the
   moving one. → Rule: frame big impacts so the object stays whole; check impact frames at full size.
5. **Number mismatch** (35,880 vs 35,876). → Rule: on-screen numbers match the voice exactly.

**Keep:** real-world data for the hero, the recurring big-number overlay, the falling-object loop.

---

# Critique of "This Fluffy Cloud Weighs Over a Million Pounds" (run of CRITIQUE_PROMPT.md)

| # | Axis | Score | Evidence |
|---|---|---|---|
| 1 | Hook | 7 | Strong claim in the first words, but frame 0 is almost static (the drop onto the hook is small). |
| 2 | Retention | 5 | **8.5–16.0 s (frames 255–480) are all inside the cloud:** 7.5 s of grey-on-grey droplets, a third of the video, with only one small label. Classic middle sag. |
| 3 | Clarity | 8 | The fact and the "why" are clear. The water-vs-air bars are too small to read at a glance. |
| 4 | Visual quality | 6 | Elephants are blobby, hills low-poly, the sky turns grey near the horizon, the inside-cloud shots are low-contrast. It reads "toy", not "premium". |
| 5 | Motion design | 7 | Smooth and clean, but every shot is a slow creep; few motion-graphics moments. |
| 6 | Typography | 6 | Labels (36 px) and bar labels are too small on a phone; some caption chunks split by word count, not meaning ("THE AIR" / "IN THE SAME" / "SPACE WEIGHS OVER"). |
| 7 | Voice and sound | 8 | Natural voice, clean mix. Music is generic. |
| 8 | Story | 8 | Good twist (the air is heavier); loop line works. |
| 9 | Accuracy | 9 | All numbers sourced; "nearly 100" kept honest. |
| 10 | Packaging | 7 | Title is clear but long; the best thumbnail (the herd) is not the recommended one. |

## Top 7 problems → fixes
1. **Middle sag (7.5 s in one grey set).** → No set may run longer than ~4 s, and every 2–3 s there must
   be a *visible* change: new set, new scale, an animated infographic, or a big number.
2. **Low contrast / grey shots.** → Each shot needs a clear value range (a dark and a bright area) and one
   saturated hero colour. No flat grey backgrounds.
3. **Small on-screen info.** → Labels ≥ 44 px, numbers ≥ 96 px, bar/diagram text ≥ 44 px. One message per graphic.
4. **Captions chunked by word count.** → Write caption chunks **by meaning** in the script (a `|` marks a
   chunk break). Never 3 random words.
5. **Static first frame.** → Frame 0 must already contain motion *and* the subject of the claim.
6. **Toy-like assets.** → Choose topics whose hero objects can look premium with procedural modelling
   (landscapes, water, rock, metal, light), and spend detail on the hero only.
7. **Slow renders limit iteration.** → Prefer stylized, emission-driven looks (cross-sections, glowing
   diagrams, dark backgrounds) that render fast, so there is time to fix things.

## Rules added for the next video
- Max ~4 s per set; a visible change every 2–3 s.
- High contrast + one saturated hero colour per shot.
- Labels ≥ 44 px; one animated infographic (ruler, counter or diagram) as a recurring "anchor".
- Caption chunks by meaning (`|` in the script).
- Frame 0 moves.
- Stylized cross-section / diorama look that renders fast.

## The next video (chosen by these rules)
**"If you dropped Mount Everest into the deepest part of the ocean, its peak would still be over a mile
underwater."** A diorama cross-section of the ocean: bright sky, blue water getting darker with depth, a
glowing depth ruler as the recurring infographic, Everest sinking into the Mariana Trench. Twist: over
6,000 people have stood on top of Everest; fewer than 30 have been to the bottom of the trench.
