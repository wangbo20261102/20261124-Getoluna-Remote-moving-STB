"""Read-only file and camera runtime checks; never connects an independent robot SDK."""
from pathlib import Path
import hashlib,io,json,time
import rclpy
from rcl_interfaces.srv import GetParameters
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from PIL import Image,ImageStat

ROOT=Path('/home/nvidia/luna-archive-exports/20261125-connected-sync')
expected=json.loads((ROOT/'expected-active-files.json').read_text())
checks=[]
for e in expected['files']:
 p=Path(e['robot_path']);h=hashlib.sha256(p.read_bytes()).hexdigest()
 checks.append({'robot_path':str(p),'repo_path':e['repo_path'],'sha256':h,'matches_snapshot_and_local':h==e['sha256']})
rclpy.init();node=rclpy.create_node('archive_readonly_consistency_check')
runtime={}
for service,names in [('/quad_csi_quickview/get_parameters',['input_width','input_height','fps','head_cam_source']),('/VR_reader/get_parameters',['human_scale_table.left_hand','human_scale_table.right_hand','human_scale_table.left_elbow','human_scale_table.right_elbow']),('/marvin_robot_node/get_parameters',['left_tool','right_tool'])]:
 client=node.create_client(GetParameters,service)
 if not client.wait_for_service(timeout_sec=2):runtime[service]={'available':False,'note':'No live parameter service; no module started by verification.'};continue
 req=GetParameters.Request();req.names=names
 future=client.call_async(req);rclpy.spin_until_future_complete(node,future,timeout_sec=4)
 if not future.done():runtime[service]={'available':True,'response_timeout':True};continue
 values=[]
 for name,v in zip(names,future.result().values):
  value={1:v.bool_value,2:v.integer_value,3:v.double_value,4:v.string_value,7:list(v.integer_array_value),8:list(v.double_array_value),9:list(v.string_array_value)}.get(v.type,None)
  values.append({'name':name,'type':v.type,'value':value})
 runtime[service]={'available':True,'values':values}
frames=[]; first=[None]
def receive(msg):
 frames.append(time.monotonic())
 if first[0] is None:first[0]=bytes(msg.data)
sub=node.create_subscription(CompressedImage,'/quad_tile/compressed',receive,qos_profile_sensor_data)
deadline=time.monotonic()+4
while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.15)
image={}
if first[0]:
 (ROOT/'live-camera-frame.jpg').write_bytes(first[0])
 img=Image.open(io.BytesIO(first[0]));w,h=img.size
 scene=img.crop((0,0,w//2,max(1,h//2-48))).convert('RGB');stats=ImageStat.Stat(scene)
 image={'quad_size':[w,h],'scene_mean_rgb':stats.mean,'scene_stddev_rgb':stats.stddev,'nonblack_scene':max(stats.mean)>10 and max(stats.stddev)>5}
report={'checked_at_unix':time.time(),'files':checks,'all_file_hashes_match':all(c['matches_snapshot_and_local'] for c in checks),'runtime_parameters':runtime,'camera_frame_count':len(frames),'camera_observed_hz':(len(frames)-1)/(frames[-1]-frames[0]) if len(frames)>1 else 0,'camera_image':image,'motion_commands_sent':False,'robot_sdk_connection_opened':False,'services_started_or_restarted':False}
(ROOT/'live-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False),flush=True)
node.destroy_node();rclpy.shutdown()
