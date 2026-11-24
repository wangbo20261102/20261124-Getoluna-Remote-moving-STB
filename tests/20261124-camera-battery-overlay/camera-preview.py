"""Camera preview with read-only battery annotation for MAXHUB screen sharing."""
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from battery_overlay import RUNTIME, refresh, video_filter
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

stop = threading.Event()
refresh()

def update_batteries():
    while not stop.wait(.5):
        refresh()

threading.Thread(target=update_batteries, daemon=True).start()
rclpy.init()
node = rclpy.create_node('luna_camera_battery_preview')
player = subprocess.Popen(
    ['/usr/bin/ffplay', '-hide_banner', '-loglevel', 'info', '-nostats',
     '-f', 'mjpeg', '-probesize', '32', '-analyzeduration', '0', '-fflags',
     'nobuffer', '-framedrop', '-an', '-autoexit', '-noborder', '-x', '1920', '-y', '1080',
     '-left', '0', '-top', '0', '-vf', video_filter(), '-window_title',
     'Luna Camera - Battery Status', '-i', 'pipe:0'], stdin=subprocess.PIPE, bufsize=0)
frames = 0
next_report = 1

def shutdown(signum, frame):
    stop.set()

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

def show(message):
    global frames, next_report
    if player.poll() is not None:
        stop.set()
        return
    try:
        player.stdin.write(bytes(message.data))
    except (BrokenPipeError, OSError):
        stop.set()
        return
    frames += 1
    if frames == 1:
        (RUNTIME / 'first-camera-frame.jpg').write_bytes(bytes(message.data))
    if frames == next_report:
        print(f'Preview frames received: {frames}', flush=True)
        next_report = 60 if frames == 1 else frames + 300
    if frames % 30 == 0:
        (RUNTIME / 'frame-heartbeat').touch()

subscription = node.create_subscription(CompressedImage, '/quad_tile/compressed', show, qos_profile_sensor_data)
try:
    while rclpy.ok() and not stop.is_set() and player.poll() is None:
        rclpy.spin_once(node, timeout_sec=.25)
finally:
    stop.set()
    player.stdin.close()
    try:
        player.wait(timeout=2)
    except subprocess.TimeoutExpired:
        player.terminate()
    node.destroy_node()
    rclpy.try_shutdown()
