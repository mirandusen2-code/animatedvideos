"""Replace the old subtitle band from native renders, then retime picture, sound and captions together."""
from pathlib import Path
import io,json,subprocess as sp,os,base64
import numpy as np
from PIL import Image
from captions import *
src=HERE.parent/'pufferfish-sand-circle'/'pufferfish-sand-circle.mp4'
dest=HERE/'pufferfish-sand-circle-v2.mp4'
N=650
assert json.loads((src.parent/'vo/timing.json').read_text())['NFRAMES']==682
def run(args,**kw):return sp.run(['ffmpeg','-hide_banner','-nostdin','-y',*args],check=True,**kw)
def loud(path):
    res=run(['-i',str(path),'-vn','-af','loudnorm=print_format=json','-f','null','-'],capture_output=True,text=True)
    return json.JSONDecoder().raw_decode(res.stderr[res.stderr.rfind('{'):])[0]
def repair_onset():
    # In the historical word alignment “Hundreds” was assigned six milliseconds.
    # Use the recorded consonant attack after “groove”, inside its long sentence break.
    words=CUES[15]['words'];assert words[0][0]=='Hundreds'
    factor=682/N;lo=CUES[14]['words'][-1][2]+.07;hi=words[1][1]-.075
    buf=run(['-loglevel','error','-ss',str(lo*factor),'-i',str(src),'-t',str((hi-lo)*factor),'-vn','-af','highpass=f=900,lowpass=f=4500','-ar','16000','-ac','1','-f','f32le','-'],stdout=sp.PIPE).stdout
    samples=np.frombuffer(buf,'<f4');energy=np.sqrt(np.mean(samples[:len(samples)//160*160].reshape(-1,160)**2,axis=1))
    energy=np.convolve(energy,[.25,.5,.25],mode='same')
    quiet=np.percentile(energy,20);threshold=quiet+.22*(np.percentile(energy,93)-quiet)
    minimum=int(np.argmin(energy[:max(2,len(energy)//2)]))
    onset=next(i for i in range(minimum,len(energy)-2) if np.all(energy[i:i+3]>threshold))
    words[0][1]=round(lo+onset*.01/factor,4);FIRST_FRAME[15]=math.ceil(words[0][1]*30-1e-8)
    print('Hundreds consonant onset',words[0][1],flush=True)
def main():
    repair_onset()
    for j in range(len(CUES)):overlay(j,-1)
    subtitles(N,'pufferfish-sand-circle-v2.srt')
    source=sp.Popen(['ffmpeg','-v','error','-i',str(src),'-an','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=sp.PIPE)
    video=HERE/'silent.mp4'
    enc=sp.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920','-r','30','-i','-','-c:v','libx264','-crf','18','-maxrate','4100k','-bufsize','5000k','-threads','3','-preset','fast','-pix_fmt','yuv420p',str(video)],stdin=sp.PIPE)
    # The feathered edge is outside both the original and revised glyphs.
    alpha=np.minimum(1,np.minimum(np.arange(240)/17,(239-np.arange(240))/17))
    mask=Image.fromarray(np.tile((alpha*255).astype('uint8')[:,None],(1,W)))
    targets={round(i*682/N):i for i in range(N)}
    review=Image.new('RGB',(540,((len(CUES)+1)//2)*46))
    seen=set();center=0
    for original in range(682):
        pix=source.stdout.read(W*H*3);assert len(pix)==W*H*3
        if original not in targets:continue
        i=targets[original];im=Image.frombytes('RGB',(W,H),pix)
        with Image.open(Path(os.environ['BANDS'])/f'{original:05}.png') as clean:im.paste(clean.convert('RGB'),(0,1320),mask)
        j,k=position(i);layer,box=overlay(j,k);im.paste(layer,(0,STRIP_TOP),layer)
        center=max(center,abs((box[0]+box[2])/2-CENTER))
        if k>=0:seen.add((j,k))
        if i==FIRST_FRAME[j]+3:review.paste(im.crop((0,1340,1080,1492)).resize((270,38),Image.Resampling.LANCZOS),((j%2)*270,j//2*46))
        enc.stdin.write(im.tobytes())
    assert not source.stdout.read(1) and source.wait()==0
    enc.stdin.close();assert enc.wait()==0 and len(seen)==sum(len(c['words']) for c in CUES)
    def mux(gain):
        run(['-loglevel','error','-i',str(video),'-i',str(src),'-map','0:v:0','-map','1:a:0','-af',f'atempo={682/N:.9f},volume={gain:.4f}dB,apad','-t',f'{N/30:.9f}','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(dest)])
    mux(0);m=loud(dest);mux(-14-float(m['input_i']));m=loud(dest)
    assert abs(float(m['input_i'])+14)<.35 and float(m['input_tp'])<=-1.5
    streams=json.loads(sp.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(dest)]))['streams'];v=streams[0]
    assert (int(v['nb_frames']),v['width'],v['height'],v['pix_fmt'])==(N,W,H,'yuv420p')
    mem=io.BytesIO();review.save(mem,'JPEG',quality=88)
    print('PFREVIEW',base64.b64encode(mem.getvalue()).decode(),'ENDIMAGE')
    print('PFSRT',base64.b64encode((HERE/'pufferfish-sand-circle-v2.srt').read_bytes()).decode());print('PFCUES',base64.b64encode(json.dumps(CUES,indent=2).encode()).decode())
    print('PUBLICQA',json.dumps(dict(frames=N,seconds=N/30,speed=682/N,cues=len(CUES),words=len(seen),font_px=72,baseline=1420,max_center_error=center,LUFS=float(m['input_i']),peak=float(m['input_tp']))))
if __name__=='__main__':main()
