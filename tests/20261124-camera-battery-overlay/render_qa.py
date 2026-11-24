"""Offline rendering tests; never writes live battery input or display text."""
import json
from pathlib import Path
import subprocess
from battery_overlay import RUNTIME, atomic_write, display_state, video_filter

base=Path(__file__).resolve().parent
root=base/'qa'
root.mkdir(exist_ok=True)
for name, values, fresh in [('low-29-30', (29,30), True), ('stale', (50,50), False)]:
    directory=root/name
    directory.mkdir(exist_ok=True)
    data={'fresh':fresh,'seconds_since_feedback':.1,
          'batteries':[{'id':n,'energy':v,'is_connected':True,'is_in_place':True,
                        'is_charging':True,'error_code':0} for n,v in zip((1,2),values)]}
    state=display_state(data)
    for key,value in state['texts'].items(): atomic_write(directory/(key+'.txt'),value)
    atomic_write(directory/'state.json',json.dumps(state,ensure_ascii=False,indent=2))
    subprocess.run(['/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-y',
                    '-i',str(RUNTIME/'first-camera-frame.jpg'),'-vf',video_filter(directory)+',scale=1920:1080',
                    '-frames:v','1',str(root/(name+'.png'))],check=True)
print('Offline rendering ready; live data unchanged')
