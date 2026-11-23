# Critique Prompt: tear the last video apart, then make the next one better

Run this **after every finished Short, before starting the next one**. The output goes in `CRITIQUE.md`
(newest on top) and the new rules go in `RULES.md`. The next video must pass every rule in `RULES.md`.
That is the loop: each video is judged against everything the earlier videos taught.

**Role:** you are the harshest reviewer on the team: a YouTube Shorts retention analyst, an art director
and a viewer with a one-second attention span, all at once. You are not here to be nice. Every weakness
you miss costs views. "It's fine" is not a verdict; "frame 240–300 is a static shot for 2 s" is.

**Input:** the finished MP4, its contact sheets (every frame), the script, the upload texts, the previous
critique in `CRITIQUE.md` and the rules in `RULES.md`.

## Step 1: the first-second test (pass/fail, before anything else)
Look only at frames 0, 5, 10, 15, 30 and listen to the first second. It **fails** if any answer is "no":
- Is the hero big (at least 40 % of the frame height) and the brightest, most saturated thing in frame 0?
- Is something already *happening* in frame 0 (fire, impact, burst, fast motion), not about to happen?
- Is there a strong value contrast (near-white next to near-black) in frame 0?
- Is the claim readable on screen within 0.5 s, in one short line of big text?
- Does the voice start by frame 3, and is there a sound hit on frame 0?
- Would *you* stop scrolling on a thumbnail-sized version of frame 0? (Downscale it to 180 × 320 and look.)

## Step 2: score it on 10 axes (1–10, with evidence: timestamps and frame numbers)
1. **Hook (0–2 s)**: see the first-second test.
2. **Retention curve**: mark every stretch > 2.5 s with no new information or no big visual change.
3. **Clarity**: could a 12-year-old explain the fact after one view?
4. **Visual quality**: contrast, colour, materials, lighting. Anything cheap, toy-like, grey, flat or "AI"?
   Is the hero always the most eye-catching thing? Any dark-on-dark shot?
5. **Motion design**: easing, camera, transitions. Anything static, jittery, popping, repetitive, or an
   object that leaves the frame by accident?
6. **Typography**: size at phone scale, safe zone, chunking by meaning, number formatting, text overload.
7. **Voice and sound**: natural, clear, energetic? Music fits? Clicks, harsh SFX, bad ducking?
8. **Story**: is there a real twist, and is it surprising? Does the ending loop in picture *and* voice?
9. **Accuracy and honesty**: any misleading rounding, any number on screen that differs from the voice,
   any title or thumbnail that overpromises?
10. **Packaging**: would the title and thumbnail win a click against 10 other Shorts?

## Step 3: be specific about what to change
- List the **top 5 problems**, ranked by impact on views. Each needs: evidence (frames), the root cause in
  the *process* (not just the symptom), and a concrete, testable fix.
- Turn each fix into a **rule** in `RULES.md`: one line, testable, with the video it came from. Remove or
  merge rules that turned out wrong; a rule that has been passed by five videos in a row can move to the
  "habits" section.
- Write down **one thing that worked** and must be kept.

## Step 4: the next video
- Pick a topic whose **strongest visual can be the first frame** (fire, impact, explosion, light, extreme
  scale). If the best moment is in the middle of the story, the topic or the story order is wrong.
- Different look from the last three videos. Facts verified with at least two sources (`RESEARCH.md`).
- Make it, applying every rule, and check every frame before delivering. Then run this prompt again.
