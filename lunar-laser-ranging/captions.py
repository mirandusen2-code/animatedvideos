"""One fixed-size shaped line. Only the fill color changes on the spoken word."""
import bisect,json,math,os
from pathlib import Path
from functools import lru_cache
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent
FPS=30
W, H = 1080, 1920
BASELINE, CENTER = 1420, 540
STRIP_TOP, STRIP_HEIGHT = 1300, 220
OUTLINE = 4
WEIGHT = 700
WHITE, ACTIVE, INK = (255, 252, 244), (255, 214, 108), (12, 23, 30)
CUES = json.loads((HERE / 'cues.json').read_text())
STARTS = [c['words'][0][1] for c in CUES]
FIRST_FRAME = [0] + [math.ceil(s*FPS-1e-8) for s in STARTS[1:]]
assert len(CUES) == len(set(FIRST_FRAME))
FONT=ImageFont.truetype(os.environ['CAPTION_FONT'],72)
SIZE=72
@lru_cache(maxsize=128)
def overlay(index, active):
    cue = CUES[index]
    text = cue['text']
    # Rasterize the entire shaped run on a shared baseline, including descenders.
    # Coloring replaces pixels inside that ink mask, so the active word cannot reflow.
    mask = Image.new('L',(W,STRIP_HEIGHT));outline = Image.new('L',mask.size)
    anchor_y = BASELINE-STRIP_TOP
    d = ImageDraw.Draw(mask)
    # Use the measured ink width and compensate for the first glyph's side bearing.
    # Measure at x=40 so negative overhangs are also retained.
    temp = Image.new('L',(W,STRIP_HEIGHT))
    ImageDraw.Draw(temp).text((40,anchor_y),text,font=FONT,anchor='ls',fill=255)
    left,_,right,_ = temp.getbbox()
    x = round(CENTER - (left+right)/2 + 40)
    d.text((x,anchor_y),text,font=FONT,anchor='ls',fill=255)
    ImageDraw.Draw(outline).text((x,anchor_y),text,font=FONT,anchor='ls',fill=255,stroke_width=OUTLINE,stroke_fill=255)
    stage = Image.new('RGBA',mask.size,(*INK,0));stage.putalpha(outline)
    colors=Image.new('RGB',mask.size,WHITE)
    if active >= 0:
        words=text.split();gap=FONT.getlength(' ')
        begin=x if active==0 else x+FONT.getlength(' '.join(words[:active]))+gap/2
        end=x+FONT.getlength(' '.join(words[:active+1]))+gap/2
        ImageDraw.Draw(colors).rectangle((math.floor(begin),0,math.floor(end),STRIP_HEIGHT),fill=ACTIVE)
    stage.paste(colors,(0,0),mask)
    box=mask.getbbox();safe=outline.getbbox()
    assert abs((box[0]+box[2])/2-CENTER)<=.5
    assert 92<=safe[0]<safe[2]<=860 and 300<=STRIP_TOP+safe[1]<STRIP_TOP+safe[3]<=1540
    return stage, box

def position(i):
    t=i/FPS;idx=bisect.bisect_right(FIRST_FRAME,i)-1
    active=next((j for j,(_,a,b) in enumerate(CUES[idx]['words']) if a<=t<b),-1)
    return idx,active

def stamp(i):
    ms=round(i/FPS*1000);return f'00:00:{ms//1000:02d},{ms%1000:03d}'

def subtitles(frames,name):
    cues=[]
    for j,cue in enumerate(CUES):
        a=FIRST_FRAME[j];b=FIRST_FRAME[j+1] if j+1<len(CUES) else frames
        cues.append(f'{j+1}\n{stamp(a)} --> {stamp(b)}\n{cue["text"]}')
    (HERE/name).write_text('\n\n'.join(cues)+'\n')
