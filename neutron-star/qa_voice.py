"""QA: transcribe every narration clip with Whisper and compare it with the script.
Usage (env with faster-whisper): python qa_voice.py <clips_dir>"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script import LINES
from faster_whisper import WhisperModel
import soundfile as sf
m = WhisperModel("small.en", device="cpu", compute_type="int8")
d = sys.argv[1]
def norm(s): return re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()
for key, spoken, *_ in LINES:
    p = os.path.join(d, f"{key}.wav")
    segs, _ = m.transcribe(p, beam_size=5, language="en")
    txt = " ".join(s.text.strip() for s in segs)
    a, b = norm(spoken), norm(txt)
    import difflib
    r = difflib.SequenceMatcher(None, a, b).ratio()
    x, sr = sf.read(p)
    print(f"{key:9s} {len(x)/sr:5.2f}s match {r:.2f} | {txt}")
