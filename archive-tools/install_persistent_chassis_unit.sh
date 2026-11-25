#!/bin/bash
# Install only. Never start Robot, Teleop, or the live bridge during archiving.
set -euo pipefail
run=/home/nvidia/luna-archive-exports/20261125-connected-sync
test "$EUID" -eq 0
systemd-analyze verify "$run/luna-pico-manual-chassis.service"
install -o root -g root -m 0644 "$run/luna-pico-manual-chassis.service" /etc/systemd/system/luna-pico-manual-chassis.service
systemctl daemon-reload
systemctl enable luna-pico-manual-chassis.service
systemctl show luna-pico-manual-chassis.service -p ActiveState -p UnitFileState -p PartOf -p Requisite
echo PERSISTENT_BRIDGE_DEFINITION_INSTALLED_NOT_STARTED
