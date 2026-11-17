# Prompt: "Wist je dat… een octopus drie harten heeft?"

**Formaat:** 1280×720, 30 fps, ~35 seconden, MP4 (H.264 + AAC), Nederlandstalig.
**Stijl:** Vrolijke 2D-cartoon in de diepzee. Donkerblauwe verloop-achtergrond met zachte lichtstralen,
opstijgende belletjes en zwevende "marine snow". Een schattige roze octopus met rechthoekige pupillen
(zoals echte octopussen), wiebelende tentakels met zuignappen. Dikke, leesbare witte tekst met donkere rand.
**Geluid:** Rustige onderwater-drone, belletjes-geluidjes, "pop" bij elke onthulling en een hartslag
(lub-dub) die synchroon loopt met de kloppende hartjes.

## Het feit
Een octopus heeft **drie harten**: twee kieuwharten die bloed door de kieuwen pompen en één hoofdhart
(systemisch hart) voor de rest van het lichaam. Zijn bloed is **blauw**, omdat het eiwit
**hemocyanine** koper gebruikt in plaats van ijzer (zoals hemoglobine bij mensen).
Bonus: tijdens het **zwemmen stopt het hoofdhart** met kloppen — daarom kruipt een octopus liever.

## Scènes
1. **0–4 s · Intro** — "Wist je dat...?" ploft in beeld, ondertitel "een random weetje uit de diepzee".
2. **4–10 s · Kennismaking** — De octopus zwemt van onderen omhoog. "Dit is een octopus." /
   "Hij verbergt een geheim..."
3. **10–19 s · Drie harten** — De octopus zoomt in, zijn mantel wordt doorzichtig. Drie kloppende hartjes
   ploffen één voor één tevoorschijn: "3 HARTEN!". Labels: 2× kieuwhart, 1× hoofdhart.
   Onderschrift: "2 voor de kieuwen, 1 voor de rest van het lichaam".
4. **19–26 s · Blauw bloed** — Octopus schuift naar links, de harten kleuren blauw en blauwe
   bloeddeeltjes stromen door de tentakels. "En zijn bloed is... BLAUW!". Rechts twee druppels:
   rood (Mens · ijzer, Fe) vs blauw (Octopus · koper, Cu). Onderschrift over hemocyanine.
5. **26–31 s · Bonus** — De octopus zwemt met stuwende bewegingen; het hoofdhart wordt grijs en stopt
   ("PAUZE"). "Als een octopus zwemt, stopt zijn hoofdhart met kloppen!" /
   "Daarom kruipt hij liever dan te zwemmen."
6. **31–35 s · Outro** — Mantel weer ondoorzichtig, "Wist jij dit al?" en een samenvatting:
   "3 harten • blauw bloed • koper i.p.v. ijzer". Uitfaden naar zwart.

## Uitvoering
Procedureel getekend in Python (Pillow + NumPy) op 2× resolutie voor anti-aliasing, frames via een pipe
naar ffmpeg; het geluid wordt met NumPy gesynthetiseerd. Zie `animate.py`.
