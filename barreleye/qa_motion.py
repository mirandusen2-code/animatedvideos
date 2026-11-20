"""Analyse the decoded export at phone scale and the uncaptioned, native seam separately."""
from post import *
import cv2
import soundfile as sf
from timeline import CUTS
c=cv2.VideoCapture('barreleye.mp4');n=0;means=[];prev=None;diff=[];fps=c.get(5);wh=[int(c.get(3)),int(c.get(4))]
while True:
 ok,im=c.read()
 if not ok:break
 small=cv2.resize(im,(108,192),interpolation=cv2.INTER_AREA).astype('f')
 if prev is not None:diff.append(float(np.abs(small-prev).mean()))
 prev=small;n+=1;means.append(float(small.mean()))
cuts=[math.ceil(a*FPS) for a in CUTS[1:-1]]
jumps=[i+1 for i,d in enumerate(diff) if d>8 and min(abs(i+1-k) for k in cuts)>1]
frozen=[];begin=None
for i,d in enumerate(diff+[1]):
 if d<.012 and begin is None:begin=i
 if d>=.012 and begin is not None:
  if i-begin>=10:frozen.append([begin,i])
  begin=None
seam=[np.asarray(image_at(i).resize((270,480),Image.Resampling.LANCZOS),dtype='f') for i in [n-3,n-2,n-1,0,1]]
seamdiff=[round(float(np.abs(a-b).mean()),4) for a,b in zip(seam,seam[1:])]
aud=ff(['-loglevel','error','-i','barreleye.mp4','-vn','-ac','1','-ar',str(SR),'-f','f32le','-'],stdout=subprocess.PIPE).stdout
a=np.frombuffer(aud,dtype='<f4')[:SAMPLES];step=float(abs(a[-1]-a[0]));rms=lambda v:round(float(np.sqrt(np.mean(v*v))),7)
normal=float(np.percentile(np.abs(np.diff(a)),95))
p=subprocess.run([FF,'-hide_banner','-i','barreleye.mp4','-vf','blackdetect=d=0.01:pix_th=0.06','-af','loudnorm=I=-14:TP=-1.5:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
import re
m=json.loads(re.findall(r'\{[^{}]*"input_i"[^{}]*\}',p.stderr)[-1]);black=[x for x in p.stderr.splitlines() if 'black_start:' in x]
report=dict(frames=n,size=wh,fps=fps,seconds=n/fps,integrated_LUFS=float(m['input_i']),true_peak_dBTP=float(m['input_tp']),black=black,jumps=jumps,freezes=frozen,shot_cut_frames=cuts,visual_loop_MAE_255=seamdiff,audio_loop_step=step,normal_p95_step=normal,seam_rms_20ms=[rms(a[-882:]),rms(a[:882])])
Path('qa/measurements.json').write_text(json.dumps(report,indent=2));print(report,flush=True)
assert n==NFRAMES and wh==[1080,1920] and fps==30 and not black and not frozen and not jumps
assert abs(float(m['input_i'])+14)<1 and float(m['input_tp'])<=-1.5
assert seamdiff[2]<1 and step<normal
