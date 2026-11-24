#!/bin/bash
set -e
source /etc/apex/apex_ros_env.sh
cd /home/nvidia/luna-test-runs/20261124-full-body-cooperation
exec /usr/bin/python3 -u pico_chassis_bridge.py --live --left-forward 2 --left-lateral -1 --right-turn -1 --record manual-chassis-telemetry.jsonl
