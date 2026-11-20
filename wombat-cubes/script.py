"""Narration: 'Wombats Poop Cubes'  (~19 s, seamless loop).
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...Scientists think that's why" -> "wombats poop cubes."
"""

LINES = [
    ("hook",    "Wombats poop cubes.", "WOMBATS | poop CUBES.", 0.3),
    ("real",    "Real cubes, with flat sides and sharp corners.", "Real CUBES, | with FLAT sides | and sharp CORNERS.", 0.25),
    ("gut",     "A wombat's gut has stiff spots and stretchy spots,", "A wombat's GUT | has STIFF spots | and STRETCHY spots,", 0.05),
    ("squeeze", "that squeeze the poop into corners as it dries.", "that SQUEEZE the poop | into CORNERS | as it DRIES.", 0.3),
    ("night",   "One wombat makes up to 100 cubes a night,", "One wombat makes | up to 100 CUBES | a NIGHT,", 0.05),
    ("turf",    "and leaves them on rocks to mark its turf.", "and leaves them | on ROCKS | to mark its TURF.", 0.3),
    ("roll",    "Round poop would just roll off.", "ROUND poop | would just ROLL OFF.", 0.3),
    ("loop",    "Scientists think that's why", "Scientists think | that's WHY", 0.0),
]
