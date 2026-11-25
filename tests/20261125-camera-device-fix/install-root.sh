#!/bin/bash
set -euo pipefail
run=/home/nvidia/luna-test-runs/20261125-camera-device-fix
test "$EUID" -eq 0
test -f "$run/70-d435-device.conf"
if test -f /etc/systemd/system/apex-camera.service.d/70-d435-device.conf; then
    cp -p /etc/systemd/system/apex-camera.service.d/70-d435-device.conf "$run/70-d435-device.before.conf"
fi
install -o root -g root -m 0644 "$run/70-d435-device.conf" /etc/systemd/system/apex-camera.service.d/70-d435-device.conf
systemctl daemon-reload
systemctl restart apex-camera.service
echo CAMERA_RGB_SELECTION_INSTALLED
