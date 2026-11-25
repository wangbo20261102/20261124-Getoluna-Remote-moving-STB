import json,pathlib,time,urllib.request,urllib.error
import rclpy
from std_srvs.srv import Trigger
out=pathlib.Path('/home/nvidia/luna-test-runs/20261125-apex-impedance-entry-fix')
report={'events':[],'home_calls':0,'sdk_links':0,'reset_attempts':0}
def api(path,data=None):
    req=urllib.request.Request('http://127.0.0.1:18080/api/v1'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
def event(label,data):
    report['events'].append({'label':label,'time':time.time(),'data':data});(out/'candidate-live-verification.json').write_text(json.dumps(report,indent=2));print(label,json.dumps(data),flush=True)
try:
    event('before',api('/robot/status'))
    try:
        answer=api('/robot/mode',{'mode':3})
        raise RuntimeError('Fault guard unexpectedly accepted request: '+str(answer))
    except urllib.error.HTTPError as exc:
        event('fault_guard',{'http_status':exc.code,'body':exc.read().decode()})
        if exc.code!=503:raise
    rclpy.init();n=rclpy.create_node('apex_mode_repair_single_clear');c=n.create_client(Trigger,'/control/clear_fault')
    if not c.wait_for_service(timeout_sec=3):raise RuntimeError('Clear fault service unavailable')
    future=c.call_async(Trigger.Request());rclpy.spin_until_future_complete(n,future,timeout_sec=5)
    report['reset_attempts']=1
    if not future.done():raise RuntimeError('Clear request timed out')
    event('explicit_single_clear_reply',{'success':future.result().success,'message':future.result().message})
    n.destroy_node();rclpy.shutdown();time.sleep(.5)
    state=api('/robot/status');event('after_clear_feedback',state)
    if any(x not in (0,1,2) for x in state['data']['arm_state'][:2]):raise RuntimeError('Fault did not clear; no mode test sent')
    event('explicit_idle_reply',api('/robot/mode',{'mode':0}));time.sleep(.3)
    state=api('/robot/status');event('idle_feedback',state)
    if state['data']['arm_state'][:2]!=[0,0] or state['data']['control_error']:raise RuntimeError('Idle not confirmed')
    event('ready_reply',api('/robot/ready',{}))
    start=time.monotonic();result=api('/robot/mode',{'mode':3})
    event('apex_mode3_candidate_reply',{'duration_sec':time.monotonic()-start,'result':result})
    for i in range(6):
        time.sleep(.3);event('confirmed_sample_'+str(i),api('/robot/status'))
    report['success']=all(e['data']['data']['arm_state'][:2]==[2,2] and not e['data']['data']['control_error'] for e in report['events'] if e['label'].startswith('confirmed_sample')) and result['data'].get('success') is True
except BaseException as exc:
    report['exception']=repr(exc);report['success']=False;print('VERIFICATION',repr(exc),flush=True)
finally:
    (out/'candidate-live-verification.json').write_text(json.dumps(report,indent=2))
