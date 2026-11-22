"""Align the actual WAV at word boundaries, including number and compound spellings."""
import difflib
import json
import re
import sys
from pathlib import Path
from faster_whisper import WhisperModel
from script import LINES

def letters(word):
    return re.sub('[^a-z]', '', word.lower())

def transcribe(model,path):
    segs,_=model.transcribe(str(path),language='en',beam_size=5,word_timestamps=True,condition_on_previous_text=False)
    return [(w.word.strip(),w.start,w.end) for segment in segs for w in segment.words]

def align(words, heard, begin, end):
    want=''.join(letters(w) for w in words)
    positions=[]
    actual=''
    for w,a,b in heard:
        chars=letters(w)
        actual+=chars
        positions.extend((a+(b-a)*i/len(chars),a+(b-a)*(i+1)/len(chars)) for i in range(len(chars)))
    match=difflib.SequenceMatcher(None,want,actual,autojunk=False)
    assert match.ratio()>=.95, (words,heard,match.ratio())
    mapped={}
    for p,q,n in match.get_matching_blocks():
        for i in range(n):
            mapped[p+i]=positions[q+i]
    pointer=0
    rows=[]
    for w in words:
        n=len(letters(w))
        spans=[mapped[i] for i in range(pointer,pointer+n) if i in mapped]
        assert spans,(w,heard)
        rows.append([max(begin,spans[0][0]),min(end,spans[-1][1])])
        pointer+=n
    return rows

def main():
    model=WhisperModel('small.en',device='cpu',compute_type='int8',cpu_threads=3)
    if len(sys.argv)>1:
        path=Path(sys.argv[1])
        heard=transcribe(model,path)
        expected=' '.join(s for _,s,_,_ in LINES)
        ok=letters(expected)==letters(' '.join(w for w,_,_ in heard))
        Path('qa').mkdir(exist_ok=True)
        Path('qa/transcript.json').write_text(json.dumps({'exact':ok,'heard':' '.join(w for w,_,_ in heard),'expected':expected},indent=2))
        print('Final transcript:',ok,heard,flush=True)
        assert ok, 'Final mix transcript needs review'
        return
    takes=json.loads(Path('vo/takes.json').read_text())
    full=transcribe(model,'vo/narration.wav')
    results=[]; by_line={}; ranges={}; report={}
    for key,spoken,caption,_ in LINES:
        a,b=takes['lines'][key]
        heard=transcribe(model,Path('vo')/(key+'.wav'))
        report[key]=heard
        local=align(spoken.split(),[(w,a+x,a+y) for w,x,y in heard],a,b)
        nearby=[row for row in full if a-.045 <= (row[1]+row[2])/2 <= b+.045]
        try:
            absolute=align(spoken.split(),nearby,a,b)
        except AssertionError:
            absolute=local
        first=len(results)
        tags=[(w,w.isupper() or any(c.isdigit() for c in w),i==len(c.split())-1) for c in caption.split('|') for i,w in enumerate(c.split())]
        assert len(tags)==len(local)
        previous=a
        for (word,hot,chunk_end), (u,v), (x,y) in zip(tags, local, absolute):
            start=max(previous, x if abs(x-u)<.20 else u)
            stop=max(start+.006, y if abs(y-v)<.20 else v)
            results.append([round(start,4),round(stop,4),word,hot,chunk_end])
            previous=stop
        by_line[key]=[results[first][0],results[-1][1]]
        ranges[key]=[first,len(results)]
    Path('vo/timing.json').write_text(json.dumps({'lines':by_line,'words':results,'ranges':ranges,'NFRAMES':takes['frames'],'DUR':takes['frames']/30},indent=2))
    Path('vo/words-review.json').write_text(json.dumps({'clips':report,'full':full},indent=2))
    print('Aligned',takes['frames'],'frames',by_line,flush=True)
if __name__=='__main__':
    main()
