"""Narration: 'This Shrimp Can Punch Hard Enough to Break Glass'.
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...One punch. Two hits." -> "This shrimp can punch hard enough to break glass."
"""

LINES = [
    ("hook",     "This shrimp can punch hard enough to break glass.",
                 "This shrimp | can PUNCH | hard enough | to break GLASS.", 0.25),
    ("speed",    "Its club swings out at fifty miles per hour,",
                 "Its club swings out | at 50 MILES | per hour,", 0.1),
    ("blink",    "faster than you can blink,", "faster than | you can BLINK,", 0.1),
    ("snail",    "smashing snail shells in a single hit.", "SMASHING snail shells | in a single HIT.", 0.35),
    ("crazy",    "But here's the crazy part.", "But here's | the CRAZY part.", 0.3),
    ("bubbles",  "The punch is so fast, the water rips open into bubbles.",
                 "The punch is so fast, | the water RIPS open | into BUBBLES.", 0.2),
    ("collapse", "When they collapse, they hit a second time,",
                 "When they COLLAPSE, | they hit | a SECOND time,", 0.1),
    ("heat",     "with a flash of light and heat over seven thousand degrees Fahrenheit.",
                 "with a FLASH | of light and heat | over 7,000 DEGREES | Fahrenheit.", 0.3),
    ("loop",     "One punch. Two hits.", "ONE punch. | TWO hits.", 0.0),
]
