import json
from websockets.sync.client import connect
with connect('ws://6.6.7.6:6001/api/AMR/State',proxy=None,open_timeout=3,close_timeout=1) as ws:
    for _ in range(25):
        state=json.loads(ws.recv(timeout=3)).get('Content',{})
        if isinstance(state,dict) and state.get('id')==1:
            names=('id','isNormal','workStatus','isScram','isSoftAuto','isPause','isSuspend','isParkingMode','isReseting','isFallback','linearSpeedVec3','angularSpeed')
            print(json.dumps({k:state.get(k) for k in names}),flush=True)
            break
