"""Composite native Cycles renders, assemble a circular mix, encode and measure the Short."""
from pathlib import Path
import sys, math, json, os, shutil, subprocess, functools, random
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
from timeline import DATA,DUR,NFRAMES,FPS,W,shot
import imageio_ffmpeg
FF=shutil.which('ffmpeg') or imageio_ffmpeg.get_ffmpeg_exe()
H,WID=1920,1080;SAFE=(92,300,860,1540);SR=44100;SAMPLES=NFRAMES*1470
ROOT=Path(__file__).resolve().parent;os.chdir(ROOT)
def ff(args,**kw):return subprocess.run([FF,'-hide_banner','-y',*args],check=True,**kw)
@functools.lru_cache(maxsize=48)
def font(size,weight=900):
 f=ImageFont.truetype('Montserrat.ttf',size);f.set_variation_by_axes([weight]);return f
Y,X=np.mgrid[0:H,0:WID:1];y=Y/H;x=X/WID
# A cool, off-axis ROV illumination cone with quiet corners; no noise field or grain.
field=np.exp(-(((x-.38)/.76)**2+((y-.41)/.50)**2)*1.7)
shaft=np.exp(-((x+.6*y-.71)/.38)**2)*np.exp(-((y-.07)/.62)**2)
bg=np.stack([3+7*field+3*shaft,9+15*field+9*shaft,14+20*field+15*shaft],axis=-1).astype('uint8')
back=Image.fromarray(bg);del X,Y,x,y,bg,field,shaft
rng=random.Random(495);snow=[(rng.uniform(0,WID),rng.uniform(0,H),rng.uniform(.7,2.35),rng.uniform(0,6.28),rng.uniform(6,22)) for i in range(85)]
def image_at(frame):
 t=frame/FPS;im=back.copy();d=ImageDraw.Draw(im);phase=2*math.pi*t/DUR
 for xx,yy,r,offset,amp in snow:
  px=xx+amp*math.sin(phase+offset);py=yy+amp*1.8*math.cos(phase+offset)
  v=round(25+r*10);d.ellipse((px-r,py-r,px+r,py+r),fill=(v-10,v+4,v+9))
 o=Image.open('frames/%05d.png'%frame).convert('RGBA')
 assert o.width==1080
 im.paste(o,(0,(H-o.height)//2),o)
 return im
chunks=[];current=[]
for v in DATA['words']:
 current.append(v)
 if v[4]:chunks.append(current);current=[]
assert not current
@functools.lru_cache(maxsize=256)
def caption(k,active):
 c=chunks[k];words=[v[2].upper() for v in c]
 sz=70
 while True:
  f=font(sz);space=f.getlength(' ');ww=sum(f.getlength(s) for s in words)+space*(len(c)-1)
  if ww<=736:break
  sz-=1
 out=Image.new('RGBA',(math.ceil(ww)+26,100));d=ImageDraw.Draw(out);x=13
 for j,s in enumerate(words):
  fill=(255,195,87) if j==active else ((175,227,241) if c[j][3] else (248,248,238))
  d.text((x+1,13),s,anchor='lt',font=f,fill=(0,0,0,160),stroke_width=7,stroke_fill=(0,0,0,160))
  d.text((x,9),s,anchor='lt',font=f,fill=fill,stroke_width=6,stroke_fill=(12,22,27,255));x+=f.getlength(s)+space
 return out
def compose(i):
 im=image_at(i);t=i/FPS
 k=max([j for j,c in enumerate(chunks) if c[0][0]<=t] or [0]);c=chunks[k]
 active=max([j for j,v in enumerate(c) if v[0]<=t] or [0])
 cap=caption(k,active);pos=(round(476-cap.width/2),1405)
 assert SAFE[0]<=pos[0] and pos[0]+cap.width<=SAFE[2] and SAFE[1]<=pos[1] and pos[1]+cap.height<=SAFE[3]
 im.paste(cap,pos,cap);return im
def picture():
 p=subprocess.Popen([FF,'-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920','-r','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-threads','3','picture.mp4'],stdin=subprocess.PIPE)
 for i in range(NFRAMES):p.stdin.write(compose(i).tobytes())
 p.stdin.close();assert p.wait()==0
def sound():
 import soundfile as sf
 from scipy.signal import butter,sosfilt
 n=SAMPLES;t=np.arange(n)/SR;rng=np.random.default_rng(710)
 music=np.zeros(n);fx=np.zeros(n);bar=DUR/6
 def fold(track,start,sig):
  idx=int(round(start*SR))%n;first=min(len(sig),n-idx);track[idx:idx+first]+=sig[:first]
  if first<len(sig):track[:len(sig)-first]+=sig[first:]
 def note(at,f,d,amp,pad=False):
  a=np.arange(round(d*SR))/SR
  if pad:e=np.sin(np.pi*np.minimum(1,a/d))**1.7
  else:e=np.minimum(1,a/.012)*np.exp(-4.6*a/d)*np.minimum(1,(d-a)/.045)
  tone=(np.sin(2*np.pi*f*a)+.20*np.sin(4*np.pi*f*a+.35)+.045*np.sin(6*np.pi*f*a))*e*amp
  fold(music,at,tone);fold(music,at+.083,.14*tone)
 for j,triad in enumerate([(146.83,174.61,220),(130.81,164.81,196),(110,146.83,174.61),(98,146.83,196),(116.54,146.83,174.61),(110,138.59,164.81)]):
  for f in triad:note(j*bar-.17,f,bar*1.22,.015,True)
  note(j*bar,triad[0]/2,bar*.70,.034)
  for k in (1.5,3):note(j*bar+k*bar/4,2*triad[int(k)%3],.75,.020)
 twist=W('turn','down')[0];gap=np.clip(np.abs(t-twist)/.30,0,1);music*=gap**1.7
 a=np.arange(round(.7*SR))/SR;fold(fx,twist,.115*np.sin(2*np.pi*(48*a+4*(1-np.exp(-20*a))))*np.exp(-8*a)*np.minimum(1,a/.009))
 for when,pitch in [(W('dome')[0],840),(W('pay')[0],590)]:
  a=np.arange(int(.46*SR))/SR;fold(fx,when,.013*np.sin(2*np.pi*pitch*a)*np.sin(np.pi*a/.46)**2*np.exp(-4*a))
 voice,sr=sf.read('vo/narration.wav');assert sr==SR
 folded=np.zeros(n);fold(folded,0,voice)
 for nm,z in [('voice',folded),('music',music),('fx',fx)]:sf.write('vo/'+nm+'-3.wav',np.tile(z,3),SR,subtype='FLOAT')
 # All filters see the neighbouring periods. Resample after loudnorm; trim by sample count.
 graph=('[0:a]highpass=f=75,equalizer=f=185:t=q:w=1:g=1.2,deesser=i=0.12,aecho=0.96:0.99:21:0.065,acompressor=threshold=0.11:ratio=2.3,asplit[v][key];'
 '[1:a][key]sidechaincompress=threshold=0.018:ratio=4:attack=8:release=150[m];[v][m][2:a]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-2.2:LRA=8,aresample=44100,atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS[a]'%(n,2*n))
 ff(['-loglevel','error','-i','vo/voice-3.wav','-i','vo/music-3.wav','-i','vo/fx-3.wav','-filter_complex',graph,'-map','[a]','-c:a','pcm_s24le','vo/master.wav'])
def subtitles():
 def tc(t):
  ms=round(t*1000);return '00:%02d:%02d,%03d'%(ms//60000,ms//1000%60,ms%1000)
 with open('barreleye.srt','w') as out:
  for j,c in enumerate(chunks):
   a=c[0][0] if j else 0;b=chunks[j+1][0][0] if j+1<len(chunks) else DUR
   out.write(f"{j+1}\n{tc(a)} --> {tc(b)}\n"+' '.join(v[2] for v in c)+'\n\n')
if __name__=='__main__':
 mode=sys.argv[1] if len(sys.argv)>1 else 'all'
 if mode in ('audio','all'):sound();subtitles()
 if mode in ('video','all'):
  picture()
  ff(['-loglevel','error','-i','picture.mp4','-i','vo/master.wav','-map','0:v:0','-map','1:a:0','-c:v','copy','-af','volume=1.19dB','-c:a','aac','-b:a','192k','-ar','44100','-ac','2','-shortest','-movflags','+faststart','barreleye.mp4'])
