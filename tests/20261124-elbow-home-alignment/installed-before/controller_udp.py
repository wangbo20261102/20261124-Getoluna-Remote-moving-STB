#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, Pose, Point
from marvin_msgs.msg import VrBody
from move.msg import State
from sensor_msgs.msg import Joy
from std_msgs.msg import Float32, Bool, Int32
from visualization_msgs.msg import Marker, MarkerArray
import socket
import json 
import threading
import select
import time
from rclpy.qos import (
    QoSProfile,
    ReliabilityPolicy,
    HistoryPolicy,
    DurabilityPolicy,
    qos_profile_sensor_data,
)
import struct
from tf2_ros import Buffer, TransformListener, LookupException, ConnectivityException, ExtrapolationException
import tf2_geometry_msgs
import numpy as np

BODY_KEYPOINTS = [
    'left_elbow',
    'right_elbow',
    'torso',
    'head',
    'pelvis',
    'left_foot',
    'right_foot',
    'left_knee',
    'right_knee',
]

TRACKED_KEYPOINTS = [
    'pelvis',
    'torso',
    'left_hip',
    'right_hip',
    'left_shoulder',
    'right_shoulder',
    'head',
    'left_knee',
    'right_knee',
    'left_elbow',
    'right_elbow',
    'left_hand',
    'right_hand',
    'left_foot',
    'right_foot',
]

BODY_PARENT_CANDIDATES = {
    'pelvis': None,
    'torso': ['pelvis'],
    'head': ['torso', 'pelvis'],
    'left_hip': ['pelvis'],
    'right_hip': ['pelvis'],
    'left_knee': ['left_hip', 'pelvis'],
    'right_knee': ['right_hip', 'pelvis'],
    'left_foot': ['left_knee'],
    'right_foot': ['right_knee'],
    'left_shoulder': ['torso', 'pelvis'],
    'right_shoulder': ['torso', 'pelvis'],
    'left_elbow': ['left_shoulder', 'torso', 'pelvis'],
    'right_elbow': ['right_shoulder', 'torso', 'pelvis'],
}

HAND_SCALE_REF = {
    'left': ('left_elbow', 'left_shoulder', 'torso', 'pelvis'),
    'right': ('right_elbow', 'right_shoulder', 'torso', 'pelvis'),
}

HAND_KEYPOINT = {
    'left': 'left_hand',
    'right': 'right_hand',
}

ROOT_KEYPOINT = 'pelvis'

BODY_POSE_ATTRS = {
    'left_elbow': 'left_elbow_pose',
    'right_elbow': 'right_elbow_pose',
    'torso': 'torso_pose',
    'head': 'head_pose',
    'pelvis': 'pelvis_pose',
    'left_foot': 'left_foot_pose',
    'right_foot': 'right_foot_pose',
    'left_knee': 'left_knee_pose',
    'right_knee': 'right_knee_pose',
}

BODY_SKELETON_EDGES = [
    ('pelvis', 'torso'),
    ('torso', 'head'),
    ('pelvis', 'left_knee'),
    ('left_knee', 'left_foot'),
    ('pelvis', 'right_knee'),
    ('right_knee', 'right_foot'),
    ('torso', 'left_elbow'),
    ('torso', 'right_elbow'),
]

CMD_CONNECT = 0x19
CMD_HEARTBEAT = 0x23
CMD_SEND_VERSION = 0x6C
PC_RECV_HEAD = 0x3F
PC_RECV_END = 0xA5
PC_SEND_HEAD = 0xCF
PC_SEND_END = 0xA5
MAX_TCP_BODY_LEN = 1024 * 1024


def pack_tcp_packet(cmd: int, body_bytes: bytes) -> bytes:
    body_len = len(body_bytes)
    timestamp_ms = int(time.time() * 1000)
    header = struct.pack('<B B I', PC_SEND_HEAD, cmd, body_len)
    footer = struct.pack('<q B', timestamp_ms, PC_SEND_END)
    return header + body_bytes + footer


def unpack_tcp_stream(buffer: bytearray):
    while len(buffer) >= 7:
        if buffer[0] != PC_RECV_HEAD:
            buffer.pop(0)
            continue

        cmd = buffer[1]
        body_len = struct.unpack('<I', buffer[2:6])[0]
        if body_len > MAX_TCP_BODY_LEN:
            buffer.pop(0)
            continue

        packet_len_with_ts = 15 + body_len
        packet_len_without_ts = 7 + body_len
        packet_len = None

        if (
            len(buffer) >= packet_len_without_ts
            and buffer[packet_len_without_ts - 1] == PC_RECV_END
        ):
            if (
                len(buffer) >= packet_len_with_ts
                and buffer[packet_len_with_ts - 1] == PC_RECV_END
            ):
                packet_len = packet_len_with_ts
            else:
                packet_len = packet_len_without_ts
        elif (
            len(buffer) >= packet_len_with_ts
            and buffer[packet_len_with_ts - 1] == PC_RECV_END
        ):
            packet_len = packet_len_with_ts

        if packet_len is None:
            if len(buffer) < packet_len_with_ts:
                break
            buffer.pop(0)
            continue

        body = bytes(buffer[6:6 + body_len])
        del buffer[:packet_len]
        return cmd, body

    return None, None


class PoseGripMsg:
    def __init__(self, px=0.0, py=0.0, pz=0.0,
                 qx=0.0, qy=0.0, qz=0.0, qw=1.0,
                 vibration=0.0,
                 base_x=0.0, base_y=0.0, base_yaw=0.0):
        self.px = px
        self.py = py
        self.pz = pz
        self.qx = qx
        self.qy = qy
        self.qz = qz
        self.qw = qw
        self.vibration = vibration
        self.base_x = base_x
        self.base_y = base_y
        self.base_yaw = base_yaw

    def pack(self):
        data = {
            "px": self.px,
            "py": self.py,
            "pz": self.pz,
            "qx": self.qx,
            "qy": self.qy,
            "qz": self.qz,
            "qw": self.qw,
            "vibration": self.vibration,
            "base_x": self.base_x,
            "base_y": self.base_y,
            "base_yaw": self.base_yaw,
        }
        return json.dumps(data).encode('utf-8')
    
class UDPPoseReceiver(Node):

    def __init__(self):
        super().__init__('udp_pose_receiver')
        control_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        reliable_control_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # ROS Publisher
        self.publisher_A = self.create_publisher(PoseStamped, 'control/target_poseL', control_qos)
        
        self.publisher_B = self.create_publisher(PoseStamped, 'control/target_poseR', control_qos)
        
        self.trigger_value_A = self.create_publisher(Float32, 'control/gripperValueL', 10)
        self.trigger_value_B = self.create_publisher(Float32, 'control/gripperValueR', 10)
        self.joy_pub_A = self.create_publisher(Joy, 'control/vr_joy_L', control_qos)
        self.joy_pub_B = self.create_publisher(Joy, 'control/vr_joy_R', control_qos)
        self.tcp_sub_A = self.create_subscription(PoseStamped, 'info/eef_left', self.tcp_callback_A, 10)
        self.tcp_sub_B = self.create_subscription(PoseStamped, 'info/eef_right', self.tcp_callback_B, 10)
        # chassis pose in the base-local frame (zeroed by control/base_local_reset,
        # e.g. on base_teleop wholebody engage); orientation.w carries raw yaw radians
        self.base_x = 0.0
        self.base_y = 0.0
        self.base_yaw = 0.0
        self.base_local_state_sub = self.create_subscription(
            State, 'info/base_local_state', self._base_local_state_cbk, 10)
	
        self.body_pub = self.create_publisher(VrBody, 'control/vr_body', reliable_control_qos)
        self.body_marker_pub = self.create_publisher(MarkerArray, 'control/vr_body_markers', control_qos)
        self.vr_connected_pub_ = self.create_publisher(Bool, 'info/vr_connected', 10)
        self.teleop_mux_source = 0
        self.active_mux_source = self.teleop_mux_source
        mux_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.mux_source_sub = self.create_subscription(
            Int32, 'info/ik_request_mux/active_source', self._mux_source_cbk, mux_qos)
        self.gripL_state = False
        self.gripR_state = False
        self.left_controller_pose = Pose()
        self.right_controller_pose = Pose()
        self.left_controller_available = False
        self.right_controller_available = False
        # self.record_State_sub = self.create_subscription(Int32, 'recorder/status', self.recorder_cbk, 10)
        # self.cli = self.create_client(Trigger, 'toggle_recording')
        self.pos_scale = 1.0
        self.raw_positions_ref = {}
        self.scaled_positions_ref = {}
        self.last_buttonX = False
        self.max_x =1.8
        self.min_x =-0.15
        self.max_y =1.8
        self.min_y =-1.8
        self.max_z =2.2
        self.min_z =0.0
        robot_ip = self.declare_parameter('robot_ip', '192.168.1.100').value
        tcp_port = self.declare_parameter('tcp_port', 9010).value
        tcp_heartbeat_timeout = self.declare_parameter('tcp_heartbeat_timeout', 5.0).value
        self.enable_tcp = self.declare_parameter('enable_tcp', True).value
        # self.base_height = self.declare_parameter('base_height', 1.0).value
        self.glove_mode = self.declare_parameter('glove_mode', False).value
        print("glove_mode:",self.glove_mode)
        self.trigger_pose_A = self.create_publisher(Bool, 'control/enableL', control_qos)
        self.trigger_pose_B = self.create_publisher(Bool, 'control/enableR', control_qos)
        # In glove/dexhand mode the enable signal comes from control/footkey
        # (published by the apex backend websocket or the physical footpad_reader)
        # instead of the VR grips. State is cached and re-published periodically
        # so a lost packet or late-joining subscriber cannot latch a stale enable.
        self.footkey_state = False
        if self.glove_mode:
            self.footkey_sub = self.create_subscription(Bool, 'control/footkey', self.footkey_cbk, control_qos)
            self.footkey_timer = self.create_timer(0.1, self._publish_footkey_enable)

        self.robot_height = self.declare_parameter('robot_height', 1.5).value
        self.body_retarget_mode = self.declare_parameter('body_retarget_mode', 'per_segment').value
        self.human_scale_table = {
            keypoint: self._declare_human_scale(keypoint)
            for keypoint in TRACKED_KEYPOINTS
        }
        # UDP 设置
        self.udp_ip = '0.0.0.0'   # 本机监听所有地址
        self.udp_portA = 9000      # 和 Unity 保持一致
        self.udp_portB = 9001      # 和 Unity 保持一致
        self.udp_fb_A =  9002      # 和 Unity 保持一致
        self.udp_fb_B =  9003      # 和 Unity 保持一致
        self.udp_portC = 9004      # 和 Unity 保持一致
        
        self.subnet = '.'.join(robot_ip.split('.')[:3]) + '.'
        self.vr_ip = None
        # Discovery settings: the first headset broadcast becomes the paired VR IP.
        self.discovery_ip = '0.0.0.0'
        self.discovery_port = 8888
        self.discovered_vr_headsets = {}
        # Broadcaster settings: periodically announce this node so headsets can discover it
        self.broadcast_name = 'ApexHost'
        self.broadcast_model = 'Orin_agx'
        self.broadcast_app_version = '251223'

        self.socka = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socka.bind((self.udp_ip, self.udp_portA))
        self.socka.setblocking(False)
        self.sockb = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sockb.bind((self.udp_ip, self.udp_portB))
        self.sockb.setblocking(False)
        self.sockc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sockc.bind((self.udp_ip, self.udp_portC))
        self.sockc.setblocking(False)
        # Discovery socket: listens for headset broadcast/heartbeat and lists candidates.
        self.sock_discovery = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_discovery.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock_discovery.bind((self.discovery_ip, self.discovery_port))
        except Exception as e:
            self.get_logger().warn(f'Could not bind discovery socket {self.discovery_ip}:{self.discovery_port}: {e}')
        self.sock_discovery.setblocking(False)

        # Broadcaster socket: will send broadcast packets announcing this node
        self.sock_bcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_bcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        self.sock_fb_A = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_fb_A.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock_fb_B = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_fb_B.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # self.sockrecord = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # self.sockrecord.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)


        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.user_height = 1.65
        self.min_user_height = 0.5
        self.max_pos_scale = 1.5
        self.min_pos_scale = 0.8
        self._tcp_connected = threading.Event()
        if self.enable_tcp:
            self._tcp_thread = threading.Thread(
                target=self._tcp_session_manager,
                args=(tcp_port, tcp_heartbeat_timeout),
                daemon=True,
                name='tcp_session_manager',
            )
            self._tcp_thread.start()
            self.get_logger().info(f'TCP session manager listening on port {tcp_port}')
        else:
            self._tcp_thread = None
            self._tcp_connected.set()
            self.get_logger().info('TCP session manager disabled by parameter enable_tcp=false')
        # UDP receive loops run in socket threads instead of ROS timers.
        self._udp_running = True
        self.udp_threads = [
            threading.Thread(target=self.udp_loop, args=('A', self.listen_udp_A), daemon=True),
            threading.Thread(target=self.udp_loop, args=('B', self.listen_udp_B), daemon=True),
            threading.Thread(target=self.udp_loop, args=('C', self.listen_udp_C), daemon=True),
        ]
        for thread in self.udp_threads:
            thread.start()
        # Discovery timer: check for headset broadcasts once per 0.5s
        self.discovery_timer = self.create_timer(1.0, self.listen_discovery)
        # Broadcast timer: send presence once per second
        self.broadcast_timer = self.create_timer(1.0, self.send_broadcast)
        self.vr_connected_timer = self.create_timer(1.0, self._pub_vr_connected)

        # self.torso_height=self.user_height*0.66


        self.get_logger().info(f'Listening UDP on {self.udp_ip}:{self.udp_portA}, {self.udp_ip}:{self.udp_portB}')

    def udp_loop(self, name, listen_cb):
        while self._udp_running and rclpy.ok():
            if not self._tcp_connected.is_set():
                self._tcp_connected.wait(timeout=0.1)
                continue
            try:
                listen_cb()
            except OSError:
                if self._udp_running:
                    self.get_logger().debug(f'UDP {name} socket loop stopped by socket error')
                break
            except Exception as e:
                self.get_logger().warn(f'UDP {name} receive failed: {e}')

    def _tcp_session_manager(self, port: int, heartbeat_timeout: float):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(('0.0.0.0', port))
        server_sock.listen(1)

        while True:
            conn = None
            try:
                self.get_logger().info(f'[TCP] Waiting for headset on port {port}...')
                conn, addr = server_sock.accept()
                conn.settimeout(heartbeat_timeout)

                self._tcp_connected.set()
                self.get_logger().info(f'[TCP] Headset connected from {addr[0]}:{addr[1]}')

                if addr[0] != self.vr_ip:
                    self.get_logger().info(f'[TCP] Updated vr_ip: {self.vr_ip} -> {addr[0]}')
                    self.vr_ip = addr[0]

                buffer = bytearray()
                while True:
                    try:
                        data = conn.recv(4096)
                        if not data:
                            raise ConnectionResetError('remote closed connection')
                        buffer.extend(data)
                        while True:
                            cmd, body = unpack_tcp_stream(buffer)
                            if cmd is None:
                                break
                            self._handle_tcp_packet(conn, cmd, body)
                    except socket.timeout:
                        self.get_logger().warn(
                            f'[TCP] Heartbeat timeout ({heartbeat_timeout:.1f}s); '
                            f'headset {addr[0]} considered disconnected'
                        )
                        break
                    except (ConnectionResetError, OSError) as e:
                        self.get_logger().warn(f'[TCP] Connection lost: {e}')
                        break
            except Exception as e:
                self.get_logger().error(f'[TCP] Session manager error: {e}')
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                self._tcp_connected.clear()
                self.get_logger().warn('[TCP] Headset disconnected; UDP processing suspended')

    def _send_tcp_packet(self, conn, cmd: int, body: bytes = b''):
        conn.sendall(pack_tcp_packet(cmd, body))

    def _handle_tcp_packet(self, conn, cmd: int, body: bytes):
        if cmd == CMD_HEARTBEAT:
            self._handle_tcp_heartbeat(conn, body)
        elif cmd == CMD_CONNECT:
            self.get_logger().info(
                f'[TCP] Connect command received: {body.decode("utf-8", errors="ignore")}'
            )
        elif cmd == CMD_SEND_VERSION:
            self.get_logger().info(
                f'[TCP] Version command received: {body.decode("utf-8", errors="ignore")}'
            )
        else:
            self.get_logger().debug(f'[TCP] Unhandled command: 0x{cmd:02X}, body_len={len(body)}')

    def _handle_tcp_heartbeat(self, conn, body: bytes):
        if len(body) == 8:
            try:
                sent_time = struct.unpack('!d', body)[0]
                rtt_ms = (time.time() - sent_time) * 1000.0
                self.get_logger().debug(f'[TCP] Heartbeat RTT: {rtt_ms:.1f} ms')
            except Exception as e:
                self.get_logger().debug(f'[TCP] Heartbeat timestamp parse failed: {e}')
            return

        timestamp_bytes = struct.pack('!d', time.time())
        self._send_tcp_packet(conn, CMD_HEARTBEAT, timestamp_bytes)

    def _pub_vr_connected(self):
        self.vr_connected_pub_.publish(Bool(data=self._tcp_connected.is_set()))

    def _recv_latest_udp(self, sock, bufsize):
        readable, _, _ = select.select([sock], [], [], 0.1)
        if not readable:
            return None, None

        latest_data, latest_addr = sock.recvfrom(bufsize)
        while True:
            try:
                latest_data, latest_addr = sock.recvfrom(bufsize)
            except BlockingIOError:
                break
        return latest_data, latest_addr

    def _mux_source_cbk(self, msg):
        self.active_mux_source = msg.data

    def footkey_cbk(self, msg):
        self.footkey_state = bool(msg.data)
        self._publish_footkey_enable()

    def _publish_footkey_enable(self):
        # same mux gating as the VR-grip enable path
        if self.active_mux_source != self.teleop_mux_source:
            return
        self.trigger_pose_A.publish(Bool(data=self.footkey_state))
        self.trigger_pose_B.publish(Bool(data=self.footkey_state))

    def make_body_marker(self, marker_id, name, pose, available, color):
        marker = Marker()
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.header.frame_id = "tracking_base_link"
        marker.ns = "vr_body"
        marker.id = marker_id
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD if available else Marker.DELETE
        marker.pose = pose
        marker.scale.x = 0.08
        marker.scale.y = 0.08
        marker.scale.z = 0.08
        marker.color.a = 0.9
        marker.color.r = color[0]
        marker.color.g = color[1]
        marker.color.b = color[2]
        return marker

    def make_controller_marker(self, marker_id, name, pose, available, color):
        marker = Marker()
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.header.frame_id = "tracking_base_link"
        marker.ns = "vr_controller"
        marker.id = marker_id
        marker.type = Marker.ARROW
        marker.action = Marker.ADD if available else Marker.DELETE
        marker.pose = pose
        marker.scale.x = 0.16
        marker.scale.y = 0.03
        marker.scale.z = 0.03
        marker.color.a = 0.95
        marker.color.r = color[0]
        marker.color.g = color[1]
        marker.color.b = color[2]
        return marker

    def make_skeleton_marker(self, marker_id, pose_msgs, availability_map):
        marker = Marker()
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.header.frame_id = "tracking_base_link"
        marker.ns = "vr_body_skeleton"
        marker.id = marker_id
        marker.type = Marker.LINE_LIST
        marker.action = Marker.ADD
        marker.scale.x = 0.025
        marker.color.a = 0.95
        marker.color.r = 0.95
        marker.color.g = 0.95
        marker.color.b = 0.2

        for start_name, end_name in BODY_SKELETON_EDGES:
            if not (availability_map.get(start_name, False) and availability_map.get(end_name, False)):
                continue

            start_pose = pose_msgs[start_name]
            end_pose = pose_msgs[end_name]
            start_point = Point(
                x=float(start_pose.position.x),
                y=float(start_pose.position.y),
                z=float(start_pose.position.z),
            )
            end_point = Point(
                x=float(end_pose.position.x),
                y=float(end_pose.position.y),
                z=float(end_pose.position.z),
            )
            marker.points.extend([start_point, end_point])

        return marker

    def _dict_to_pos(self, pose_data):
        return np.array([pose_data['px'], pose_data['py'], pose_data['pz']], dtype=float)

    def _make_pose(self, pose_data, pos):
        pose = Pose()
        pose.position.x = float(pos[0])
        pose.position.y = float(pos[1])
        pose.position.z = float(pos[2])
        pose.orientation.x = pose_data['qx']
        pose.orientation.y = pose_data['qy']
        pose.orientation.z = pose_data['qz']
        pose.orientation.w = pose_data['qw']
        return pose

    def _declare_human_scale(self, keypoint):
        param_name = f'human_scale_table.{keypoint}'
        return float(self.declare_parameter(param_name, 1.0).value)

    def _find_parent(self, name, raw_positions, scaled_positions):
        parents = BODY_PARENT_CANDIDATES.get(name)
        if parents is None:
            return None
        for parent in parents:
            if parent in raw_positions and parent in scaled_positions:
                return parent
        return None

    def _retarget_global(self, raw_positions):
        if ROOT_KEYPOINT in raw_positions:
            root = raw_positions[ROOT_KEYPOINT]
            return {
                name: root + (pos - root) * self.pos_scale
                for name, pos in raw_positions.items()
            }
        return {name: pos * self.pos_scale for name, pos in raw_positions.items()}

    def _retarget_per_segment(self, raw_positions):
        scaled_positions = {}

        if ROOT_KEYPOINT in raw_positions:
            root_scale = self.human_scale_table.get(ROOT_KEYPOINT, 1.0)
            scaled_positions[ROOT_KEYPOINT] = raw_positions[ROOT_KEYPOINT] * root_scale

        for name in TRACKED_KEYPOINTS:
            if name == ROOT_KEYPOINT or name not in raw_positions:
                continue

            parent = self._find_parent(name, raw_positions, scaled_positions)
            if parent is not None:
                user_vec = raw_positions[name] - raw_positions[parent]
                scale = self.human_scale_table.get(name, 1.0)
                scaled_positions[name] = scaled_positions[parent] + user_vec * scale
            else:
                scale = self.human_scale_table.get(name, self.pos_scale)
                scaled_positions[name] = raw_positions[name] * scale

        return scaled_positions

    def _retarget_body_keypoints(self, raw_positions):
        if self.body_retarget_mode == 'per_segment':
            return self._retarget_per_segment(raw_positions)
        return self._retarget_global(raw_positions)

    def _scale_hand_position(self, hand_raw, side):
        scale = self.human_scale_table.get(HAND_KEYPOINT[side], 1.0)
        ref = self._hand_reference(side)
        if ref is None:
            return hand_raw * scale
        return self.scaled_positions_ref[ref] + (hand_raw - self.raw_positions_ref[ref]) * scale

    def _hand_reference(self, side):
        for name in HAND_SCALE_REF[side]:
            if name in self.raw_positions_ref and name in self.scaled_positions_ref:
                return name
        return None

    def _publish_joy(self, pose_data, publisher, stamp, frame_id):
        if not any(key in pose_data for key in ('joystickX', 'joystickY', 'joystickClick')):
            return

        joy_msg = Joy()
        joy_msg.header.stamp = stamp
        joy_msg.header.frame_id = frame_id
        joy_msg.axes = [
            float(pose_data.get('joystickX', 0.0)),
            float(pose_data.get('joystickY', 0.0)),
        ]
        joy_msg.buttons = [1 if bool(pose_data.get('joystickClick', False)) else 0]
        publisher.publish(joy_msg)



    def listen_udp_A(self):
        try:
            data, addr = self._recv_latest_udp(self.socka, 1024)
            if data is None:
                return
            message = data.decode('utf-8')
            pose_data = json.loads(message)
            x, y, z = pose_data['px'], pose_data['py'], pose_data['pz']
            if x < self.min_x:
                x = self.min_x
            if y > self.max_y:
                y = self.max_y
            if z < self.min_z:
                z = self.min_z
            if z > self.max_z:
                z = self.max_z
            pose_msg = PoseStamped()
            pose_msg.header.stamp = self.get_clock().now().to_msg()
            pose_msg.header.frame_id = "tracking_base_link"  # 根据实际情况修改
            self._publish_joy(pose_data, self.joy_pub_A, pose_msg.header.stamp, 'vr_controller_left')
            hand_raw = np.array([x, y, z])
            eef_pos = self._scale_hand_position(hand_raw, 'left')
            pose_msg.pose.position.x = eef_pos[0]
            pose_msg.pose.position.y = eef_pos[1]
            pose_msg.pose.position.z = eef_pos[2]
            pose_msg.pose.orientation.x = pose_data['qx']
            pose_msg.pose.orientation.y = pose_data['qy']
            pose_msg.pose.orientation.z = pose_data['qz']
            pose_msg.pose.orientation.w = pose_data['qw']
            grip_msg = pose_data['grip']
            self.gripL_state = grip_msg
            trigger_msg = pose_data['triggerValue']
            self.publisher_A.publish(pose_msg)
            x, y, z = pose_msg.pose.position.x, pose_msg.pose.position.y, pose_msg.pose.position.z
            if self.active_mux_source == self.teleop_mux_source:
                if not self.glove_mode:
                    self.trigger_pose_A.publish(Bool(data=grip_msg))
                self.trigger_value_A.publish(Float32(data=trigger_msg))

            # inside listen_udp_A after parsing pose_data
            buttonX = pose_data['buttonX']

            # Edge detection: only trigger when pressed down once
            if buttonX and not self.last_buttonX:
                # self.send_request()
                # self.get_logger().info("Request sent to toggle recording")
                pass

            # Update last state
            self.last_buttonX = buttonX



            # self.zerosw_A_pub_.publish(Bool(data=zero_sw))


            # self.get_logger().info(f'Received and published pose: {pose_msg}')
        except BlockingIOError:
            # 没有数据就跳过
            pass
    def listen_udp_B(self):
        try:
            data, addr = self._recv_latest_udp(self.sockb, 1024)
            if data is None:
                return
            message = data.decode('utf-8')
            pose_data = json.loads(message)
            x, y, z = pose_data['px'], pose_data['py'], pose_data['pz']
            if x < self.min_x:
                x = self.min_x
            if y > self.max_y:
                y = self.max_y
            if z < self.min_z:
                z = self.min_z
            if z > self.max_z:
                z = self.max_z
            pose_msg = PoseStamped()
            pose_msg.header.stamp = self.get_clock().now().to_msg()
            pose_msg.header.frame_id = "tracking_base_link"  # 根据实际情况修改
            self._publish_joy(pose_data, self.joy_pub_B, pose_msg.header.stamp, 'vr_controller_right')
            hand_raw = np.array([x, y, z])
            eef_pos = self._scale_hand_position(hand_raw, 'right')
            pose_msg.pose.position.x = eef_pos[0]
            pose_msg.pose.position.y = eef_pos[1]
            pose_msg.pose.position.z = eef_pos[2]
            pose_msg.pose.orientation.x = pose_data['qx']
            pose_msg.pose.orientation.y = pose_data['qy']
            pose_msg.pose.orientation.z = pose_data['qz']
            pose_msg.pose.orientation.w = pose_data['qw']
            grip_msg = pose_data['grip']
            self.gripR_state = grip_msg
            trigger_msg = pose_data['triggerValue']
            self.publisher_B.publish(pose_msg)
            if self.active_mux_source == self.teleop_mux_source:
                if not self.glove_mode:
                    self.trigger_pose_B.publish(Bool(data=grip_msg))
                self.trigger_value_B.publish(Float32(data=trigger_msg))
            # self.zerosw_B_pub_.publish(Bool(data=zero_sw))
            # self.get_logger().info(f'Received and published pose: {pose_msg}')
        except BlockingIOError:
            # 没有数据就跳过
            pass
    def listen_udp_C(self):
        try:
            data, addr = self._recv_latest_udp(self.sockc, 2048)
            if data is None:
                return
            message = data.decode('utf-8')
            pose_data = json.loads(message)
            # print(pose_data)
            # Availability flags for incoming body joints
            # [left_elbow, right_elbow, torso, head, pelvis, left_foot, right_foot, left_knee, right_knee]
            availability = [isinstance(pose_data.get(name), dict) for name in BODY_KEYPOINTS]

            incoming_user_height = pose_data.get('user_height', None)
            if isinstance(incoming_user_height, (int, float)) and incoming_user_height > self.min_user_height:
                self.user_height = float(incoming_user_height)
                scale = self.robot_height / self.user_height
                self.pos_scale = float(np.clip(scale, self.min_pos_scale, self.max_pos_scale))

            raw_positions = {
                name: self._dict_to_pos(pose_data[name])
                for name in TRACKED_KEYPOINTS
                if isinstance(pose_data.get(name), dict)
            }
            scaled_positions = self._retarget_body_keypoints(raw_positions)

            pose_msgs = {name: Pose() for name in BODY_KEYPOINTS}
            for name, available in zip(BODY_KEYPOINTS, availability):
                if not available:
                    continue
                pose_msgs[name] = self._make_pose(pose_data[name], scaled_positions[name])

            self.raw_positions_ref = raw_positions
            self.scaled_positions_ref = scaled_positions
            

            Body_msg = VrBody()
            Body_msg.header.stamp = self.get_clock().now().to_msg()
            Body_msg.header.frame_id = "tracking_base_link"
            for name, attr in BODY_POSE_ATTRS.items():
                setattr(Body_msg, attr, pose_msgs[name])
            Body_msg.available = availability
            self.body_pub.publish(Body_msg)

            availability_map = {
                name: available for name, available in zip(BODY_KEYPOINTS, availability)
            }

            marker_array = MarkerArray()
            marker_array.markers.append(self.make_body_marker(0, 'left_elbow', pose_msgs['left_elbow'], availability[0], (0.2, 0.8, 0.2)))
            marker_array.markers.append(self.make_body_marker(1, 'right_elbow', pose_msgs['right_elbow'], availability[1], (0.2, 0.2, 0.8)))
            marker_array.markers.append(self.make_body_marker(2, 'torso', pose_msgs['torso'], availability[2], (0.9, 0.6, 0.1)))
            marker_array.markers.append(self.make_body_marker(3, 'head', pose_msgs['head'], availability[3], (0.9, 0.9, 0.2)))
            marker_array.markers.append(self.make_body_marker(4, 'pelvis', pose_msgs['pelvis'], availability[4], (0.9, 0.2, 0.9)))
            marker_array.markers.append(self.make_body_marker(5, 'left_foot', pose_msgs['left_foot'], availability[5], (0.0, 0.7, 0.7)))
            marker_array.markers.append(self.make_body_marker(6, 'right_foot', pose_msgs['right_foot'], availability[6], (0.7, 0.4, 0.1)))
            marker_array.markers.append(self.make_body_marker(7, 'left_knee', pose_msgs['left_knee'], availability[7], (0.1, 0.9, 0.5)))
            marker_array.markers.append(self.make_body_marker(8, 'right_knee', pose_msgs['right_knee'], availability[8], (0.5, 0.5, 0.9)))
            marker_array.markers.append(self.make_controller_marker(100, 'left_controller', self.left_controller_pose, self.left_controller_available, (0.1, 0.7, 1.0)))
            marker_array.markers.append(self.make_controller_marker(101, 'right_controller', self.right_controller_pose, self.right_controller_available, (1.0, 0.4, 0.2)))
            marker_array.markers.append(self.make_skeleton_marker(200, pose_msgs, availability_map))
            self.body_marker_pub.publish(marker_array)
            # self.publisher_Torso.publish(torso_pose_msg)

            # self.torso_height = 0.66*self.user_height
            
        except (ValueError, TypeError) as e:
            self.get_logger().debug(f'Invalid UDP C payload: {e}')
        except BlockingIOError:
            # no data
            pass
    def listen_discovery(self):
        """Listen for headset discovery/broadcast packets and print headset candidates."""
        updated = False
        try:
            while True:
                data, addr = self.sock_discovery.recvfrom(4096)
                # Only treat the packet as a discovery if it's JSON and name == 'ApexHeadset'
                try:
                    text = data.decode('utf-8')
                except Exception:
                    text = data.decode('utf-8', errors='replace')
                # print(text)
                try:
                    obj = json.loads(text)
                except Exception:
                    # not JSON -> ignore
                    continue

                if obj.get('name') == 'ApexHeadset':
                    new_ip = addr[0]
                    self.discovered_vr_headsets[new_ip] = {
                        'port': addr[1],
                        'model': obj.get('model', ''),
                        'app_version': obj.get('app_version', ''),
                    }
                    if self.vr_ip is None:
                        self.vr_ip = new_ip
                        self.get_logger().info(
                            f"Set vr_ip to first discovered headset {self.vr_ip} "
                            f"(from {addr[0]}:{addr[1]})"
                        )
                    updated = True
        except BlockingIOError:
            # no data
            pass

        if updated:
            headsets = ', '.join(
                f"{ip}:{info['port']} model={info['model']} version={info['app_version']}"
                for ip, info in sorted(self.discovered_vr_headsets.items())
            )
            print("VR headsets:", headsets)

    def send_broadcast(self):
        """Broadcast a small JSON payload so headsets can discover this node.

        Payload looks like: {"name":"Apex_host","model":"Apex_node","app_version":"251223"}
        Sent to the discovery port using UDP broadcast.
        """
        payload = {
            'name': self.broadcast_name,
            'model': self.broadcast_model,
            'app_version': self.broadcast_app_version,
        }
        try:
            text = json.dumps(payload)
            bcast_addr = self.subnet + '255'
            self.sock_bcast.sendto(text.encode('utf-8'), (bcast_addr, self.discovery_port))
        except Exception as e:
            self.get_logger().debug(f'Broadcast failed: {e}')
    def _invert_hand_scale(self, eef_pos: np.ndarray, side) -> np.ndarray:
        scale = self.human_scale_table.get(HAND_KEYPOINT[side], 1.0)
        ref = self._hand_reference(side)
        if ref is None:
            if abs(scale) < 1e-6:
                return eef_pos
            return eef_pos / scale
        if abs(scale) < 1e-6:
            return eef_pos
        return self.raw_positions_ref[ref] + (eef_pos - self.scaled_positions_ref[ref]) / scale

    def _base_local_state_cbk(self, msg):
        self.base_x = msg.odometry.position.x
        self.base_y = msg.odometry.position.y
        self.base_yaw = msg.odometry.orientation.w

    def tcp_callback_A(self, msg):
        try:
            transform = self.tf_buffer.lookup_transform(
                'tracking_base_link',
                'base_link',
                self.get_clock().now()
            )
            pose_out = tf2_geometry_msgs.do_transform_pose(msg.pose, transform)
            eef_pos = np.array([pose_out.position.x, pose_out.position.y, pose_out.position.z])
            hand_raw = self._invert_hand_scale(eef_pos, 'left')
            self.left_controller_pose.position.x = pose_out.position.x
            self.left_controller_pose.position.y = pose_out.position.y
            self.left_controller_pose.position.z = pose_out.position.z
            self.left_controller_pose.orientation.x = pose_out.orientation.x
            self.left_controller_pose.orientation.y = pose_out.orientation.y
            self.left_controller_pose.orientation.z = pose_out.orientation.z
            self.left_controller_pose.orientation.w = pose_out.orientation.w
            self.left_controller_available = True
            Posemsg = PoseGripMsg(
                px=hand_raw[0], py=hand_raw[1], pz=hand_raw[2],
                qx=pose_out.orientation.x,
                qy=pose_out.orientation.y,
                qz=pose_out.orientation.z,
                qw=pose_out.orientation.w,
                base_x=self.base_x,
                base_y=self.base_y,
                base_yaw=self.base_yaw,
            )
            if self.vr_ip is not None and self._tcp_connected.is_set():
                self.sock_fb_A.sendto(Posemsg.pack(), (self.vr_ip, self.udp_fb_A))

        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            pass

    def tcp_callback_B(self, msg):
        try:
            transform = self.tf_buffer.lookup_transform(
                'tracking_base_link',
                'base_link',
                self.get_clock().now()
            )
            pose_out = tf2_geometry_msgs.do_transform_pose(msg.pose, transform)
            eef_pos = np.array([pose_out.position.x, pose_out.position.y, pose_out.position.z])
            hand_raw = self._invert_hand_scale(eef_pos, 'right')
            self.right_controller_pose.position.x = pose_out.position.x
            self.right_controller_pose.position.y = pose_out.position.y
            self.right_controller_pose.position.z = pose_out.position.z
            self.right_controller_pose.orientation.x = pose_out.orientation.x
            self.right_controller_pose.orientation.y = pose_out.orientation.y
            self.right_controller_pose.orientation.z = pose_out.orientation.z
            self.right_controller_pose.orientation.w = pose_out.orientation.w
            self.right_controller_available = True
            Posemsg = PoseGripMsg(
                px=hand_raw[0], py=hand_raw[1], pz=hand_raw[2],
                qx=pose_out.orientation.x,
                qy=pose_out.orientation.y,
                qz=pose_out.orientation.z,
                qw=pose_out.orientation.w,
                base_x=self.base_x,
                base_y=self.base_y,
                base_yaw=self.base_yaw,
            )
            if self.vr_ip is not None and self._tcp_connected.is_set():
                self.sock_fb_B.sendto(Posemsg.pack(), (self.vr_ip, self.udp_fb_B))

        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            pass

    # def recorder_cbk(self, msg):
    #     if msg.data == 1:
    #         # self.get_logger().info("Recorder started")
    #         self.sockrecord.sendto(b"1", (self.vr_ip, self.udP_record))
    #     elif msg.data == 0:
    #         # self.get_logger().info("Recorder stopped")
    #         self.sockrecord.sendto(b"0", (self.vr_ip, self.udP_record))
    #     else:
    #         self.get_logger().warn(f"Unknown recorder status: {msg.data}")

    # def send_request(self):
    #     # Non-blocking call
    #     future = self.cli.call_async(Trigger.Request())
    #     # Do NOT spin_until_future_complete
    #     # Optionally, you can add a callback later:
    #     future.add_done_callback(self.response_callback)

    def response_callback(self, future):
        try:
            response = future.result()
            self.get_logger().info(f'Result: {response.success}, {response.message}')
        except Exception as e:
            self.get_logger().error(f'Service call failed: {e}')

    def destroy_node(self):
        self._udp_running = False
        for sock in (self.socka, self.sockb, self.sockc):
            try:
                sock.close()
            except OSError:
                pass
        for thread in getattr(self, 'udp_threads', []):
            thread.join(timeout=0.2)
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = UDPPoseReceiver()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
