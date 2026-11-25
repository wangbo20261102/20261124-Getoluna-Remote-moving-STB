#!/usr/bin/env bash
# User-invoked display and camera startup only. No Robot/Teleop/Tool startup.
set -euo pipefail
runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
test -d "$runtime" || { echo 'No user runtime directory/X11 desktop available.' >&2; exit 1; }
mapfile -t clients < <(find "$HOME/.local/share" -maxdepth 1 -type d -name 'maxhub-5.10.46.0.*')
test "${#clients[@]}" -eq 1 || { echo 'Expected one installed MAXHUB 5.10.46.0 directory.' >&2; exit 1; }
client_dir="${clients[0]}"
client="$client_dir/opt/apps/com.cvte.exceedshare/files/bin/DongleClient"
test -x "$client" && test -r "$client_dir/camera-preview.py"
lsusb -d 1ff7:0f52
if pgrep -f '^(\./|/[^ ]*/)[D]ongleClient$' >/dev/null && pgrep -f '^/usr/bin/python3 /[^ ]*/[c]amera-preview[.]py$' >/dev/null; then
    echo 'Display client and preview are already running; no duplicate was started.'
    exit 0
fi
sudo -n /usr/local/sbin/luna-maxhub-prepare
export DISPLAY=:0 XAUTHORITY=/run/luna-maxhub/Xauthority
xrandr --query | grep -q '^DP-1 connected' || { echo 'DP-1 is not connected.' >&2; exit 1; }
xrandr --output DP-1 --mode 1920x1080 --rate 60
if systemctl is-active --quiet luna-d435-preview.service; then
    echo 'The independent D435 preview owns the camera; stop it through the normal UI first.' >&2
    exit 1
fi
command -v v4l2-ctl >/dev/null
v4l2-ctl --device=/dev/video12 --info | grep -i 'realsense' >/dev/null || {
    echo 'D435 video12 identity check failed. Inspect V4L2 nodes before starting Camera.' >&2; exit 1;
}
v4l2-ctl --device=/dev/video12 --list-formats-ext | grep -F "'YUYV'" >/dev/null || {
    echo 'D435 video12 is not a YUYV colour capture node; inspect enumeration first.' >&2; exit 1;
}
sudo -n /usr/bin/systemctl start apex-camera.service
logs="$HOME/luna-ready-20261123/logs"
mkdir -p "$logs"
stamp=$(date +%Y%m%d-%H%M%S)
cd "$(dirname "$client")"
if ! pgrep -f '^(\./|/[^ ]*/)[D]ongleClient$' >/dev/null; then
    nohup env LD_LIBRARY_PATH="$PWD/../lib" QT_PLUGIN_PATH="$PWD/../plugins" QT_QPA_PLATFORM=xcb \
        ./DongleClient >"$logs/wt12-$stamp.log" 2>&1 </dev/null &
fi
if ! pgrep -f '^/usr/bin/python3 /[^ ]*/[c]amera-preview[.]py$' >/dev/null; then
    nohup bash -c 'source /etc/apex/apex_ros_env.sh; exec /usr/bin/python3 "$1"' bash \
        "$client_dir/camera-preview.py" >"$logs/camera-preview-$stamp.log" 2>&1 </dev/null &
fi
disown -a
echo "Display started; logs: $logs. Press the WT12 centre button when ready."
