"""Native-size composition, per-batch encoding, circular score, foley and measured mastering."""
from pathlib import Path
from functools import lru_cache
import json, math, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from timeline import D, FPS, NFRAMES, DUR, W, shot
H,WIDTH=1920,1080
SAFE=(92,300,860,1540)
FONT=Path(__file__).with_name('Montserrat.ttf')
SR=44100; NS=1470*NFRAMES
def ff(args,**kwargs):
    return subprocess.run(['ffmpeg','-nostdin','-hide_banner','-y',*args],check=True,**kwargs)
@lru_cache(maxsize=90)
def font(px,weight=840):
    f=ImageFont.truetype(str(FONT),px);f.set_variation_by_axes([weight]);return f
chunks=[];chunk=[]
for word in D['words']:
    chunk.append(word)
    if word[4]:chunks.append(chunk);chunk=[]
assert not chunk
def guard(x,y,w,h):
    assert x>=SAFE[0] and y>=SAFE[1] and x+w<=SAFE[2] and y+h<=SAFE[3],(x,y,w,h)
@lru_cache(maxsize=180)
def caption(number,active):
    c=chunks[number];words=[w[2] for w in c];size=72
    while True:
        f=font(size);gap=f.getlength(' ');width=sum(f.getlength(x) for x in words)+gap*(len(words)-1)
        if width<=715:break
        size-=1
    out=Image.new('RGBA',(math.ceil(width)+24,105))
    dr=ImageDraw.Draw(out);x=12
    for i,w in enumerate(words):
        color=(255,202,85) if i==active else ((169,232,232) if c[i][3] else (255,252,238))
        dr.text((x+1,15),w,font=f,anchor='lt',fill=(5,20,21,175),stroke_width=7,stroke_fill=(5,20,21,175))
        dr.text((x,10),w,font=f,anchor='lt',fill=color,stroke_width=4,stroke_fill=(13,33,33))
        x+=f.getlength(w)+gap
    return out
def compose(im,i):
    t=i/FPS;k=max([j for j,c in enumerate(chunks) if c[0][0]<=t] or [0]);c=chunks[k]
    active=max([j for j,v in enumerate(c) if v[0]<=t] or [0])
    cap=caption(k,active);x=round(476-cap.width/2);y=1380;guard(x,y,*cap.size);im.paste(cap,(x,y),cap)
    return im
def clip(start,end):
    target=Path(os.environ['CLIP_DIR']);target.mkdir(exist_ok=True,parents=True)
    frames=Path(os.environ['FRAME_DIR'])
    end=min(end,NFRAMES)
    proc=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','1080x1920','-framerate','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-maxrate','3400k','-bufsize','4200k','-pix_fmt','yuv420p','-g','40','-keyint_min','40','-sc_threshold','0','-threads','3','-movflags','+faststart',str(target/'clip.mp4')],stdin=subprocess.PIPE)
    from thumbnails import choices,cover
    sheet=Image.new('RGB',(800,4*164),'#151d1d');dr=ImageDraw.Draw(sheet)
    from timeline import CUTS
    cuts={math.ceil(c*FPS) for c in CUTS}
    for i in range(start,end):
        with Image.open(frames/f'{i:05}.png') as f: im=f.convert('RGB')
        assert im.size==(WIDTH,H)
        if i in (0,1,NFRAMES-1,NFRAMES-2,NFRAMES-3):
            im.resize((270,480),Image.Resampling.LANCZOS).save(target/f'seam-{i:04}.png')
        if i in choices():
            label,words=choices()[i];cover(im.copy(),words).save(target/('choice-'+label+'.jpg'),quality=94)
        im=compose(im,i)
        proc.stdin.write(im.tobytes())
        j=i-start;x=(j%10)*80;y=(j//10)*164;sheet.paste(im.resize((80,142),Image.Resampling.BILINEAR),(x,y))
        dr.rectangle((x+7,y+22,x+64,y+114),outline='#538778')
        dr.text((x+3,y+144),str(i),fill='orange' if i in cuts else 'white')
    proc.stdin.close();assert proc.wait()==0
    sheet.save(target/f'frames-{start:04}.jpg',quality=82)
    info=subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','stream=nb_frames','-of','csv=p=0',str(target/'clip.mp4')],text=True)
    assert int(info.strip())==end-start
def mix_sound():
    import soundfile as sf
    from scipy.signal import butter,sosfilt
    rng=np.random.default_rng(546);music=np.zeros(NS);effects=np.zeros(NS);t=np.arange(NS)/SR;bar=DUR/8
    def fold(dst,start,x):
        ix=round(start*SR)%NS;n=min(NS-ix,len(x));dst[ix:ix+n]+=x[:n]
        if n<len(x):dst[:len(x)-n]+=x[n:]
    def note(at,f,d,g,soft=False):
        a=np.arange(round(SR*d))/SR
        if soft: env=np.sin(pi*np.minimum(1,a/d))**1.7
        else:env=np.minimum(1,a/.014)*np.exp(-4.8*a/d)*np.minimum(1,(d-a)/.055)
        s=g*env*(np.sin(2*pi*f*a)+.22*np.sin(4*pi*f*a+.2)+.07*np.sin(6*pi*f*a))
        fold(music,at,s);fold(music,at+.092,s*.20);fold(music,at+.161,s*.08)
    for j,triad in enumerate([(130.81,164.81,196.),(110.,130.81,164.81),(87.31,130.81,174.61),(98.,123.47,146.83),(130.81,164.81,196.),(146.83,174.61,220.),(87.31,110.,130.81),(98.,123.47,196.)]):
        for f in triad:note(j*bar-.15,f*.841,1.18*bar,.012,True)
        for beat,p in [(0,0),(1.5,2),(3,1)]:note(j*bar+beat*bar/4,triad[p]*.841*(.5 if beat==0 else 2),1.1 if beat==0 else .45,.036 if beat==0 else .022)
    reveal=W('back','mirror');music*=np.clip(np.abs(t-reveal)/.26,0,1)**1.4
    a=np.arange(round(.56*SR))/SR;fold(effects,reveal,.095*np.sin(2*pi*(43*a+2.4*(1-np.exp(-12*a))))*np.exp(-9*a)*np.minimum(1,a/.012))
    for at,hz,g in [(W('back'),796,.016),(W('tiles'),1183,.022),(W('focus'),933,.023)]:
        a=np.arange(round(.64*SR))/SR
        chime=g*np.exp(-6.4*a)*np.minimum(1,a/.014)*(np.sin(2*pi*hz*a)+.33*np.sin(2*pi*hz*1.51*a))
        fold(effects,at,chime)
    voice,sr=sf.read('vo/narration.wav');assert sr==SR and len(voice)==NS
    for name,x in [('speech',voice),('score',music),('optics',effects)]:sf.write('vo/'+name+'-3.wav',np.tile(x,3),SR,subtype='FLOAT')
    graph=('[0:a]highpass=f=75,equalizer=f=175:t=q:w=1:g=1,deesser=i=.12,acompressor=threshold=.12:ratio=2.4,aecho=.96:.98:18:.045,asplit[v][key];'
           '[1:a][key]sidechaincompress=threshold=.017:ratio=4:attack=7:release=145[m];'
           f'[v][m][2:a]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-2.5:LRA=8,aresample=44100,atrim=start_sample={NS}:end_sample={2*NS},asetpts=PTS-STARTPTS[a]')
    ff(['-loglevel','error','-i','vo/speech-3.wav','-i','vo/score-3.wav','-i','vo/optics-3.wav','-filter_complex',graph,'-map','[a]','-c:a','pcm_s24le','vo/mix.wav'])
def loudness(path):
    p=ff(['-i',str(path),'-vn','-af','loudnorm=I=-14:TP=-1.5:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True)
    return json.loads(re.findall(r'\{[^{}]*"input_i"[^{}]*\}',p.stderr)[-1])
def subtitles():
    def stamp(t):
        ms=round(t*1000);return f'00:{ms//60000:02}:{(ms//1000)%60:02},{ms%1000:03}'
    lines=[]
    for j,c in enumerate(chunks):
        a=c[0][0] if j else 0;b=chunks[j+1][0][0] if j+1<len(chunks) else DUR
        lines.append(f'{j+1}\n{stamp(a)} --> {stamp(b)}\n'+' '.join(v[2] for v in c))
    Path('scallop-mirror-eyes.srt').write_text('\n\n'.join(lines)+'\n')
def finish():
    folders=[Path(os.environ['RUNNER_TEMP'])/f'scallop-clip-{i}' for i in range(0,NFRAMES,40)]
    concat=Path(os.environ['RUNNER_TEMP'])/'clips.txt';concat.write_text(''.join(f"file '{f/'clip.mp4'}'\n" for f in folders))
    mix_sound();subtitles()
    dest='scallop-mirror-eyes.mp4'
    def encode(gain):
        ff(['-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-i','vo/mix.wav','-map','0:v','-map','1:a','-c:v','copy','-af',f'volume={gain:.4f}dB','-c:a','aac','-b:a','192k','-ar','44100','-ac','2','-t',f'{DUR:.9f}','-movflags','+faststart',dest])
    encode(0);q=loudness(dest);gain=min(-14-float(q['input_i']),-1.62-float(q['input_tp']))
    if abs(gain)>.06:encode(gain)
    from shutil import copy2
    for p in ('qa','thumbnails'):Path(p).mkdir(exist_ok=True)
    for folder in folders:
        for pattern,directory in [('seam-*.png','qa'),('frames-*.jpg','qa'),('choice-*.jpg','thumbnails')]:
            for p in folder.glob(pattern):copy2(p,Path(directory)/p.name)
pi=math.pi
if __name__=='__main__':
    if sys.argv[1]=='clip':clip(int(sys.argv[2]),int(sys.argv[3]))
    else:finish()
