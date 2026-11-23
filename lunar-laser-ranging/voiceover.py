"""Render consistent male takes and assemble a pitch-preserving 22.7-second reading."""
import os
import json
import subprocess
from pathlib import Path
import numpy as np
import onnxruntime as ort
import soundfile as sf
from kokoro_onnx import Kokoro
from scipy.signal import resample_poly
from script import LINES

RATE = 44100
TARGET = 21.5
LEAD = 0.10
TAIL = 0.16

def main():
    out = Path('vo')
    out.mkdir(exist_ok=True)
    session = ort.SessionOptions()
    session.intra_op_num_threads = 3
    voice = Kokoro.from_session(ort.InferenceSession(os.environ['KOKORO_MODEL'], sess_options=session, providers=['CPUExecutionProvider']), os.environ['KOKORO_VOICES'])
    takes = []
    for key, spoken, _, pause in LINES:
        samples, rate = voice.create(spoken, voice='bm_george', speed=1.045, lang='en-gb')
        active = np.flatnonzero(np.abs(samples) > .006)
        samples = samples[max(0, active[0]-int(.018*rate)):min(len(samples),active[-1]+int(.045*rate))]
        takes.append((key, samples, rate, pause))
    pauses = sum(t[3] for t in takes)
    speed = sum(len(x)/r for _,x,r,_ in takes)/(TARGET-LEAD-TAIL-pauses)
    parts = [np.zeros(round(LEAD*RATE), np.float32)]
    starts = {}
    for key,x,r,pause in takes:
        p = subprocess.run(['ffmpeg','-v','error','-f','f32le','-ar',str(r),'-ac','1','-i','-','-af',f'atempo={speed:.8f}','-ar',str(RATE),'-f','f32le','-'],input=x.astype('<f4').tobytes(),stdout=subprocess.PIPE,check=True)
        x = np.frombuffer(p.stdout,dtype='<f4')
        start = sum(map(len,parts))/RATE
        starts[key] = [start,start+len(x)/RATE]
        sf.write(out/(key+'.wav'),x,RATE)
        parts.extend((x,np.zeros(round(pause*RATE),np.float32)))
    samples = np.concatenate(parts+[np.zeros(round(TAIL*RATE),np.float32)])
    frames = round(len(samples)/RATE*30)
    assert 600 <= frames <= 750
    samples = np.pad(samples,(0,max(0,1470*frames-len(samples))))[:1470*frames]
    sf.write(out/'narration.wav',samples,RATE,subtype='PCM_24')
    (out/'takes.json').write_text(json.dumps({'lines':starts,'frames':frames}))
if __name__=='__main__':
    main()
