"""Pack the imagegen 4x4 animation atlas into the UI playback format."""
from pathlib import Path
from PIL import Image
import math

base=Path(__file__).resolve().parent/'assets'
atlas=Image.open(base/'marmot-atlas.png').convert('RGBA')
w,h=atlas.size
size=(math.ceil(w/4),math.ceil(h/4))
frames=[];boxes=[]
for y in range(4):
    for x in range(4):
        cell=atlas.crop((round(x*w/4),round(y*h/4),round((x+1)*w/4),round((y+1)*h/4)))
        canvas=Image.new('RGBA',size);canvas.alpha_composite(cell)
        box=canvas.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox()
        if box is None:raise RuntimeError('Empty atlas cell')
        frames.append(canvas);boxes.append(box)
bounds=(max(0,min(b[0] for b in boxes)-4),max(0,min(b[1] for b in boxes)-3),
        min(size[0],max(b[2] for b in boxes)+4),min(size[1],max(b[3] for b in boxes)+3))
frames=[im.crop(bounds) for im in frames]
palette=frames[0].convert('RGB').quantize(colors=255)
encoded=[]
for rgba in frames:
    im=rgba.convert('RGB').quantize(palette=palette,dither=0)
    im.paste(255,mask=rgba.getchannel('A').point(lambda a:255 if a<128 else 0))
    im.putpalette((im.getpalette()+[0]*768)[:765]+[0,0,0]);encoded.append(im)
encoded[0].save(base/'marmots.gif',save_all=True,append_images=encoded[1:],duration=80,
                loop=0,transparency=255,disposal=2,optimize=False)
print({'atlas_size':atlas.size,'frame_size':frames[0].size,'frames':len(encoded)})
