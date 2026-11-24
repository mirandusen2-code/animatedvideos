# key, spoken text, caption text (| = chunk break by meaning, CAPS = highlight), pause after (s)
LINES = [
 ("hook", "This corn kernel explodes inside out at three hundred fifty-six degrees.",
  "This CORN KERNEL | EXPLODES | inside out | at 356°F.", 0.3),
 ("water", "Inside, a drop of water is trapped in a hard shell.",
  "INSIDE, | a DROP OF WATER | is trapped | in a HARD SHELL.", 0.25),
 ("steam", "The heat turns it to steam at nine times normal air pressure.",
  "The HEAT | turns it to STEAM | at 9× | NORMAL AIR PRESSURE.", 0.3),
 ("burst", "The shell cracks, and the starch puffs into foam forty times bigger.",
  "The SHELL CRACKS, | and the starch puffs into FOAM | 40× BIGGER.", 0.3),
 ("leg", "It even kicks out a leg and flips like a gymnast.",
  "It even KICKS OUT A LEG | and FLIPS | like a GYMNAST.", 0.3),
 ("pop", "And the pop? That's the steam escaping, not the shell.",
  "And the POP? | That's the STEAM ESCAPING, | NOT THE SHELL.", 0.35),
 ("loop", "Heat it up, and", "HEAT IT UP, | and", 0.0),
]
