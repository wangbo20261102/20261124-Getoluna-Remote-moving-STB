import json,pathlib,subprocess,sys,time
for svc in ('apex-robot','apex-teleop','apex-tool'):
    if subprocess.run(['systemctl','is-active','--quiet',svc]).returncode==0:raise SystemExit('SDK owner active: '+svc)
sys.path.insert(0,'/home/nvidia/tianji-robot-SDK/PYTHON_SDK')
from GentoRobot import GentoRobot
robot=GentoRobot(precision=6)
data={'read_only':True,'parameter_writes':0,'motion_commands':0}
try:
    data['link']=robot.link(6,6,7,190)
    if data['link']<0:raise RuntimeError('Link failed')
    time.sleep(.3)
    data['feedback']=robot.get_rt_dict()
    data['limits']={}
    for arm in (0,1):
        rows=[]
        for joint in range(7):
            row={'joint':joint+1}
            for key in ('LimitNeg','LimitPos'):
                ret,value=robot.param_get_float(f'R.A{arm}.L{joint}.BASIC.{key}')
                if ret:raise RuntimeError(f'Limit read failed: arm{arm} J{joint+1} {key} ret={ret}')
                row[key]=value
            row['actual']=data['feedback']['arms'][arm]['fb']['fb_pos'][joint]
            row['inside']=row['LimitNeg']<=row['actual']<=row['LimitPos']
            rows.append(row)
        data['limits'][str(arm)]=rows
    print(json.dumps({'states':[a['state'] for a in data['feedback']['arms']],'limits':data['limits']},ensure_ascii=False),flush=True)
finally:
    robot.unlink()
    pathlib.Path('/home/nvidia/luna-incidents/20261124-right-gripper-power/current-joint-limits.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
