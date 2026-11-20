"""Build the timed periodic narration, using full-track ASR and verified clip boundaries."""
import json,math,re,subprocess,shutil
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from faster_whisper import WhisperModel
from script import LINES
rate=44100
def norm(w):return re.sub('[^a-z0-9]','',w.lower().replace('’',"'"))
parts=[];meta=[];start=.10
for key,spoken,cap,pause in LINES:
 x,sr=sf.read('vo/clips/'+key+'.wav')
 x=resample_poly(x,rate//math.gcd(rate,sr),sr//math.gcd(rate,sr))
 ff=shutil.which('ffmpeg') or str(next(Path('/tmp/bpy/imageio_ffmpeg/binaries').glob('ffmpeg-linux*')))
 x=np.frombuffer(subprocess.run([ff,'-loglevel','error','-f','f32le','-ar',str(rate),'-ac','1','-i','-','-af','atempo=0.90','-f','f32le','-'],input=x.astype('<f4').tobytes(),stdout=subprocess.PIPE,check=True).stdout,dtype='<f4')
 raw=json.load(open('vo/clips/'+key+'.json'))
 assert raw['score']>=.95
 labels=[(w,w.strip('.,!?').isupper(),i==len(chunk.split())-1) for chunk in cap.split('|') for i,w in enumerate(chunk.split())]
 assert len(labels)==len(raw['words']),(key,labels,raw)
 parts.append((round(start*rate),x));meta.append((key,start,start+len(x)/rate,labels,raw['words']));start+=len(x)/rate+pause
out=np.zeros(round((start+.3)*rate))
for i,x in parts:out[i:i+len(x)]+=x
sf.write('vo/assembled.wav',out,rate)
model=WhisperModel('small.en',device='cpu',cpu_threads=3,compute_type='int8')
segments,_=model.transcribe('vo/assembled.wav',language='en',word_timestamps=True,beam_size=5,condition_on_previous_text=False)
heard=[(w.word.strip(),w.start,w.end) for s in segments for w in s.words];json.dump(heard,open('vo/whole-asr.json','w'))
pos=0;words=[];lines={};ranges={}
for key,a,b,labels,clip in meta:
 lo=len(words);prev=a
 for (label,hot,end),(_,u,v) in zip(labels,clip):
  begin,stop=a+u/.90,min(a+v/.90,b)
  if pos<len(heard) and norm(heard[pos][0])==norm(label):
   _,h1,h2=heard[pos];pos+=1
   if abs(h1-begin)<.20 and abs(h2-stop)<.22:begin,stop=max(a,h1),min(b,h2)
  begin=max(begin,prev);stop=max(begin+.008,stop);prev=stop
  words.append([round(begin,4),round(stop,4),label,hot,end])
 lines[key]=[words[lo][0],words[-1][1]];ranges[key]=[lo,len(words)]
# Preserve a quiet final consonant if the recogniser releases it early.
last=parts[-1][0]/rate+len(parts[-1][1])/rate
words[-1][1]=round(last,4);lines['loop'][1]=round(last,4)
N=round((last+.05)*30);ns=round(N/30*rate);sf.write('vo/narration.wav',out[:ns],rate)
json.dump(dict(lines=lines,words=words,ranges=ranges,NFRAMES=N,DUR=N/30),open('vo/timing.json','w'),indent=2)
print(N,N/30,lines,flush=True)
