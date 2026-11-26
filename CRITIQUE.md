# Critique of "Engineers Fire Chickens at Airplanes" (run of CRITIQUE_PROMPT.md)

**First-second test: PASS.** Frame 0: the chicken bursting on the cockpit pane, feathers flying at the lens, cracks
spreading, "350 MILES PER HOUR" on screen, impact on frame 0. At 180 × 320 it reads as "a chicken just hit a plane".

**WHY test: PASS.** Spoken at 4.3 s ("Why do they do it? Birds hit planes about sixty times a day"), with a big "WHY?"
title over an airliner flying through gulls, a 0 → 60 counter, then Flight 1549 and the 75 mph windshield.

| # | Axis | Score | Evidence |
|---|---|---|---|
| 1 | Hook | 9 | Absurd premise + destruction on frame 0 + big number. |
| 2 | Retention | 8 | Something happens every second; S5 (cockpit window, 2 s) is a slow push-in on a static nose. |
| 3 | Clarity | 9 | Scale reads 4.0 LB, 35 PSI pill, red X on the ice block, "ALL 155 ON BOARD LIVED". |
| 4 | Visual quality | 7 | Lab, impact and glass shards are crisp; the gulls close to the lens in S2 read as pale blobs; the old pane is invisible before it breaks. |
| 5 | Motion design | 8 | Chicken flight, shards at the camera, melt; S5 is camera-drift only. |
| 6 | Typography | 9 | Pills and counters clean, no chunk shrank, labels clear of captions. |
| 7 | Voice and sound | 8 | Tempo as the lightning video; cannon, impact, gulls, honks, engine bangs, beeps, clunks, drips all on events. |
| 8 | Story | 9 | What → WHY (60/day, 1549) → old windshields → the rule → the test → twist (not frozen) → loop "That's why, before you fly, → engineers fire chickens…". |
| 9 | Accuracy | 9 | FAA 2024 (61/day), NTSB AAR-10/03, 14 CFR 25.775, chicken-gun history; "at 350 mph" is a typical test speed (stated in the description). |
| 10 | Packaging | 9 | "CHICKEN VS PLANE" on the impact frame. |

**Fixed during QA:** the "AIR CANNON" label in S1 sat on the nose (the barrel axis projects behind it) → removed; the
breech shot hid the chicken behind a full-length foam sabot while the label said "REAL CHICKEN" → sabot made a thin
pusher plate, camera moved to the side, loading slowed so the bird is visible under the label; one stale frame (673)
at the shot boundary re-rendered.

# Critique of "Scientists Blast a Fuel Pellet With 192 Lasers" (run of CRITIQUE_PROMPT.md)

**First-second test: PASS.** Frame 0: the fuel capsule bursting inside the gold can, shards and sparks flying at the
lens, "192 LASER BEAMS" on screen, blast on frame 0. At 180 × 320 it reads as "something just exploded".

**WHY test (new user rule): PASS.** Spoken at 4.1 s ("Why do it? They want to build a star on Earth"), with a big
"WHY?" title, a star flaring in the chamber, then 5 s of why: Sun fusion, zero CO2, fuel from seawater.

| # | Axis | Score | Evidence |
|---|---|---|---|
| 1 | Hook | 9 | Destruction on frame 0 plus a big number; 192 beams converge 2 s later. |
| 2 | Retention | 7 | S9 (24.7–26.4 s) holds on the intact capsule for 1.7 s; S6 holds a white ball for ~1 s after the bars fill. |
| 3 | Clarity | 9 | Pellet next to a peppercorn; temperature bars (100 vs 27 million °F); energy bars 2.1 → 8.6 MJ. |
| 4 | Visual quality | 7 | Chamber, sun and drop read well; the fusion flash and the deuterium glow white-out their nuclei for ~0.5 s; S7 hohlraum is a near-static frame until the burn. |
| 5 | Motion design | 7 | Implosion, star birth and the burn are strong; S6/S9 rely on slow camera drift. |
| 6 | Typography | 9 | Counters and pills clean; no chunk shrank; labels clear of captions. |
| 7 | Voice and sound | 8 | Tempo as the lightning video; zaps, booms, ticks and falling beeps match events. |
| 8 | Story | 9 | What → WHY → how → record → twist ("years away") → loop line "That's why, over and over, → Scientists blast…". |
| 9 | Accuracy | 9 | NIF/LLNL numbers; "fuel from seawater" simplified (tritium from lithium, noted in the description). |
| 10 | Packaging | 8 | "192 LASERS VS 1 PELLET" is a clear curiosity frame. |

## Top 5 problems → fixes
1. **Close-up shots with nothing new for > 1 s** (S6 end, S9). → Rule: in a close shot, plan a visible event (beam
   flash, spark, label pop) at least every 1 s; check the event list per shot before rendering.
2. **Emissive flashes white out the hero** (fusion flash, deuterium glow). → Rule: a flash may cover the hero for
   ≤ 0.3 s; keep glow alpha ≤ 0.5 over the subject the label names.
3. **Render cost not measured before the full run** (chamber 160 s/frame at SPP 24). → Rule: time one frame per
   set before the full render; when > 60 s, test SPP 12 against 24 (OIDN) and the costliest objects.
4. **Static establishing frame before the burn** (S7). → Rule: the camera travels ≥ 15 % of the subject distance or
   the subject animates in every shot longer than 1.5 s.
5. **Simplified science claim** ("fuel from seawater"). → Keep the short claim only if the description gives the
   full fact in one sentence.

# Critique of "NASA Slammed a Spacecraft Into an Asteroid" (run of CRITIQUE_PROMPT.md)

**First-second test: PASS.** Frame 0: Dimorphos bursting with boulders and a bright dust cone flying at the lens,
"14,000 MILES PER HOUR" on screen, impact boom on frame 0. At 180 × 320 it reads as "something exploded in space".

| # | Axis | Score | Evidence |
|---|---|---|---|
| 1 | Hook | 9 | Destruction on frame 0 plus a big number; a current topic (Hera arrived this month). |
| 2 | Retention | 7 | S1 (frames 73–154) is a slow wide of the settling plume for 2.7 s with only the caption changing. |
| 3 | Clarity | 8 | Orbit clock 11 H 55 → 11 H 22 makes "33 minutes" concrete; in S2 Dimorphos is tiny (≈ 3 % of the height), so the reticle has to carry it. |
| 4 | Visual quality | 8 | Rubble piles read well up close (S6/S7); S5 is very dark and the Hera bus sits right behind the caption. |
| 5 | Motion design | 7 | S7's accelerating POV into the boulders is strong; S1 and S2 are almost static. |
| 6 | Typography | 9 | Counters (clock, 0 → 6,000 miles) and pills read cleanly; no chunk shrank. |
| 7 | Voice and sound | 8 | Event-synced; proximity beeps accelerate into the cut. |
| 8 | Story | 9 | News peg + twist ("no crater") + loop line "All because → NASA slammed…". |
| 9 | Accuracy | 9 | Peer-reviewed numbers; "may be" hedges the reshape claim until Hera's images. |
| 10 | Packaging | 8 | Impact thumbnail is bright; the no-crater grid thumbnail is a strong curiosity alternative. |

## Top 5 problems → fixes
1. **Hero too small in establishing shots** (Dimorphos in S2). → Rule: the subject the voice names is ≥ 10 % of the
   frame height, or the shot pushes in to that size within 1 s.
2. **Slow wide after the hook** (S1). → Rule: the second shot keeps moving: camera travel ≥ 15 % of the subject
   distance, or a new event, at least every 1 s (the existing rule, now also checked on the second shot).
3. **Hero hidden behind the caption** (Hera in S5). → Rule: project the hero's bounding box per frame and keep it
   out of the caption band (y ≈ 1300–1540).
4. **Dark shots on a dark sky** (S5). → Rule: the hero's mean luminance ≥ 0.25 after grading; add a rim light if not.
5. **Seam needs a cut instead of continuous motion** when the story ends on the cause. → Accept a hard cut only if
   the same on-screen title spans the seam and the motion direction continues (here: rushing in → burst outward).

# Critique of "This Corn Kernel Explodes Inside Out" (run of CRITIQUE_PROMPT.md)

**First-second test: PASS.** Frame 0: a big foam flake bursting out of the kernel, hull chips and crumbs flying at
the lens, "356°F" on screen, burst sound on frame 0. At 180 × 320 it reads as "popcorn exploding".

| # | Axis | Score | Evidence |
|---|---|---|---|
| 1 | Hook | 9 | Destruction on frame 0, as the user asked after the glass drop. |
| 2 | Retention | 7 | S1 (frames 69–141) shows a finished flake with no new action for 1.3 s; S3's steam dots carry the section. |
| 3 | Clarity | 9 | Water → steam → 9× → crack → 40× → flip → pop explains the whole mechanism. |
| 4 | Visual quality | 8 | Foam reads as popcorn; the section is clean; the S5 side view is dark at the bottom. |
| 5 | Motion design | 6 | First render: the loop shot's camera flew away (44 empty frames). The flip is hard to read at speed. |
| 6 | Typography | 8 | Pressure counter reads well; one caption chunk was too long and shrank (split). |
| 7 | Voice and sound | 8 | Event-synced throughout; tempo matches the lightning video. |
| 8 | Story | 9 | Two surprises (backflip, the pop isn't the shell) and a natural loop line. |
| 9 | Accuracy | 9 | Numbers from peer-reviewed papers, °F. |
| 10 | Packaging | 8 | Bright flake + debris thumbnail. |

## Top 5 problems → fixes
1. **Camera functions evaluated outside their designed range** (cam0 at negative time in the loop shot). →
   Rule: print the camera position for every frame of the loop shot (and any shot that reuses another shot's
   camera) before rendering; any curve used at negative time needs a bounded, C1-smooth extension.
2. **Long caption chunks shrink below readable size.** → Rule: ≤ 3 words or ≤ 18 characters per chunk.
3. **Labels on the caption line** ("1 KERNEL"). → Rule: labels stay ≥ 120 px above the caption block.
4. **Fast acrobatics in a wide shot read weakly** (the flip). → Rule: a key motion gets a camera that is close
   enough that the hero is ≥ 35 % of the frame height during the motion.
5. **Idle stretch after the hook** (S1 settling). → Rule: every shot has a new on-screen event at least every 1 s.

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
