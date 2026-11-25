#!/bin/bash
set -e
source /etc/apex/apex_ros_env.sh
export PYTHONPATH=/home/nvidia/luna-test-runs/20261125-apex-impedance-entry-fix/overlay:$PYTHONPATH
export APEX_BACKEND_HOST=127.0.0.1
export APEX_BACKEND_PORT=18080
exec python3 -m apex_backend.backend
