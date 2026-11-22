import json,math
from pathlib import Path
D=json.loads((Path(__file__).parent/'vo/timing.json').read_text())
FPS=30;NFRAMES=D['NFRAMES'];DUR=NFRAMES/FPS
def W(key,word=None):
    if word is None:return D['lines'][key][0]
    a,b=D['ranges'][key]
    for t,_,w,_,_ in D['words'][a:b]:
        if w.strip('.,?!').casefold()==word.casefold():return t
    raise KeyError((key,word))
SHOTS=[('hook',0),('hive',W('hive')-.07),('run',W('run')-.07),('angle',W('angle')-.07),
       ('map',W('angle','same')-.07),('duration',W('distance')-.06),('far',W('distance','farther')-.05),
       ('quiz',W('quiz')-.06)]
CUTS=[a for _,a in SHOTS]+[DUR]
def shot(t):
    k=max(i for i,(_,a) in enumerate(SHOTS) if a<=t+1e-8)
    key,a=SHOTS[k];b=CUTS[k+1]
    return key,max(0,min(1,(t-a)/(b-a))),a,b
def ease(x):
    x=max(0,min(1,x));return x*x*(3-2*x)
