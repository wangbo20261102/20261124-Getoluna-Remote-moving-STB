#!/bin/bash
set -e
source /etc/apex/apex_ros_env.sh
exec /usr/bin/python3 /home/nvidia/luna-test-runs/20261124-0p2-full-5min/chassis_only_receiver.py \
 --ros-args -r __node:=pico_chassis_only_receiver \
 --params-file /opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/config/luna/robot_param.yaml \
 --params-file /opt/kernelmind/apex/install/marvin_ros_control/share/marvin_ros_control/config/robot_param_luna.yaml \
 -p enable_tcp:=true -p glove_mode:=false
