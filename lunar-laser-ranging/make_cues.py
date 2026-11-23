"""Build single-line captions from the verified recording; reserve a complete phrase for each cue."""
import json,os
from pathlib import Path
from PIL import ImageFont
d=json.loads(Path('vo/timing.json').read_text());font=ImageFont.truetype(os.environ['CAPTION_FONT'],72)
rows=d['words'];groups=[];pending=[]
for a,b,word,hot,end in rows:
    pending.append([word,a,b])
    if end:
        # Keep the numerical round-trip bound readable in a single glance.
        if [w[0].lower() for w in pending]==['about','two','and','a','half']:
            pending=[pending[0],['2.5',pending[1][1],pending[-1][2]]]
        groups.append(pending);pending=[]
assert not pending
out=[]
for group in groups:
    words=[]
    for word in group:
        phrase=' '.join(x[0] for x in words+[word])
        if words and font.getlength(phrase)>610:out.append(words);words=[]
        words.append(word)
    out.append(words)
Path('cues.json').write_text(json.dumps([dict(text=' '.join(v[0] for v in c),words=c) for c in out],indent=2))
