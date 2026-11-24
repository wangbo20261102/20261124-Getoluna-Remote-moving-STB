import ctypes,json,pathlib,subprocess,sys,time
for service in ('apex-robot','apex-teleop','apex-tool'):
    if subprocess.run(['systemctl','is-active','--quiet',service]).returncode==0:
        raise SystemExit('Refusing a second SDK owner while '+service+' is active')
sys.path.insert(0,'/home/nvidia/tianji-robot-SDK/PYTHON_SDK')
from GentoRobot import GentoRobot,FXObjType,error_dict
out=pathlib.Path('/home/nvidia/luna-incidents/20261124-right-gripper-power')
robot=GentoRobot(precision=6)
result={'read_only':True,'calls':['System_Link','GetLinkState','get_rt_dict','State_GetServoErrorCode','System_Unlink'],'motion_or_reset_calls':False}
try:
    result['link_result']=robot.link(6,6,7,190)
    if result['link_result']<0:raise RuntimeError('Controller SDK link failed')
    time.sleep(.5)
    result['rt_before']=robot.get_rt_dict()
    result['servo_errors']={}
    for side,obj in [('left',FXObjType.OBJ_ARM0),('right',FXObjType.OBJ_ARM1)]:
        ret,text=robot.get_servo_error_codes(obj)
        result['servo_errors'][side]={'ret':ret,'text':text}
    result['rt_after']=robot.get_rt_dict()
    print(json.dumps({'link_result':result['link_result'],'states':[arm.get('state') for arm in result['rt_after']['arms']],'servo_errors':result['servo_errors']},ensure_ascii=False),flush=True)
finally:
    robot.unlink()
    (out/'read-only-sdk-diagnostic.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
