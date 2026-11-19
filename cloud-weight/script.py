"""Narration: 'This Fluffy Cloud Weighs Over a Million Pounds'.
(key, spoken text, on-screen caption, pause after). Captions: CAPS / digits = highlighted keywords.
Every number is checked in RESEARCH.md. Works in a flat, neutral voice (no irony, no colons).
The last line flows back into the first (loop).
"""

LINES = [
    ("hook",     "This fluffy cloud weighs over a million pounds.",
                 "This fluffy cloud weighs over 1 MILLION POUNDS.", 0.25),
    ("elephants", "That's as heavy as nearly a hundred elephants.",
                 "That's as heavy as nearly 100 ELEPHANTS.", 0.3),
    ("why",      "So why doesn't it fall?", "So why doesn't it FALL?", 0.3),
    ("droplets", "Its water is split into trillions of tiny droplets.",
                 "Its water is split into TRILLIONS of tiny droplets.", 0.2),
    ("light",    "Each one is so light that rising warm air holds it up.",
                 "Each one is so LIGHT that rising warm air holds it up.", 0.3),
    ("crazy",    "But here's the crazy part.", "But here's the CRAZY part.", 0.3),
    ("air",      "The air in the same space weighs over a thousand times more.",
                 "The AIR in the same space weighs over 1,000× MORE.", 0.25),
    ("feather",  "So it floats... even though...",
                 "So it FLOATS... even though...", 0.0),
]
