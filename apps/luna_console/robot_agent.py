#!/usr/bin/env python3
"""Allowlisted console transport. Reuses Apex; never opens another robot SDK."""
import argparse
import base64
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import qos_profile_sensor_data
from rcl_interfaces.srv import GetParameters, ListParameters
from rosidl_runtime_py.convert import message_to_ordereddict
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Bool, Int32MultiArray, String
from std_srvs.srv import Trigger
from marvin_msgs.msg import Jointfeedback
from PIL import Image
import yaml

VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parent
RUN = Path('/run/user/1000/luna-unified-console')
RUN.mkdir(exist_ok=True)
CANCEL = RUN / 'cancel'
API = 'http://127.0.0.1:8080/api/v1'
APPROVED_SDK = '07cecbce36ebcd89e915cf5a7f274db2159251f68dcab83d707a5d3f7a85aa43'
SDK = Path('/usr/local/lib/luna-apex-wrist/sdk/libGentoSDK.so')
FILES = {
 'Robot 控制/工具/阻抗': '/opt/kernelmind/apex/install/marvin_ros_control/share/marvin_ros_control/config/robot_param_luna.yaml',
 'PICO 缩放与映射': '/opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/config/luna/robot_param.yaml',
 'Home 肘部锚点': '/home/nvidia/luna-test-runs/20261124-elbow-home-alignment/calibration.json',
 'QP 控制器': '/opt/kernelmind/apex/install/marvin_qp_controller/share/marvin_qp_controller/config/luna/robot_param.yaml',
 'IK 任务': '/opt/kernelmind/apex/install/marvin_qp_controller/share/marvin_qp_controller/config/luna/ik_tasks.yaml',
 '碰撞对': '/opt/kernelmind/apex/install/marvin_qp_controller/share/marvin_qp_controller/config/luna/collision_pairs.json',
 '彩色摄像头': '/home/nvidia/d435-preview/apex-color1080.yaml',
 '充电动画': '/home/nvidia/luna-test-runs/20261124-camera-fast-marmots/animations.json',
 '底盘启动与上限': '/home/nvidia/luna-test-runs/20261124-full-body-cooperation/start_manual_chassis.sh',
 '底盘桥程序与保护': '/home/nvidia/luna-test-runs/20261124-full-body-cooperation/pico_chassis_bridge.py',
 '摄像头固定身份': '/etc/systemd/system/apex-camera.service.d/70-d435-device.conf',
 'MAXHUB 开机恢复': '/home/nvidia/.config/systemd/user/luna-maxhub-client.service',
 '显示预览服务': '/home/nvidia/.config/systemd/user/luna-camera-fast-marmots.service',
 '充电语音服务': '/home/nvidia/.config/systemd/user/luna-battery-voice-warning.service',
 'PICO 底盘持久服务': '/etc/systemd/system/luna-pico-manual-chassis.service',
}
SYSTEM_UNITS = ['apex-backend.service','apex-camera.service','apex-robot.service','apex-teleop.service','apex-tool.service','luna-pico-manual-chassis.service']
USER_UNITS = ['luna-maxhub-client.service','luna-camera-fast-marmots.service','luna-battery-voice-warning.service']
MODE_NAMES = {0:'待机',1:'位置',2:'阻抗'}

def read_json(path):
    try: return json.loads(Path(path).read_text())
    except (OSError, ValueError): return None

def shell(args, timeout=12):
    p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    if p.returncode: raise RuntimeError(p.stdout.strip()[-1000:] or f'{args[0]} 返回 {p.returncode}')
    return p.stdout

def api(path, body=None):
    req = urllib.request.Request(API+path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'}, method='GET' if body is None else 'POST')
    try:
        with urllib.request.urlopen(req, timeout=12) as response: value=json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode(errors='replace')[:700]) from exc
    if value.get('ok') is False: raise RuntimeError(str(value.get('error',value)))
    data=value.get('data',value)
    if isinstance(data,dict) and data.get('success') is False: raise RuntimeError(str(data.get('message') or data.get('error') or data))
    return data

def parameter_value(v):
    return {1:v.bool_value,2:v.integer_value,3:v.double_value,4:v.string_value,5:list(v.byte_array_value),6:list(v.bool_array_value),7:list(v.integer_array_value),8:list(v.double_array_value),9:list(v.string_array_value)}.get(v.type)

class Agent:
    def __init__(self, video=False):
        rclpy.init()
        self.node=rclpy.create_node('luna_console_video' if video else 'luna_console_control')
        self.code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.node.get_logger().set_level(rclpy.logging.LoggingSeverity.WARN)
        self.executor=MultiThreadedExecutor(num_threads=2)
        self.executor.add_node(self.node)
        self.thread=threading.Thread(target=self.executor.spin,daemon=True);self.thread.start()
        self.lock=threading.Lock();self.latest={};self.frame=None;self.frame_time=0
        self.service_cache=None;self.service_time=0
        self.sdk_hash=hashlib.sha256(SDK.read_bytes()).hexdigest() if SDK.exists() else None
        self.sdk_mtime=SDK.stat().st_mtime_ns if SDK.exists() else None
        self.model_limits=self.limits()
        self.subs=[]
        if video:
            self.subs.append(self.node.create_subscription(CompressedImage,'/quad_tile/compressed',self.on_frame,qos_profile_sensor_data))
        else:
            for topic,kind in [('/info/joint_feedback',Jointfeedback),('/info/vr_connected',Bool),('/control/enableL',Bool),('/control/enableR',Bool),('/info/wrist485_L',Int32MultiArray),('/info/wrist485_R',Int32MultiArray),('/info/pico_elbow_home_alignment',String)]:
                self.subs.append(self.node.create_subscription(kind,topic,lambda msg,t=topic:self.on_topic(t,msg),qos_profile_sensor_data))

    def on_topic(self,topic,msg):
        with self.lock:self.latest[topic]={'age_base':time.monotonic(),'data':message_to_ordereddict(msg)}

    def on_frame(self,msg):
        with self.lock:self.frame=bytes(msg.data);self.frame_time=time.monotonic()

    def limits(self):
        p=Path('/opt/kernelmind/apex/install/marvin_description/share/marvin_description/mjcf/Gento_Luna/Gento_Luna.xml')
        result={}
        try:
            root=ET.parse(p).getroot();compiler=root.find('compiler');radians=compiler is not None and compiler.get('angle')=='radian'
            for joint in root.iter('joint'):
                if joint.get('name') and joint.get('range'):
                    bounds=[float(x) for x in joint.get('range').split()]
                    result[joint.get('name')]=[math.degrees(x) for x in bounds] if radians else bounds
        except Exception:pass
        return result

    def services(self):
        if self.service_cache and time.monotonic()-self.service_time<2:return self.service_cache
        result={}
        for user,units in [(False,SYSTEM_UNITS),(True,USER_UNITS)]:
            cmd=['systemctl']+(['--user'] if user else [])+['show',*units,'-p','Id','-p','ActiveState','-p','MainPID','-p','UnitFileState']
            out=shell(cmd)
            for block in out.strip().split('\n\n'):
                row=dict(line.split('=',1) for line in block.splitlines() if '=' in line)
                if 'Id' in row:result[row['Id']]=row
        self.service_cache=result;self.service_time=time.monotonic();return result

    def status(self):
        if SDK.exists() and SDK.stat().st_mtime_ns!=self.sdk_mtime:
            self.sdk_hash=hashlib.sha256(SDK.read_bytes()).hexdigest();self.sdk_mtime=SDK.stat().st_mtime_ns
        now=time.monotonic()
        with self.lock:topics={t:{'age':round(now-v['age_base'],3),'data':v['data']} for t,v in self.latest.items()}
        battery=read_json('/run/luna-battery-screen/status.json')
        # The source JSON's own fresh flag can be stale if its writer has exited.
        if battery:
            try:age=max(0,time.time()-Path('/run/luna-battery-screen/status.json').stat().st_mtime)
            except OSError:age=1e9
            battery['console_file_age']=age
            battery['fresh']=bool(battery.get('fresh')) and age<4
        return {'version':VERSION,'received_at':time.time(),'robot':api('/robot/status'),'battery':battery,'services':self.services(),'topics':topics,'sdk_sha256':self.sdk_hash,'sdk_approved':self.sdk_hash==APPROVED_SDK,'maxhub':read_json('/run/user/1000/luna-maxhub-client/status.json'),'display':read_json('/run/user/1000/luna-camera-fast-marmots/display-state.json'),'model_limits_deg':self.model_limits,'j6_controller_limit_record_deg':[-60,60]}

    def call(self,kind,path,req,timeout=3):
        client=self.node.create_client(kind,path)
        try:
            if not client.wait_for_service(timeout_sec=.7):return None
            future=client.call_async(req);event=threading.Event();future.add_done_callback(lambda _:event.set())
            if not event.wait(timeout):raise RuntimeError(f'接口响应超时：{path}')
            return future.result()
        finally:self.node.destroy_client(client)

    def parameters(self):
        files=[]
        for label,name in FILES.items():
            p=Path(name)
            try:
                b=p.read_bytes();text=b.decode('utf-8',errors='replace')
                parsed=yaml.safe_load(text) if p.suffix in ['.yaml','.yml','.json'] else None
                files.append({'label':label,'path':name,'sha256':hashlib.sha256(b).hexdigest(),'text':text,'values':parsed})
            except Exception as exc:files.append({'label':label,'path':name,'error':str(exc)})
        live={}
        nodes={'marvin_robot_node':['left_tool','right_tool','left_pd.k','left_pd.d','right_pd.k','right_pd.d','body_pd.k','body_pd.d','speed_ratio','accel_ratio','robot_ip','pd_cmd_cycle_time_ms'],
               'VR_reader':['human_scale_table.left_hand','human_scale_table.right_hand','human_scale_table.left_elbow','human_scale_table.right_elbow','robot_height','body_retarget_mode','elbow_home_alignment.enabled','elbow_home_alignment.state_file']}
        for path,types in self.node.get_service_names_and_types():
            if path.endswith('/get_parameters') and 'rcl_interfaces/srv/GetParameters' in types:
                name=path[1:-len('/get_parameters')]
                if name and not name.startswith('luna_console_'):nodes.setdefault(name,[])
        for node,names in nodes.items():
            listed=self.call(ListParameters,f'/{node}/list_parameters',ListParameters.Request(depth=0),timeout=2)
            if listed is not None:names=sorted(set(names)|set(listed.result.names))
            answer=self.call(GetParameters,f'/{node}/get_parameters',GetParameters.Request(names=list(names)))
            live[node]=None if answer is None else {name:parameter_value(value) for name,value in zip(names,answer.values)}
        caps=None
        try:
            url='http://6.6.7.6:8080/api/Config/AMR/GetParam'
            request=urllib.request.Request(url,data=b'{}',headers={'Content-Type':'application/json'})
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=2) as response:configuration=json.load(response)
            if configuration.get('ErrorCode')!=0:raise RuntimeError('厂家底盘参数接口未返回成功')
            values=configuration['Content']
            # Network credentials are not needed for motion-parameter inspection/export.
            values={k:('***' if any(x in k.lower() for x in ['password','passwd','token','secret']) else v) for k,v in values.items()}
            text=json.dumps(values,ensure_ascii=False,indent=2)
            files.append({'label':'底盘厂家参数（只读）','path':url,'sha256':hashlib.sha256(text.encode()).hexdigest(),'text':text,'values':values})
            caps={'linear':min(float(values['max_speed.linear']),.2),'angular':min(float(values['max_speed.angular']),.2),'avoid_enabled':values.get('robot.manual_move.enable_avoid')}
        except Exception as exc:files.append({'label':'底盘厂家参数（只读）','path':'6.6.7.6 / GetParam','error':str(exc)})
        return {'files':files,'live':live,'chassis_effective_caps':caps,'model_limits_deg':self.model_limits,'notes':['参数页为只读；配置文件与运行时读回分开显示。','模型限位不等于厂家固件完整限位读回；两侧 J6 历史实读 ±60°。','本控制台不另开 SDK，不写工具负载、刚度、关节限位或厂家电池阈值。']}

    def preflight(self):
        s=self.status();checks=[]
        b=s['battery'];fresh=bool(b and b.get('fresh'))
        rows=b.get('batteries',[]) if fresh else []
        low=[x for x in rows if x.get('is_connected') and x.get('is_in_place') and x.get('energy',101)<30]
        if low:checks.append({'level':'warn','text':'电量低于 30%，请优先充电；本项目有低电量相关报警历史'})
        valid=fresh and len(rows)==2 and all(r.get('is_connected') and r.get('is_in_place') and r.get('energy') is not None for r in rows)
        checks.append({'level':'ok' if valid else 'error','text':'两块电池反馈新鲜' if valid else '无法判断当前电量，请检查机器人连接'})
        checks.append({'level':'ok' if s['sdk_approved'] else 'error','text':'夹爪 SDK 与已验证版本一致' if s['sdk_approved'] else 'SDK 版本与已验证版本不同，暂不允许就绪'})
        state=s['robot'];checks.append({'level':'error' if state.get('control_error') else 'ok','text':state.get('control_error_message') or '当前未报告控制故障'})
        fb=s['topics'].get('/info/joint_feedback')
        if fb and fb['age']<1:
            pos=fb['data'].get('arm_positions',[])
            for index,name in [(5,'左 J6'),(12,'右 J6')]:
                value=math.degrees(pos[index]) if len(pos)>index else float('nan')
                checks.append({'level':'ok' if math.isfinite(value) and abs(value)<=60 else 'error','text':f'{name}：{value:.2f}°，厂家记录限位 ±60°'})
        else:checks.append({'level':'warn','text':'关节反馈尚不可用；启动 Robot 后会再次核对'})
        checks.append({'level':'ok','text':'底盘沿用原 0.2 m/s、0.2 rad/s；启动/重连仍须摇杆回中'})
        checks.append({'level':'ok','text':'打开控制台不执行 Home，不自动使能或动作夹爪'})
        return {'status':s,'checks':checks,'passed':not any(c['level']=='error' for c in checks)}

    def support(self,args):
        if args.get('supported') is not True:raise RuntimeError('请先确认双腕已支撑、手柄已松开')

    def checkpoint(self):
        if CANCEL.exists():raise RuntimeError('操作已被暂停；保留 Robot 当前模式')

    def robot_fresh(self,allow_fault=False):
        s=api('/robot/status')
        if s.get('arm_state_age_sec') is None or s['arm_state_age_sec']>1:raise RuntimeError('控制器反馈已过期，未执行操作')
        if s.get('control_error') and not allow_fault:raise RuntimeError(s.get('control_error_message') or '控制器报错，未执行操作')
        return s

    def require_arm_feedback(self):
        deadline=time.monotonic()+2
        while True:
            self.checkpoint()
            with self.lock:row=self.latest.get('/info/joint_feedback')
            if row and time.monotonic()-row['age_base']<1:
                positions=row['data'].get('arm_positions',[])
                if len(positions)<14 or not all(math.isfinite(x) for x in positions):raise RuntimeError('双臂关节反馈无效，未执行使能/运动请求')
                if any(abs(math.degrees(positions[i]))>60 for i in [5,12]):raise RuntimeError('J6 超出厂家记录 ±60°，请保持支撑并检查；不自动归位或放宽限位')
                return
            if time.monotonic()>=deadline:raise RuntimeError('没有新鲜的双臂关节反馈，未执行使能/运动请求')
            time.sleep(.05)

    def wait_robot(self,predicate,seconds=10):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            self.checkpoint();state=api('/robot/status')
            if predicate(state):return state
            time.sleep(.25)
        raise RuntimeError('等待控制器状态超时，请读取状态后检查；未执行 Home')

    def action(self,command,args):
        if command=='pause':
            CANCEL.touch();result=[]
            # Stop input producers, preserve Robot and the wrist holding mode.
            for module in ['teleop','tool']:
                try:result.append(api('/modules/'+module+'/stop',{}))
                except Exception as exc:result.append({'error':str(exc)})
            self.service_time=0
            return {'message':'遥操输入已请求停止；Robot 模式与投屏保持','results':result,'state':api('/robot/status')}
        with (RUN/'action.lock').open('w') as guard:
            try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('另一个控制操作正在进行，请稍后；暂停遥操仍可使用')
            if CANCEL.exists():CANCEL.unlink()
            if command=='display':
                api('/modules/camera/start',{})
                shell(['systemctl','--user','start','luna-maxhub-client.service','luna-camera-fast-marmots.service','luna-battery-voice-warning.service'])
                return {'message':'摄像头、MAXHUB、电量显示服务已就绪'}
            self.support(args)
            if command in ['ready','prepare']:
                report=self.preflight()
                if not report['passed']:raise RuntimeError('预检未通过：'+'；'.join(c['text'] for c in report['checks'] if c['level']=='error'))
                self.checkpoint();api('/modules/camera/start',{})
                self.checkpoint();api('/modules/robot/start',{})
                self.wait_robot(lambda s:s.get('arm_state_age_sec') is not None and s['arm_state_age_sec']<1)
                self.checkpoint();api('/robot/ready',{})
                self.wait_robot(lambda s:s.get('control_ready') and all(v>=0 for v in s.get('arm_state') or [-1]))
                report=self.preflight()
                if not report['passed']:raise RuntimeError('就绪后预检未通过：'+'；'.join(c['text'] for c in report['checks'] if c['level']=='error'))
                if command=='ready':return {'message':'Robot 已连接并就绪；尚未切换关节保持模式','state':api('/robot/status')}
                self.checkpoint();state=self.robot_fresh()
                self.require_arm_feedback()
                if (state.get('arm_state') or [])[:2]!=[2,2]:
                    self.checkpoint();api('/robot/mode',{'mode':1})
                    self.wait_robot(lambda s:(s.get('arm_state') or [])[:2]==[1,1],5)
                    self.checkpoint();api('/robot/mode',{'mode':3})
                    self.wait_robot(lambda s:(s.get('arm_state') or [])[:2]==[2,2],5)
                return {'message':'阻抗模式已就绪；未执行 Home，未启动遥操','state':api('/robot/status')}
            if command=='teleop':
                state=self.robot_fresh()
                if not state.get('control_ready') or (state.get('arm_state') or [])[:2]!=[2,2]:raise RuntimeError('请先完成“一键就绪（阻抗）”')
                self.require_arm_feedback()
                self.checkpoint();api('/modules/tool/start',{})
                self.checkpoint();api('/modules/teleop/start',{})
                self.service_time=0
                return {'message':'PICO 接收与夹爪输入已启动；头显连接 6.6.7.100，手柄先回中。Home 需单独确认','state':api('/robot/status')}
            if command=='clear':
                self.robot_fresh(allow_fault=True)
                answer=self.call(Trigger,'/control/clear_fault',Trigger.Request(),5)
                if answer is None:raise RuntimeError('Robot 清错接口不可用')
                time.sleep(.4)
                return {'message':'已发送仅清错请求，未调用 Home；请以实际状态判断是否清除','trigger_success':answer.success,'trigger_message':answer.message,'state':api('/robot/status')}
            if command in ['home','mode']:
                state=self.robot_fresh()
                if command=='home':
                    if args.get('home_confirmed') is not True:raise RuntimeError('Home 必须单独确认归位路径')
                    if self.services().get('apex-teleop.service',{}).get('ActiveState')!='active':raise RuntimeError('请先启动遥操规划模块，再单独确认 Home')
                    self.require_arm_feedback()
                    self.checkpoint();return {'message':'已提交 Home 请求；请观察现场和控制器状态','result':api('/robot/go_home',{})}
                mode=args.get('mode')
                if mode not in [0,1,3]:raise RuntimeError('不支持的控制模式')
                if mode in [1,3]:self.require_arm_feedback()
                self.checkpoint();return {'message':'模式切换请求已完成','result':api('/robot/mode',{'mode':mode}),'state':api('/robot/status')}
            if command=='robot_stop':
                if any(self.services().get(x,{}).get('ActiveState')=='active' for x in ['apex-teleop.service','apex-tool.service']):raise RuntimeError('请先暂停遥操，再断开 Robot')
                self.robot_fresh(allow_fault=True);self.checkpoint()
                return {'message':'Robot 服务已请求断开，请保留双腕支撑','result':api('/modules/robot/stop',{})}
            raise RuntimeError('未知操作')

    def dispatch(self,command,args):
        if command=='hello':return {'version':VERSION,'agent_sha256':self.code_sha,'read_only_on_connect':True}
        if command=='status':return self.status()
        if command=='parameters':return self.parameters()
        if command=='preflight':return self.preflight()
        allowed={'display','ready','prepare','teleop','pause','clear','home','mode','robot_stop'}
        if command not in allowed:raise RuntimeError('未允许的命令')
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=self.code_sha:raise RuntimeError('代理文件已更新，请关闭并重新打开控制台后再操作')
        start=time.time()
        try:
            result=self.action(command,args);self.audit(command,args,start,True,result);return result
        except Exception as exc:
            self.audit(command,args,start,False,{'error':str(exc)});raise

    def audit(self,command,args,start,ok,result):
        with (ROOT/'actions.jsonl').open('a') as f:f.write(json.dumps({'started_at':start,'finished_at':time.time(),'command':command,'args':args,'ok':ok,'result':result},ensure_ascii=False)+'\n')

    def video(self):
        while rclpy.ok():
            with self.lock:raw=self.frame;age=time.monotonic()-self.frame_time
            if raw and age<3:
                try:
                    img=Image.open(io.BytesIO(raw));w,h=img.size
                    img=img.crop((0,0,w//2,h//2)).resize((800,450))
                    out=io.BytesIO();img.save(out,format='PNG',compress_level=1)
                    print(json.dumps({'frame':base64.b64encode(out.getvalue()).decode(),'age':round(age,3)}),flush=True)
                except Exception as exc:print(json.dumps({'error':str(exc)}),flush=True)
            else:print(json.dumps({'waiting':True,'message':'等待摄像头新鲜视频帧'}),flush=True)
            time.sleep(.5)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--video',action='store_true');args=parser.parse_args()
    agent=Agent(video=args.video)
    try:
        if args.video:agent.video()
        else:
            for line in sys.stdin:
                request={}
                try:
                    request=json.loads(line);result=agent.dispatch(request.get('cmd'),request.get('args') or {})
                    response={'id':request.get('id'),'ok':True,'data':result}
                except Exception as exc:response={'id':request.get('id'),'ok':False,'error':str(exc)}
                print(json.dumps(response,ensure_ascii=False),flush=True)
    finally:agent.executor.shutdown();agent.node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
