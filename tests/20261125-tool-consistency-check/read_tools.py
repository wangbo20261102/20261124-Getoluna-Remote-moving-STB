import datetime,json,pathlib,subprocess,sys,time,yaml
for svc in ('apex-robot','apex-teleop','apex-tool'):
    if subprocess.run(['systemctl','is-active','--quiet',svc]).returncode==0:raise SystemExit('Refusing second SDK owner: '+svc)
sys.path.insert(0,'/home/nvidia/tianji-robot-SDK/PYTHON_SDK')
from GentoRobot import GentoRobot,FXObjType
out=pathlib.Path('/home/nvidia/luna-test-runs/20261125-tool-consistency-check');out.mkdir(parents=True,exist_ok=True)
r=GentoRobot(precision=6)
result={'read_only':True,'time':datetime.datetime.now().isoformat(),'expected_dynamics':[1.8,0,0,0,0.004,0,0,0.004,0,0.03],'expected_kinematics':[0]*6,'samples':[]}
try:
    result['link']=r.link(6,6,7,190)
    if result['link']<0:raise RuntimeError('Link failed')
    time.sleep(.6)
    for i in range(3):
        rt=r.get_rt_dict();sg=r.get_sg_dict()
        result['samples'].append({'frame':rt['frame_serial'],'arms':[{'state':rt['arms'][a]['state'],'position':rt['arms'][a]['fb']['fb_pos'],'velocity':rt['arms'][a]['fb']['fb_vel'],'tool_dynamics':sg['arms'][a]['set']['tool_dyna'],'tool_kinematics':sg['arms'][a]['set']['tool_kine']} for a in (0,1)]})
        time.sleep(.2)
    result['servo_errors']={side:r.get_servo_error_codes(obj) for side,obj in [('left',FXObjType.OBJ_ARM0),('right',FXObjType.OBJ_ARM1)]}
finally:
    if r._connected:r.unlink()
    (out/'controller-tools-before.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,ensure_ascii=False),flush=True)
