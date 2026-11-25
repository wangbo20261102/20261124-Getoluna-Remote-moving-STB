#!/bin/bash
set -euo pipefail
if [[ $(id -u) != 0 ]]; then
    echo 'Run: sudo bash /home/nvidia/luna-test-runs/20261125-apex-impedance-entry-fix/install_backend.sh' >&2
    exit 1
fi
base=/home/nvidia/luna-test-runs/20261125-apex-impedance-entry-fix
dest=/opt/kernelmind/apex/install/apex_backend/lib/python3.10/site-packages/apex_backend/ros_state.py
expected_before=422bd391aca5709bd8352970cd2a7efff0761a09c000c7979f49d65055389e09
cd "$base"
sha256sum --check deploy.sha256
current=$(sha256sum "$dest" | cut -d' ' -f1)
candidate=$(sha256sum ros_state.py | cut -d' ' -f1)
if [[ $current != "$expected_before" && $current != "$candidate" ]]; then
    echo 'Installed backend changed since preparation; refusing to overwrite it.' >&2
    exit 1
fi
head -n 2 before/installed.sha256 | sha256sum --check
python3 -m py_compile ros_state.py
backup=$(mktemp -d /var/backups/luna-apex-mode-entry.XXXXXXXX)
cp -a "$dest" "$backup/ros_state.py"
rollback_on_error() {
    echo "Installation failed; restoring $backup/ros_state.py" >&2
    install -o root -g root -m 0664 "$backup/ros_state.py" "$dest"
    systemctl restart apex-backend.service || true
}
trap rollback_on_error ERR
install -o root -g root -m 0664 ros_state.py "$dest"
python3 -m py_compile "$dest"
systemctl restart apex-backend.service
ready=false
for attempt in $(seq 1 40); do
    if curl -fsS --max-time 1 http://127.0.0.1:8080/api/v1/robot/status > "$backup/backend-status.json"; then
        ready=true
        break
    fi
    sleep 0.25
done
[[ $ready == true ]]
head -n 2 before/installed.sha256 | sha256sum --check
trap - ERR
echo "Installed backend: $(sha256sum "$dest" | cut -d' ' -f1)"
echo "Backup: $backup/ros_state.py"
echo 'Only Apex backend code was installed. Robot/SDK/configuration were not replaced; no mode/Home/reset command was sent.'
