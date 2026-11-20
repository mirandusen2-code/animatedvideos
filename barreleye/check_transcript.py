import json,re,pathlib,sys
from faster_whisper import WhisperModel
from script import LINES
m=WhisperModel('small.en',device='cpu',compute_type='int8',cpu_threads=3)
segments,_=m.transcribe('barreleye.mp4',language='en',beam_size=5,word_timestamps=True,condition_on_previous_text=False)
txt=' '.join(s.text.strip() for s in segments)
def words(s):return re.findall(r'[a-z]+',s.lower().replace('’','').replace("'",""))
want=' '.join(x[1] for x in LINES)
ok=words(txt)==words(want);pathlib.Path('qa/final-asr.json').write_text(json.dumps(dict(transcript=txt,expected=want,word_for_word=ok),indent=2))
print(ok,txt);assert ok
