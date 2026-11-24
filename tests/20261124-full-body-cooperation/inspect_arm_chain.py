"""Read-only observation of PICO-to-arm topics; no commands or service calls."""
import datetime,json,pathlib,time
import rclpy
from rclpy.qos import QoSProfile,ReliabilityPolicy
from rosidl_runtime_py.convert import message_to_ordereddict
from std_msgs.msg import Bool,Int32
from geometry_msgs.msg import PoseStamped
from marvin_msgs.msg import IKRequest,JointcmdArm,Jointfeedback,VrBody

spec=[('/control/enableL',Bool),('/control/enableR',Bool),
 ('/control/target_poseL',PoseStamped),('/control/target_poseR',PoseStamped),
 ('/control/vr_body',VrBody),('/info/vr_connected',Bool),
 ('/control/teleop/ik_request',IKRequest),('/control/ik_request',IKRequest),
 ('/control/qp_controller/joint_cmd_A',JointcmdArm),('/control/qp_controller/joint_cmd_B',JointcmdArm),
 ('/control/joint_cmd_A',JointcmdArm),('/control/joint_cmd_B',JointcmdArm),
 ('/info/ik_request_mux/active_source',Int32),('/info/joint_cmd_mux/active_source',Int32),
 ('/control/input_mode',Int32),('/info/joint_feedback',Jointfeedback)]
rclpy.init();node=rclpy.create_node('read_only_arm_chain_probe')
qos=QoSProfile(depth=5,reliability=ReliabilityPolicy.BEST_EFFORT)
data={topic:{'count':0,'true_count':0} for topic,_ in spec}
def receive(topic,msg):
    row=data[topic];row['count']+=1
    if hasattr(msg,'data') and isinstance(msg.data,bool):row['true_count']+=int(msg.data)
    row['last']=message_to_ordereddict(msg)
for topic,kind in spec:
    node.create_subscription(kind,topic,lambda m,t=topic:receive(t,m),qos)
deadline=time.monotonic()+12
while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.1)
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
path=pathlib.Path(__file__).with_name('arm-chain-'+stamp+'.json')
path.write_text(json.dumps({'read_only':True,'topics':data},ensure_ascii=False,indent=2))
for topic,row in data.items():
    last=row.get('last',{})
    print(topic,json.dumps({'count':row['count'],'true_count':row['true_count'],
        'state':last.get('data'),'available':last.get('available')}))
print('saved='+str(path))
node.destroy_node();rclpy.shutdown()
