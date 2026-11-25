#!/bin/bash
set -euo pipefail
test "$EUID" -eq 0
systemctl enable apex-camera.service
echo CAMERA_BOOT_START_ENABLED
