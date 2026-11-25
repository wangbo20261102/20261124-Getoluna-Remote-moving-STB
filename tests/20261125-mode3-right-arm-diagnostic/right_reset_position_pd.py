import datetime,json,math,pathlib,subprocess,sys,time,yaml
for svc in ('apex-robot','apex-teleop','apex-tool'):
    if subprocess.run(['systemctl','is-active','--quiet',svc]).returncode==0:raise SystemExit('Refusing second SDK owner: '+svc)
sys.path.insert(0,'/home/nvidia/tianji-robot-SDK/PYTHON_SDK')
from GentoRobot import GentoRobot,FXObjType,FXLogMask,error_dict
out=pathlib.Path('/home/nvidia/luna-test-runs/20261125-mode3-right-arm-diagnostic')
cfg=yaml.safe_load(pathlib.Path('/opt/kernelmind/apex/install/marvin_ros_control/share/marvin_ros_control/config/robot_param_luna.yaml').read_text())['/**']['ros__parameters']
r=GentoRobot(precision=6);obj=FXObjType.OBJ_ARM1
res={'time':datetime.datetime.now().isoformat(),'test':'single standard reset, current-position hold, PD only if hold succeeds; then idle','home_calls':0,'persistent_parameter_writes':0,'events':[]}
def snap(label):
    v={'label':label,'time':datetime.datetime.now().isoformat(),'rt':r.get_rt_dict(),'sg':r.get_sg_dict(),'right_servo_errors':r.get_servo_error_codes(obj),'right_physical':r.get_ctrl_obj_physical_state(obj)}
    res['events'].append(v)
    (out/'right-reset-position-pd.json').write_text(json.dumps(res,indent=2))
    print(json.dumps({'label':label,'states':[a['state'] for a in v['rt']['arms']],'right_errors':v['right_servo_errors']},ensure_ascii=False),flush=True)
    return v
try:
    res['link']=r.link(6,6,7,190,FXLogMask.FX_LOG_ALL_FLAG)
    if res['link']<0:raise RuntimeError('Controller link failed')
    time.sleep(.5);v=snap('before')
    if v['rt']['arms'][0]['state']['cur']!=0 or v['rt']['arms'][1]['state']['cur'] not in (0,100):raise RuntimeError('Unexpected current state')
    if v['rt']['arms'][1]['state']['cur']==100:
        res['reset_ret']=r.reset_error(obj,2000)
        time.sleep(.5);v=snap('after_single_reset')
        if res['reset_ret']!=(0,0) or v['rt']['arms'][1]['state']['cur']!=0:raise RuntimeError('Reset did not restore idle')
    ret,text=v['right_servo_errors']
    if ret or len(text.splitlines())!=7 or any('0x0000 - No error' not in line for line in text.splitlines()):raise RuntimeError('Existing right drive error')
    q=v['rt']['arms'][1]['fb']['fb_pos'];vel=v['rt']['arms'][1]['fb']['fb_vel']
    if max(abs(x) for x in vel)>.5:raise RuntimeError('Arm moving')
    for j,a in enumerate(q):
        rn,lo=r.param_get_float(f'R.A1.L{j}.BASIC.LimitNeg');rp,hi=r.param_get_float(f'R.A1.L{j}.BASIC.LimitPos')
        if rn or rp or not math.isfinite(a) or not lo+1<a<hi-1:raise RuntimeError('Joint limit margin check failed')
    res['known_tool_dynamics']=cfg['right_tool']
    res['tool_set_ret']=r.runtime_set_tool_d(obj,cfg['right_tool'])
    res['seed_ret']=r.runtime_set_joint_pos_cmd(obj,q)
    res['seed_target_deg']=q
    if res['tool_set_ret'] or res['seed_ret']:raise RuntimeError('Runtime preparation failed')
    time.sleep(.2);snap('after_runtime_preparation')
    res['pd_gains']={'k':cfg['right_pd']['k'],'d':cfg['right_pd']['d']}
    res['position_ret']=r.switch_to_position_mode(obj,2000,1,1)
    time.sleep(.3);v=snap('after_position_hold')
    if res['position_ret'] or v['rt']['arms'][1]['state']['cur']!=1:raise RuntimeError('Static position enable failed; no PD attempt')
    if max(abs(a-b) for a,b in zip(q,v['rt']['arms'][1]['fb']['fb_pos']))>2:raise RuntimeError('Unexpected displacement; no PD attempt')
    res['pd_ret']=r.switch_to_pd_mode(obj,1500,1,1,cfg['right_pd']['k'],cfg['right_pd']['d'])
    for i in range(3):
        time.sleep(.15);snap('after_pd_'+str(i))
except BaseException as exc:
    res['exception']=repr(exc);print('DIAGNOSTIC:',repr(exc),flush=True)
finally:
    if r._connected:
        if r.current_state(obj) in (1,2,11):
            res['return_idle_ret']=r.switch_to_idle(obj,1500);time.sleep(.2)
        snap('final_before_unlink');r.unlink()
    (out/'right-reset-position-pd.json').write_text(json.dumps(res,indent=2))


