"""Measure the actual muxed file, excluding intended camera cuts in the jump test."""
from pathlib import Path
import json,subprocess,math
import numpy as np
from PIL import Image
from timeline import CUTS,DUR,FPS,NFRAMES
from post import loudness,ff,SR,NS
movie='honeybee-dance.mp4'
p=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',movie]))
v=next(s for s in p['streams'] if s['codec_type']=='video')
a=next(s for s in p['streams'] if s['codec_type']=='audio')
assert (v['codec_name'],v['width'],v['height'],v['pix_fmt'],v['r_frame_rate'])==('h264',1080,1920,'yuv420p','30/1')
assert a['codec_name']=='aac' and 600<=NFRAMES<=750
raw=ff(['-v','error','-i',movie,'-an','-vf','scale=90:160:flags=area','-pix_fmt','gray','-f','rawvideo','-'],stdout=subprocess.PIPE).stdout
images=np.frombuffer(raw,np.uint8).reshape(-1,160,90)
assert len(images)==NFRAMES
diff=np.abs(np.diff(images.astype('f'),axis=0)).mean(axis=(1,2))
cuts=[round(x*FPS) for x in CUTS]
jumps=[i+1 for i,m in enumerate(diff) if m>15 and min(abs(i+1-k) for k in cuts)>2]
frozen=[];start=None
for i,q in enumerate([*diff,2]):
    if q<.035 and start is None:start=i
    elif q>=.035 and start is not None:
        if i-start>=12:frozen.append([start,i])
        start=None
black=np.where(images.mean(axis=(1,2))<8)[0].tolist()
seam=[np.asarray(Image.open('qa/seam-%04d.png'%i),dtype='f') for i in [NFRAMES-3,NFRAMES-2,NFRAMES-1,0,1]]
mae=[round(float(np.abs(b-a).mean()),4) for a,b in zip(seam,seam[1:])]
x=np.frombuffer(ff(['-v','error','-i',movie,'-vn','-ac','1','-ar',str(SR),'-f','f32le','-'],stdout=subprocess.PIPE).stdout,'<f4')[:NS]
l=loudness(movie)
q=dict(frames=NFRAMES,seconds=DUR,fps=FPS,size=[1080,1920],integrated_LUFS=float(l['input_i']),true_peak_dBTP=float(l['input_tp']),black=black,unexpected_jumps=jumps,freezes=frozen,seam_raw_MAE=mae,audio_seam_step=float(abs(x[-1]-x[0])),audio_step_p95=float(np.percentile(np.abs(np.diff(x)),95)),aac_bit_rate=int(a['bit_rate']))
Path('qa/measurements.json').write_text(json.dumps(q,indent=2));print(q,flush=True)
assert not (jumps or frozen or black),q
assert abs(q['integrated_LUFS']+14)<.45 and q['true_peak_dBTP']<=-1.5
assert mae[2]<5,q
