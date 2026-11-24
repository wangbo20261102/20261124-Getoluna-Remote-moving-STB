"""Run the installed VR parser with a strict chassis-only publication allowlist."""
import runpy
from rclpy.node import Node

ALLOWED={'/control/vr_joy_L','/control/vr_joy_R','/info/vr_connected'}
original=Node.create_publisher

class MutedPublisher:
    def publish(self,*args,**kwargs):pass
    def get_subscription_count(self):return 0

def create_publisher(self,msg_type,topic,qos,*args,**kwargs):
    if '/'+topic.lstrip('/') not in ALLOWED:
        return MutedPublisher()
    return original(self,msg_type,topic,qos,*args,**kwargs)

Node.create_publisher=create_publisher
runpy.run_path('/opt/kernelmind/apex/install/marvin_teleop/lib/marvin_teleop/controller_udp.py',run_name='__main__')
