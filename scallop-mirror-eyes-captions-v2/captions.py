"""Rebuild the English captions using one font, one optical center and one baseline."""
import base64
import bisect
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ['ORIGINAL']).resolve()
sys.path.insert(0, str(SOURCE))
from art import frame as clean_frame
from timeline import D, FPS, NFRAMES

W, H = 1080, 1920
BASELINE, CENTER = 1420, 540
STRIP_TOP, STRIP_HEIGHT = 1300, 220
OUTLINE = 4
WEIGHT = 700
WHITE, ACTIVE, INK = (255, 252, 244), (255, 214, 108), (12, 23, 30)
ORIGINAL = SOURCE / 'scallop-mirror-eyes.mp4'
MOVIE = HERE / 'scallop-mirror-eyes-v2.mp4'
CUES = json.loads((HERE / 'cues.json').read_text())
STARTS = [c['words'][0][1] for c in CUES]
FIRST_FRAME = [0] + [math.ceil(s*FPS-1e-8) for s in STARTS[1:]]
assert len(CUES) == len(set(FIRST_FRAME))
spoken = [w[2].casefold() for w in D['words']]
assert [w[0].casefold() for c in CUES for w in c['words']] == spoken

def matched_font():
    for size in range(72, 57, -1):
        font = ImageFont.truetype(str(HERE/'BarlowSemiCondensed-Bold.ttf'), size)
        bounds = [font.getbbox(c['text'], anchor='ls', stroke_width=OUTLINE) for c in CUES]
        if max(r-l for l,t,r,b in bounds) <= 620:
            return font, size
    raise ValueError('Edit the longest caption phrase to fit the mobile safe zone.')
FONT, SIZE = matched_font()

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

def h264(i):
    return subprocess.check_output(['ffmpeg','-loglevel','error','-ss',f'{i/FPS:.7f}','-i',str(ORIGINAL),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])

def format_srt():
    cues=[]
    for j,cue in enumerate(CUES):
        a=FIRST_FRAME[j];b=FIRST_FRAME[j+1] if j+1<len(CUES) else NFRAMES
        cues.append(f'{j+1}\n{stamp(a)} --> {stamp(b)}\n{cue["text"]}')
    (HERE/'scallop-mirror-eyes-v2.srt').write_text('\n\n'.join(cues)+'\n')

def render():
    format_srt()
    process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','1080x1920','-framerate','30','-i','-','-i',str(ORIGINAL),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','18','-maxrate','3700k','-bufsize','4500k','-threads','3','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(MOVIE)],stdin=subprocess.PIPE)
    review=Image.new('RGB',(540,((len(CUES)+1)//2)*44),(15,21,25))
    proof=Image.new('RGB',(740,4*118),(18,23,27))
    proofnumbers=[2,6,13,19]
    maxcenter=0;minright=W;highlighted=set()
    for i in range(NFRAMES):
        im=clean_frame(i);j,k=position(i);layer,box=overlay(j,k)
        im.paste(layer,(0,STRIP_TOP),layer)
        maxcenter=max(maxcenter,abs((box[0]+box[2])/2-CENTER));minright=min(minright,W-layer.getbbox()[2])
        if k>=0:highlighted.add((j,k))
        if i==FIRST_FRAME[j]+3:
            strip=im.crop((0,1347,1080,1491))
            review.paste(strip.resize((270,36),Image.Resampling.LANCZOS),((j%2)*270,(j//2)*44))
            if j in proofnumbers:
                row=proofnumbers.index(j)
                original=Image.frombytes('RGB',(W,H),h264(i))
                for col,pic in enumerate((original,im)):
                    thumb=pic.crop((0,1320,1080,1510)).resize((365,64),Image.Resampling.LANCZOS)
                    proof.paste(thumb,(col*370,row*118+27))
        process.stdin.write(im.tobytes())
    process.stdin.close();assert process.wait()==0
    assert len(highlighted)==sum(len(c['words']) for c in CUES)
    for name,pic in [('ALLCAPTIONS',review),('OLDNEW',proof)]:
        mem=io.BytesIO();pic.save(mem,'JPEG',quality=92)
        print(name,base64.b64encode(mem.getvalue()).decode(),'ENDIMAGE',flush=True)
    def audio(path):
        return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-']).decode().strip()
    assert audio(ORIGINAL)==audio(MOVIE)
    def streams(path):
        return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))['streams']
    old,new=streams(ORIGINAL),streams(MOVIE)
    v=new[0];assert (v['codec_name'],v['width'],v['height'],v['pix_fmt'],v['r_frame_rate'],int(v['nb_frames']))==('h264',W,H,'yuv420p','30/1',NFRAMES)
    assert abs(float(old[0]['duration'])-float(v['duration'])) < .034
    assert old[1]['duration_ts']==new[1]['duration_ts'] and old[1]['start_pts']==new[1]['start_pts']
    # Compare the finished movies outside the caption band at matching frame indexes.
    filt='[0:v]setpts=N/(30*TB),scale=270:480,drawbox=x=0:y=324:w=270:h=57:color=black:t=fill[a];[1:v]setpts=N/(30*TB),scale=270:480,drawbox=x=0:y=324:w=270:h=57:color=black:t=fill[b];[a][b]ssim'
    result=subprocess.run(['ffmpeg','-hide_banner','-i',str(ORIGINAL),'-i',str(MOVIE),'-filter_complex',filt,'-an','-f','null','-'],capture_output=True,text=True,check=True)
    import re
    score=float(re.findall(r'All:([0-9.]+)',result.stderr)[-1]);assert score>=.985,score
    report=dict(frames=NFRAMES,seconds=NFRAMES/FPS,font='Barlow Semi Condensed',weight=WEIGHT,font_px=SIZE,baseline_px=BASELINE,center_x=CENTER,max_center_error_px=maxcenter,right_clearance_px=minright,cues=len(CUES),timed_words=len(highlighted),audio_sha256=audio(MOVIE),outside_caption_SSIM=score,bytes=MOVIE.stat().st_size)
    (HERE/'QA.json').write_text(json.dumps(report,indent=2)+'\n')
    print('CAPTION_QA',json.dumps(report),flush=True)
if __name__=='__main__':render()
