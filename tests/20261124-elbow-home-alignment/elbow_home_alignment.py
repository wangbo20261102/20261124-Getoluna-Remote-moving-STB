"""Torso-frame elbow calibration. No robot commands or hardware access."""
import json
from pathlib import Path
import numpy as np

HOME={'left_elbow':np.array([0.0002057573,0.2568665801,-0.1490945009]),
      'right_elbow':np.array([0.0002073629,-0.2568665801,-0.1490944996])}

def rotation(q):
    a=np.array([q['w'],q['x'],q['y'],q['z']],dtype=float)
    if not np.isfinite(a).all() or np.linalg.norm(a)<.5:raise ValueError('Invalid torso rotation')
    w,x,y,z=a/np.linalg.norm(a)
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

class ElbowHomeAlignment:
    def __init__(self,enabled=False,state_file=None):
        self.enabled=enabled;self.path=Path(state_file) if state_file else None
        self.offsets=None;self.armed=False;self.samples=[];self.last_body=float('-inf')
        self.error=None
        if self.path and self.path.exists():
            try:
                state=json.loads(self.path.read_text())
                offsets={k:np.array(state['offsets'][k],dtype=float) for k in HOME}
                if state.get('version')!=1 or any(v.shape!=(3,) or not np.isfinite(v).all() or np.linalg.norm(v)>.5 for v in offsets.values()):raise ValueError('Invalid saved calibration')
                self.offsets=offsets
            except (ValueError,KeyError,OSError,TypeError) as e:self.error=str(e)

    def request(self):
        self.offsets=None;self.samples=[];self.armed=True;self.error=None

    def ready(self,now):
        return not self.enabled or (self.offsets is not None and now-self.last_body<.3)

    def observe(self,positions,orientation,released,now):
        if not self.enabled:return positions
        if any(k not in positions for k in ['torso',*HOME]):return positions
        R=rotation(orientation);origin=np.asarray(positions['torso'])
        local=np.array([R.T@(np.asarray(positions[k])-origin) for k in HOME])
        if not np.isfinite(local).all():raise ValueError('Invalid elbow position')
        self.last_body=now
        if self.armed:
            if not released:self.samples=[]
            else:
                self.samples.append((now,local.copy()))
                self.samples=self.samples[-100:]
                values=np.array([s[1] for s in self.samples])
                if np.max(np.ptp(values,axis=0))>.015:
                    self.samples=[(now,local.copy())]
                elif len(self.samples)>=10 and now-self.samples[0][0]>=.75:
                    average=values.mean(axis=0)
                    offsets={k:HOME[k]-average[i] for i,k in enumerate(HOME)}
                    if any(np.linalg.norm(v)>.5 for v in offsets.values()):
                        self.error='Neutral posture too far from Home; calibration rejected'
                        self.armed=False
                    else:
                        # Persist before publishing a ready state; no partial calibration.
                        if self.path:
                            record={'version':1,'offsets':{k:v.tolist() for k,v in offsets.items()},
                                    'reference':{k:average[i].tolist() for i,k in enumerate(HOME)},
                                    'home':{k:v.tolist() for k,v in HOME.items()}}
                            tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(record,indent=2));tmp.replace(self.path)
                        self.offsets=offsets;self.armed=False
        result=dict(positions)
        if self.offsets is not None:
            for k in HOME:result[k]=np.asarray(positions[k])+R@self.offsets[k]
        return result

    def status(self,now):
        return {'enabled':self.enabled,'calibrated':self.offsets is not None,'ready':self.ready(now),
                'collecting':self.armed,'samples':len(self.samples),'error':self.error,
                'offsets':None if self.offsets is None else {k:v.tolist() for k,v in self.offsets.items()}}
