import json,time
from websockets.sync.client import connect
last=None
end=time.monotonic()+35
maximum=[0.,0.,0.]
last_report=0
with connect('ws://6.6.7.6:6001/api/AMR/State',proxy=None,open_timeout=3,close_timeout=1) as ws:
    while time.monotonic()<end:
        state=json.loads(ws.recv(timeout=3)).get('Content',{})
        if not isinstance(state,dict) or state.get('id')!=1: continue
        v=state.get('linearSpeedVec3',{})
        speed=(round(float(v.get('x',0)),4),round(float(v.get('y',0)),4),round(float(state.get('angularSpeed',0)),4))
        maximum=[max(a,abs(b)) for a,b in zip(maximum,speed)]
        now=time.monotonic()
        if speed!=last and (speed==(0.,0.,0.) or now-last_report>0.5):
            print(json.dumps({'actual_velocity':speed,'scram':state.get('isScram'),'manual':state.get('workStatus')}),flush=True)
            last_report=now
        last=speed
print(json.dumps({'max_abs_observed':maximum,'last_velocity':last}),flush=True)
