# 最新冻结版本：Apex 阻抗入口修复已部署并实测

当前依据为 [2026-11-25 Apex 冻结记录](20261125-APEX-FROZEN.md) 和 manifests/20261125-apex-frozen。下方内容保留为历史阶段记录，不能将其中旧的待机、工具质量1.8kg或未验证状态当成最新状态。

# 最新追加：Robot 工具参数已完成运行时读回

在现场确认支撑后启动 Robot、仅 set_ready。左右工具数组与文件一致，控制器 ready=true/error=false，部件待机 0，未切换保持模式，请保留支撑。详见 `tests/20261125-tool-runtime-verification`。以下为先前各阶段的历史记录。

# 2026-11-25 当前状态补充

以 [联机同步报告](20261125-SYNC-REPORT.md) 与 `manifests/robot-active-file-consistency.json` 为当前依据。以下 11 月 24 日参数仍保留；原文中的临时底盘服务已由系统 `luna-pico-manual-chassis.service` 取代，随操作人员启动 Teleop 后启动，归档时未运行。当前摄像头、MAXHUB、显示/语音服务已确认运行；Robot/Teleop 当前未启动，未确认控制器实时工具补偿。

# 当日最终配置与接续说明

以下为最后成功联机操作时的确认结果。归档时连接超时，不能据此声称这些服务此刻仍在运行，也不能将历史电量作为当前值。

| 项目 | 最终值 / 位置 |
| --- | --- |
| 日期 | 2026-11-24，Asia/Shanghai |
| 机器人 / PC 以太网 | 6.6.7.100 / 6.6.7.200；底盘 6.6.7.6 |
| 手部缩放 | left_hand=1.5，right_hand=1.5 |
| 肘部缩放 | left_elbow=1.2，right_elbow=1.2 |
| 校正 | 左右独立 Home 肘锚点；最后两次缩放不改 calibration.json |
| 身体映射 | per_segment，robot_height=1.7 |
| 运动上限 | 平移 0.2 m/s，转向 0.2 rad/s |
| 摇杆 | 左：前后/横移；右：转向；无按住左摇杆条件 |
| J6 厂家实际限位 | 两侧 −60°～+60°，保持 |
| 最近控制模式 | 双臂阻抗；没有在归档中变更模式 |

## 文件与部署位置

- Teleop 参数：`/opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/config/luna/robot_param.yaml`；最终副本 `current-config/teleop-robot_param.yaml`。
- VR 接收器：`/opt/kernelmind/apex/install/marvin_teleop/lib/marvin_teleop/controller_udp.py`，同目录 `elbow_home_alignment.py`。源文件与测试在 `tests/20261124-elbow-home-alignment`。
- 校正状态：`/home/nvidia/luna-test-runs/20261124-elbow-home-alignment/calibration.json`；独立校正服务 `/control/pico_elbow_home/calibrate`，状态话题 `/info/pico_elbow_home_alignment`。
- 底盘手动桥：`/home/nvidia/luna-test-runs/20261124-full-body-cooperation/start_manual_chassis.sh`；用户服务 `luna-pico-manual-chassis-20261124.service`。
- 新 SDK：`/usr/local/lib/luna-apex-wrist/sdk/libGentoSDK.so`；原版备份及新产物的本地证据见 `tests/20261124-gripper-release-fix`。编译还依赖原机器人厂家库/对象，不能仅凭源码副本宣称干净环境可完整构建。
- 电量动画预览：用户服务 `luna-camera-fast-marmots.service`，目录 `/home/nvidia/luna-test-runs/20261124-camera-fast-marmots`，接口 `animations.json`。只运行一个预览守护。
- 语音：用户服务 `luna-battery-voice-warning.service`，目录 `/home/nvidia/luna-test-runs/20261124-battery-voice-charging-stop`。
- MAXHUB：沿用 DongleClient，最后核对时 PID 7497；归档不重启、不替换传屏客户端。

最后一次手部改动前读取的新鲜电量为 57% / 56%，随后读取参数已确认手部 1.5 / 1.5、肘部 1.2 / 1.2。该电量仅是历史操作读数，不是归档时读数。

## 次日人工测试

最后肘 1.2 / 手 1.5 参数更新未执行运动测试或 Home。Teleop 重载会重建 PICO 接收链、可能要求重新连接；应由现场按正常流程接续，不自动重放旧测试。

先读取两块电池各自的 SOC、充电状态和数据新鲜度，任一严格低于 30% 时优先充电。本项目有用户归档的低电量相关报警历史。

J5～J7 无抱闸，不能在未支撑腕部、仍夹持物体时为了加载历史文件随意停 Robot。`/robot/reset` 在当前后端可能调用 Home，不等同于只清故障；不要作为通用清错入口重放。保留原保护/限位，现场监督的人工操作与软件离线测试结果应分开记录。

当日未改动：工具质量/质心/惯量、关节限位、负载和力矩保护、厂家电池阈值、冻结基准。

