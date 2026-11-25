import collections,json,pathlib,time
import rclpy
from rclpy.qos import QoSProfile,ReliabilityPolicy
from std_msgs.msg import Bool,Float32,Int32MultiArray
rclpy.init();node=rclpy.create_node('readonly_gripper_release_observer')
qos=QoSProfile(depth=10,reliability=ReliabilityPolicy.BEST_EFFORT)
base=pathlib.Path(__file__).parent
counts=collections.Counter();ranges={};last={}
f=(base/'passive-input-feedback.jsonl').open('w',buffering=1)
def cb(topic,msg):
 value=list(msg.data) if isinstance(msg,Int32MultiArray) else msg.data
 counts[topic]+=1;last[topic]=value
 if isinstance(msg,Float32):
  r=ranges.setdefault(topic,[value,value]);r[0]=min(r[0],value);r[1]=max(r[1],value)
 f.write(json.dumps({'mono':time.monotonic(),'time':time.time(),'topic':topic,'value':value})+'\n')
for side in ('L','R'):
 for topic,typ in [('/control/enable'+side,Bool),('/control/gripperValue'+side,Float32),('/info/wrist485_'+side,Int32MultiArray)]:
  node.create_subscription(typ,topic,lambda msg,t=topic:cb(t,msg),qos)
node.create_subscription(Bool,'/info/vr_connected',lambda msg:cb('/info/vr_connected',msg),qos)
end=time.monotonic()+60
while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.1)
f.close()
summary={'read_only':True,'duration_seconds':60,'counts':dict(counts),'trigger_ranges':ranges,'last':last}
(base/'passive-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
node.destroy_node();rclpy.shutdown()
