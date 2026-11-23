"""Assemble, mix, meter and inspect the actual phone export."""
from pathlib import Path
import io,base64,json,math,subprocess,re,os
from math import pi
import numpy as np
from PIL import Image,ImageDraw
from art import frame,W,D,N,DUR,SHOTS,font
from captions import overlay,position,FIRST_FRAME,CUES,STRIP_TOP,subtitles
NFRAMES=N;SR=44100;NS=N*1470
def ff(args,**kw):return subprocess.run(['ffmpeg','-hide_banner','-nostdin','-y',*args],check=True,**kw)
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
        for f in triad:note(j*bar-.15,f*.944,1.18*bar,.012,True)
        for beat,p in [(0,0),(2.5,2)]:note(j*bar+beat*bar/4,triad[p]*.944*(.5 if beat==0 else 2),1.1 if beat==0 else .45,.036 if beat==0 else .022)
    reveal=W('echo','returns');music*=np.clip(np.abs(t-reveal)/.26,0,1)**1.4
    a=np.arange(round(.56*SR))/SR;fold(effects,reveal,.095*np.sin(2*pi*(43*a+2.4*(1-np.exp(-12*a))))*np.exp(-9*a)*np.minimum(1,a/.012))
    for at,hz,g in [(W('pulse','laser'),1046,.018),(reveal,1568,.024),(W('drift','away'),784,.017)]:
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

def encode():
    name='lunar-laser-ranging';subtitles(N,name+'.srt');mix_sound()
    p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920','-r','30','-i','-','-c:v','libx264','-threads','3','-preset','fast','-crf','18','-maxrate','4600k','-bufsize','6000k','-pix_fmt','yuv420p','silent.mp4'],stdin=subprocess.PIPE)
    sheet=Image.new('RGB',(600,534));seen=set();qa=Path('qa');qa.mkdir(exist_ok=True);covers=Path('thumbnails');covers.mkdir(exist_ok=True)
    samples={round((a+.49*((SHOTS[j+1][1] if j+1<len(SHOTS) else DUR)-a))*30):j for j,(_,a) in enumerate(SHOTS)}
    picks={round((W('apollo')+1)*30):('a',['A MIRROR','ON THE MOON']),round((W('echo')+2.5)*30):('b',['LIGHT COMES','BACK']),round((W('drift','away')+.77)*30):('c',['THE MOON','IS LEAVING'])}
    shape=None
    for i in range(N):
        im=frame(i);assert im.size==(1080,1920)
        if i in (0,N-1):
            arr=np.array(im.resize((180,320))).astype(float)
            if i==0:shape=arr
            else:seam=float(np.abs(arr-shape).mean())
        if i in picks:
            letter,lines=picks[i];cover=im.copy();dr=ImageDraw.Draw(cover)
            for j,line in enumerate(lines):
                f=font(107);width=dr.textlength(line,font=f);assert width<740
                dr.text((476,362+j*100),line,anchor='mt',font=f,fill=(255,221,154) if j else 'white',stroke_width=5,stroke_fill=(13,24,31))
            cover.save(covers/('cover-'+letter+'.jpg'),quality=91)
        j,k=position(i);layer,box=overlay(j,k);im.paste(layer,(0,STRIP_TOP),layer)
        if k>=0:seen.add((j,k))
        if i in samples:
            j=samples[i];sheet.paste(im.resize((150,267),Image.Resampling.LANCZOS),((j%4)*150,(j//4)*267))
        p.stdin.write(im.tobytes())
    p.stdin.close();assert p.wait()==0
    assert len(seen)==sum(len(c['words']) for c in CUES) and seam<6,seam
    sheet.save(qa/'shot-sheet.jpg',quality=88)
    def mux(gain):
        ff(['-loglevel','error','-i','silent.mp4','-i','vo/mix.wav','-map','0:v','-map','1:a','-c:v','copy','-af',f'volume={gain:.4f}dB','-c:a','aac','-b:a','192k','-ac','2','-t',f'{DUR:.9f}','-movflags','+faststart',name+'.mp4'])
    mux(0);m=loudness(name+'.mp4');mux(min(-14-float(m['input_i']),-1.65-float(m['input_tp'])));m=loudness(name+'.mp4')
    raw=ff(['-v','error','-i',name+'.mp4','-an','-vf','scale=90:160:flags=area','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE).stdout
    frames=np.frombuffer(raw,'uint8').reshape(-1,160,90);assert len(frames)==N
    dif=np.abs(np.diff(frames.astype('f'),axis=0)).mean((1,2));cuts=[round(t*30) for _,t in SHOTS]
    jumps=[i+1 for i,mv in enumerate(dif) if mv>18 and min(abs(i+1-c) for c in cuts)>2]
    freezes=[];start=None
    for i,mv in enumerate([*dif,3]):
        if mv<.018 and start is None:start=i
        elif mv>=.018 and start is not None:
            if i-start>=15:freezes.append([start,i])
            start=None
    dark=np.where(frames.max(axis=(1,2))<30)[0].tolist()
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',name+'.mp4']))['streams']
    assert streams[0]['pix_fmt']=='yuv420p' and streams[0]['r_frame_rate']=='30/1' and streams[1]['codec_name']=='aac'
    q=dict(frames=N,seconds=DUR,words=65,wpm=round(65*60/DUR,1),font_px=72,baseline=1420,cues=len(CUES),LUFS=float(m['input_i']),peak=float(m['input_tp']),black_frames=dark,unexpected_jumps=jumps,freezes=freezes,seam_MAE=seam)
    print('PUBLICQA',json.dumps(q),flush=True)
    assert abs(q['LUFS']+14)<.4 and q['peak']<=-1.5 and not (jumps or freezes or dark),q
    (qa/'measurements.json').write_text(json.dumps(q,indent=2))
if __name__=='__main__':encode()
