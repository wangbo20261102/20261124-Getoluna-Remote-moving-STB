"""Read-only input and joint check before the operator-supported restart."""
import json,math,pathlib,time
import rclpy
from rclpy.qos import QoSProfile,ReliabilityPolicy
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool,Float32
from marvin_msgs.msg import Jointfeedback

rclpy.init();node=rclpy.create_node('wrist_fix_deployment_precheck')
qos=QoSProfile(depth=1,reliability=ReliabilityPolicy.BEST_EFFORT)
values={}
def receive(key,msg):values[key]=(time.monotonic(),msg)
topics=[('connected','/info/vr_connected',Bool),('joints','/info/joint_feedback',Jointfeedback)]
for side in ('L','R'):
    topics += [('enable'+side,'/control/enable'+side,Bool),
               ('trigger'+side,'/control/gripperValue'+side,Float32),
               ('joy'+side,'/control/vr_joy_'+side,Joy)]
for key,topic,kind in topics:
    node.create_subscription(kind,topic,lambda msg,k=key:receive(k,msg),qos)
end=time.monotonic()+3
while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.05)
now=time.monotonic()
fresh=lambda key,age:key in values and now-values[key][0]<age
connected=fresh('connected',1.5) and values['connected'][1].data
input_ok=fresh('connected',1.5)
if connected:
    for side in ('L','R'):
        input_ok &= all(fresh(k,.3) for k in ('enable'+side,'trigger'+side,'joy'+side))
        if input_ok:
            input_ok &= not values['enable'+side][1].data
            input_ok &= values['trigger'+side][1].data<=.2
            input_ok &= all(abs(v)<=.15 for v in values['joy'+side][1].axes[:2])
joint_ok=fresh('joints',.3)
positions=[];speeds=[]
if joint_ok:
    positions=list(values['joints'][1].arm_positions)
    speeds=list(values['joints'][1].arm_velocities)
    joint_ok = len(positions)==14 and len(speeds)==14 and all(math.isfinite(x) for x in positions+speeds)
    joint_ok &= max(abs(x) for x in speeds)<.01
    joint_ok &= all(abs(math.degrees(positions[i]))<59.5 for i in (5,12))
result={'passed':bool(input_ok and joint_ok),'inputs_neutral':bool(input_ok),'joints_stationary_and_j6_inside_limits':bool(joint_ok),'pico_connected':bool(connected),'arm_positions_rad':positions,'arm_velocities_rad_s':speeds}
path=pathlib.Path(__file__).with_name('deployment-precheck.json')
path.write_text(json.dumps(result,indent=2));print(json.dumps(result))
node.destroy_node();rclpy.shutdown()
raise SystemExit(0 if result['passed'] else 1)
