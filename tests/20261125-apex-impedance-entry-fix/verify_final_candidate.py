import json,pathlib,time,urllib.request,urllib.error
out=pathlib.Path('/home/nvidia/luna-test-runs/20261125-apex-impedance-entry-fix')
report={'events':[],'cycles':[],'home_calls':0,'reset_calls':0,'sdk_links':0,'success':False}
def api(path,data=None):
    req=urllib.request.Request('http://127.0.0.1:18080/api/v1'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError(str(e.code)+': '+e.read().decode())
def save(label,data):
    report['events'].append({'label':label,'time':time.time(),'data':data});(out/'final-candidate-live-verification.json').write_text(json.dumps(report,indent=2));print(label,json.dumps(data),flush=True)
try:
    for attempt in range(20):
        try:state=api('/robot/status');break
        except Exception:time.sleep(.25)
    save('before',state)
    if state['data']['arm_state'][:2]!=[2,2] or state['data']['control_error']:raise RuntimeError('Expected healthy existing PD hold; no test started')
    for tool_on in (False,True):
        save('tool_start' if tool_on else 'tool_stop',api('/modules/tool/'+('start' if tool_on else 'stop'),{}))
        save('idle',api('/robot/mode',{'mode':0}));time.sleep(.3)
        started=time.monotonic();reply=api('/robot/mode',{'mode':3});elapsed=time.monotonic()-started
        save('mode3_reply',{'tool_initially_active':tool_on,'duration_sec':elapsed,'reply':reply})
        if reply['data'].get('success') is not True:raise RuntimeError('Mode entry failed; no further cycle')
        samples=[]
        for i in range(6):
            time.sleep(.25);s=api('/robot/status')['data'];samples.append(s)
            if s['arm_state'][:2]!=[2,2] or s['control_error'] or s['arm_state_age_sec']>1:raise RuntimeError('Controller mode not maintained')
        modules=api('/modules')['data'];tool=next(m for m in modules if m['id']=='tool')
        if (tool['active_state']=='active')!=tool_on:raise RuntimeError('Tool prior state was not restored')
        report['cycles'].append({'tool_initially_active':tool_on,'duration_sec':elapsed,'samples':samples,'tool_after':tool['active_state']})
        save('cycle_passed',{'tool_initially_active':tool_on,'samples':len(samples)})
    report['success']=True
except BaseException as exc:
    report['exception']=repr(exc);print('VERIFICATION',repr(exc),flush=True)
finally:
    try:save('tool_final_stop',api('/modules/tool/stop',{}))
    except Exception as exc:report['final_stop_error']=repr(exc)
    (out/'final-candidate-live-verification.json').write_text(json.dumps(report,indent=2))
