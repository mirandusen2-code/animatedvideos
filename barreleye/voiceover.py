"""Generate a licensed synthetic male reference, then direct and verify individual takes."""
import os, sys, wave, json, re, difflib
from pathlib import Path
import numpy as np
from script import LINES
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
def norm(s): return re.findall(r"[a-z]+",s.lower().replace("’","'").replace("'",""))
def trim(x,sr):
 active=np.flatnonzero(np.abs(x)>.009)
 return x[max(0,active[0]-int(.012*sr)):active[-1]+int(.028*sr)]
if __name__=='__main__':
 if '--guide' in sys.argv:
  import onnxruntime as ort
  from kokoro_onnx import Kokoro
  op=ort.SessionOptions();op.intra_op_num_threads=3;op.inter_op_num_threads=1
  k=Kokoro.from_session(ort.InferenceSession(os.environ['KOKORO_MODEL'],sess_options=op,providers=['CPUExecutionProvider']),os.environ['KOKORO_VOICES'])
  x,sr=k.create("Watch the water just above his head. Something small is drifting down. Keep your eye on it.",voice="bm_george",speed=1.01,lang="en-gb")
  with wave.open('vo/reference.wav','wb') as f:
   f.setparams((1,2,sr,0,'NONE',''));f.writeframes((x*32000).astype('<i2').tobytes())
  sys.exit()
 import torch, soundfile as sf
 from chatterbox.tts import ChatterboxTTS
 from faster_whisper import WhisperModel
 torch.set_num_threads(3); model=ChatterboxTTS.from_pretrained('cpu');asr=WhisperModel('small.en',device='cpu',compute_type='int8',cpu_threads=3)
 for j,(key,spoken,_,pause) in enumerate(LINES):
  wav=Path('vo/clips')/(key+'.wav');audit=wav.with_suffix('.json')
  if wav.exists() and audit.exists():continue
  for attempt in range(5):
   torch.manual_seed(770+j+attempt*81)
   x=model.generate(spoken,audio_prompt_path='vo/reference.wav',exaggeration=.38+.025*attempt,cfg_weight=.45)[0].numpy()
   sf.write(wav,trim(x,model.sr),model.sr)
   seg,_=asr.transcribe(str(wav),language='en',beam_size=5,word_timestamps=True,condition_on_previous_text=False)
   rows=[(w.word.strip(),w.start,w.end) for s in seg for w in s.words];heard=' '.join(w[0] for w in rows)
   ratio=difflib.SequenceMatcher(None,norm(spoken),norm(heard)).ratio()
   print(key,attempt,ratio,heard,flush=True)
   if ratio>=.95:
    audit.write_text(json.dumps(dict(heard=heard,score=ratio,words=rows)));break
  else:raise RuntimeError(key+' failed ASR, review take')
