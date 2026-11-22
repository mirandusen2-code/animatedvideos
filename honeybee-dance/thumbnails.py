from PIL import ImageDraw
from timeline import FPS,W
def choices():
    return {round(.5*FPS):('a',['READ HER','DANCE']), round((W('angle','sun')-.25)*FPS):('b',['FOLLOW','THE SUN']), round((W('quiz')+.7)*FPS):('c',['WHICH WAY?'])}
def cover(im,lines):
    from post import font,guard
    d=ImageDraw.Draw(im)
    for i,s in enumerate(lines):
        size=112
        while font(size,900).getlength(s)>698:size-=2
        f=font(size,900);x=round(476-f.getlength(s)/2);y=348+i*117
        left,top,right,bottom=d.textbbox((x,y),s,anchor='lt',font=f,stroke_width=6)
        guard(left,top,right-left,bottom-top)
        d.text((x,y),s,font=f,anchor='lt',fill=(252,206,103) if i else (255,248,222),stroke_width=6,stroke_fill=(40,31,26))
    return im
