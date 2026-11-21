"""Review the native-frame contact sheets with cut marks and safe zones from post.py."""
from pathlib import Path
from PIL import Image,ImageDraw
import io,base64
from timeline import NFRAMES
files=sorted(Path('qa').glob('frames-*.jpg'));assert len(files)==(NFRAMES+39)//40
# Compact overview for an in-chat check; original sheets retain every frame.
sheet=Image.new('RGB',(600,((len(files)+2)//3)*160),'#172223')
for i,p in enumerate(files):
    with Image.open(p) as im:shot=im.resize((195,158),Image.Resampling.LANCZOS)
    sheet.paste(shot,((i%3)*200,(i//3)*160))
sheet.save('qa/contact-overview.jpg',quality=86)
