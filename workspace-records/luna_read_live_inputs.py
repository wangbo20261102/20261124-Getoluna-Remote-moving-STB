import json, time
import rclpy
from rosidl_runtime_py.utilities import get_message
from rosidl_runtime_py.convert import message_to_ordereddict
rclpy.init()
node=rclpy.create_node('luna_readonly_test_preflight')
values={}
subs={}
wanted={'/control/enableL','/control/enableR','/control/gripperValueL','/control/gripperValueR','/control/vr_joy_L','/control/vr_joy_R','/info/wrist485_L','/info/wrist485_R','/info/vr_connected'}
end=time.monotonic()+4
while time.monotonic()<end:
    for topic,types in node.get_topic_names_and_types():
        if topic in wanted and topic not in subs:
            def record(msg, topic=topic):
                data=message_to_ordereddict(msg)
                data.pop('header',None)
                values[topic]=data
            subs[topic]=node.create_subscription(get_message(types[0]),topic,record,rclpy.qos.qos_profile_sensor_data)
    rclpy.spin_once(node,timeout_sec=0.1)
print(json.dumps(values,ensure_ascii=False))
node.destroy_node()
rclpy.shutdown()
