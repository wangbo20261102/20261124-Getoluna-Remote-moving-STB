import json,pathlib,subprocess,sys,time,datetime
for svc in ('apex-robot','apex-teleop','apex-tool'):
    if subprocess.run(['systemctl','is-active','--quiet',svc]).returncode==0:
        raise SystemExit('Refusing second SDK owner: '+svc)
sys.path.insert(0,'/home/nvidia/tianji-robot-SDK/PYTHON_SDK')
from GentoRobot import GentoRobot,FXObjType,FXLogMask
out=pathlib.Path('/home/nvidia/luna-test-runs/20261125-mode3-right-arm-diagnostic');out.mkdir(parents=True,exist_ok=True)
r=GentoRobot(precision=6);result={'read_only':True,'time':datetime.datetime.now().isoformat(),'events':[]}
try:
    result['link']=r.link(6,6,7,190,FXLogMask.FX_LOG_ALL_FLAG)
    if result['link']<0:raise RuntimeError('Link failed')
    time.sleep(.6)
    result['sg']=r.get_sg_dict()
    for i in range(3):
        v={'rt':r.get_rt_dict(),'errors':{},'physical':{}}
        for side,obj in [('left',FXObjType.OBJ_ARM0),('right',FXObjType.OBJ_ARM1)]:
            v['errors'][side]=r.get_servo_error_codes(obj)
            v['physical'][side]=r.get_ctrl_obj_physical_state(obj)
        result['events'].append(v);time.sleep(.2)
    result['limits']={}
    for side,arm in [('left','A0'),('right','A1')]:
        result['limits'][side]=[{k:r.param_get_float(f'R.{arm}.L{j}.BASIC.{k}') for k in ('LimitNeg','LimitPos')} for j in range(7)]
finally:
    if r._connected:r.unlink()
    (out/'read-only.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print(json.dumps({'states':[a['state'] for a in result['events'][-1]['rt']['arms']],'errors':result['events'][-1]['errors'],'physical':result['events'][-1]['physical'],'limits':result.get('limits')},ensure_ascii=False))
