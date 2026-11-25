import json,time,pathlib,numpy as np,rclpy
from rclpy.qos import QoSProfile,ReliabilityPolicy
from marvin_msgs.msg import VrBody
from elbow_home_alignment import HOME,rotation
rclpy.init();node=rclpy.create_node('readonly_home_elbow_validation');rows=[]
def cb(m):
 if not all(m.available[:3]):return
 q=m.torso_pose.orientation;R=rotation({'w':q.w,'x':q.x,'y':q.y,'z':q.z})
 v=lambda p:np.array([p.x,p.y,p.z]);origin=v(m.torso_pose.position)
 rows.append([R.T@(v(m.left_elbow_pose.position)-origin),R.T@(v(m.right_elbow_pose.position)-origin)])
node.create_subscription(VrBody,'/control/vr_body',cb,QoSProfile(depth=1,reliability=ReliabilityPolicy.BEST_EFFORT))
end=time.monotonic()+60
while len(rows)<60 and time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.1)
result={'frames':len(rows),'home_m':{k:v.tolist() for k,v in HOME.items()},'robot_commands_sent':False}
if rows:
 a=np.array(rows);result.update({'mean_m':a.mean(0).tolist(),'std_m':a.std(0).tolist(),'difference_from_home_m':(a.mean(0)-np.array(list(HOME.values()))).tolist()})
p=pathlib.Path(__file__).with_name('live-verification.json');p.write_text(json.dumps(result,indent=2));print(json.dumps(result))
node.destroy_node();rclpy.shutdown()
