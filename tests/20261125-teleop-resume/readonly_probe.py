import json,time
import rclpy
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.utilities import get_message
from rosidl_runtime_py.convert import message_to_ordereddict
rclpy.init()
n=rclpy.create_node('teleop_resume_readonly_probe')
values={}; subs={}; counts={}; frames=[]
wanted={'/control/enableL','/control/enableR','/control/gripperValueL','/control/gripperValueR','/control/vr_joy_L','/control/vr_joy_R','/info/wrist485_L','/info/wrist485_R','/info/vr_connected','/quad_tile/compressed'}
end=time.monotonic()+8
while time.monotonic()<end:
    for t,types in n.get_topic_names_and_types():
        if t in wanted and t not in subs:
            def record(m,t=t):
                counts[t]=counts.get(t,0)+1
                if t=='/quad_tile/compressed':
                    frames.append((time.monotonic(),len(m.data)))
                else:
                    d=message_to_ordereddict(m); d.pop('header',None); values[t]=d
            subs[t]=n.create_subscription(get_message(types[0]),t,record,qos_profile_sensor_data)
    rclpy.spin_once(n,timeout_sec=0.05)
print(json.dumps({'values':values,'counts':counts,'camera_fps':(len(frames)-1)/(frames[-1][0]-frames[0][0]) if len(frames)>1 else 0,'last_image_bytes':frames[-1][1] if frames else 0}))
n.destroy_node(); rclpy.shutdown()
