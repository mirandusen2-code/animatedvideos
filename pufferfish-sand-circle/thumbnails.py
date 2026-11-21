"""Three native 9:16 covers drawn from the film before captions."""
from PIL import Image,ImageDraw
from timeline import FPS,W
def choices():
    return {round(.59*FPS):('a',['A FISH','BUILT THIS']),round((W('where','male')+.65)*FPS):('b',['MEET THE','BUILDER']),round((W('ridges','hundreds')+.67)*FPS):('c',['SIX FEET','OF SAND'])}
def cover(im,lines):
    from post import font,guard
    d=ImageDraw.Draw(im)
    for j,s in enumerate(lines):
        sz=114
        while font(sz,900).getlength(s)>710:sz-=2
        f=font(sz,900);x=round(476-f.getlength(s)/2);y=339+j*123
        bounds=d.textbbox((x,y),s,font=f,anchor='lt',stroke_width=7)
        guard(bounds[0],bounds[1],bounds[2]-bounds[0],bounds[3]-bounds[1])
        d.text((x,y),s,font=f,anchor='lt',fill=(255,211,109) if j else (252,249,232),stroke_width=7,stroke_fill=(20,36,35))
    return im
