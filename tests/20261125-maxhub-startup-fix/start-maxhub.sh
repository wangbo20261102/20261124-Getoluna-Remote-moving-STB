#!/usr/bin/env bash
# Display/camera only; delegate to the persistent single-instance services.
set -euo pipefail
sudo -n /usr/bin/systemctl start apex-camera.service
systemctl --user start luna-maxhub-client.service
systemctl --user start luna-camera-fast-marmots.service
echo 'MAXHUB client and annotated camera preview are managed by persistent services.'
echo 'No Robot, Teleop, Tool or Home command was issued.'
