"""Check rendered boundary frames, not the live battery input."""
import json
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parent/'qa'
counts={}
for phase in (0,10,20.3,20.9,30.3):
    im=Image.open(root/f'phase-{phase}.png').convert('RGB')
    turtle=sum(g>70 and g>r*1.3 and g>b*1.15
               for r,g,b in im.crop((1470,25,1860,95)).getdata())
    snail=sum(g>80 and r>g*1.12 and g>b*1.2
              for r,g,b in im.crop((1470,98,1860,168)).getdata())
    counts[str(phase)]={'turtle_colored_pixels':turtle,'snail_colored_pixels':snail}
assert counts['0']['turtle_colored_pixels']>100
assert counts['10']['turtle_colored_pixels']>100
assert counts['20.3']['turtle_colored_pixels']==0
assert counts['20.9']['turtle_colored_pixels']>100
assert counts['20.3']['snail_colored_pixels']>100
assert counts['30.3']['snail_colored_pixels']==0
(root/'boundary-render-check.json').write_text(json.dumps({'passed':True,'counts':counts},indent=2))
print(json.dumps({'passed':True,'counts':counts}))
