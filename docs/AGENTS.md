# 机器人联机操作约定

本节适用于本项目中的 Gento Luna / Apex / PICO 机器人工作。

- 2026-11-24 用户指定将本次右臂/腕部故障归档为“电量不足引起的报警”。恢复情况：用户已通过 Apex 进入阻抗并复位，随后新鲜控制器反馈双臂状态为 2、control_ready=true、control_error=false。引用故障归类时注明其为用户确认的归档结论；保留原始诊断事实，不将尚未隔离验证的供电因果写成厂家已确认的结论。
- 后续连接检查、测试准备和故障排查时，优先读取两块电池各自的电量与充电状态。任一电池 SOC < 30% 时，先明确提示“电量低于 30%，请优先充电；本项目有低电量相关报警历史”，再给出其他检查结果。使用两块电池中的较低值，不以平均值代替。数据不新鲜或不可读时明确说明无法判断。30% 本身不属于“低于 30%”。
- 这是一项助手后续操作提醒规则，不代表已配置后台自动通知或修改厂家保护策略。未经另行要求，不修改厂家补能/报警阈值，不因该提醒自动断使能。
- 历史测试的冻结基准位于 `E:\Github\Mubea-EV-Gentoluna-baselines\20261124-before-0p2`，保持只读。新诊断和改动放在独立版本；当前事件材料位于 `E:\Github\Mubea-EV-Gentoluna-tests\20261124-0p2-0p2\right-gripper-incident`。

人读记录见同目录 `20261124_右臂报警归档与电量提醒.md`。

## 2026-11-24 已部署的摄像头电量提示

- 现有机器人本地摄像头预览与 MAXHUB 投屏已加入两块电池实时百分比和充电状态。任一电池严格低于 30% 时对应文字及充电提醒显示红色；数据过期显示未知。用户已确认大屏画面正常。
- 独立版本：`E:\Github\Mubea-EV-Gentoluna-tests\20261124-camera-battery-overlay`；机器人：`/home/nvidia/luna-test-runs/20261124-camera-battery-overlay`；用户服务：`luna-camera-battery-overlay.service`（已启用）。
- 新服务替代旧预览守护，保持 DongleClient 运行。不要同时启动两个预览守护；回退说明在独立版本 README.md。上面的助手提醒规则仍适用；此新增功能是画面可视提示，未修改厂家阈值或控制机器人使能。

### 当前显示版本：密集轨迹乌龟 / 写实移动对打土拨鼠

- 用户进一步要求加快对打动作后，当前显示服务为 `luna-camera-fast-marmots.service`，独立版本为 `E:\Github\Mubea-EV-Gentoluna-tests\20261124-camera-fast-marmots`，机器人同名目录位于 `/home/nvidia/luna-test-runs/`。对打动作 action_fps=37.5，是前一版默认 12.5 的 3 倍；图像素材与所有平移、轨迹、重现参数不变。此前写实、卡通土拨鼠、动物点线、乌龟蜗牛和纯电量版本均保留，已停止并取消自动启动；不要同时启动两个预览守护。
- 电池 1 充电文字后显示绿色乌龟，保留原速度，单向爬行、尾后密集点线，右端消失后从左重现，不掉头。电池 2 使用参考照片外观生成的棕色厚毛土拨鼠，两只面对面对打，整组沿同样路线向右移动、留下同密度点线，到右侧消失再从左重现，不再原地停留。两组速度独立。仅对应电池充电且数据有效时出现。原电量/红色提示及语音规则保留。
- 自定义接口为独立版本 `animations.json`，控制种类、大小、位置、活动范围与周期，详见该版本 README.md。MAXHUB 客户端无需为动画重启。

## 2026-11-24 已部署的低电量语音

- 按用户最新要求，任一电池有效 SOC < 30% 且未充电时，经机器人现有扬声器播报“warning，请立即充电”，相邻播报开始间隔约 10 秒。触发后保持提醒，直到确认开始充电或整机断电；电量读数跳动、反馈暂失或语音服务重启不自行消除提醒。确认任一有效电池开始充电时，立即中断当前播报并暂停后续播报；停止充电后若仍低于 30%，重新触发。图像叠加显示保持不变。
- 当前独立版本：`E:\Github\Mubea-EV-Gentoluna-tests\20261124-battery-voice-charging-stop`；机器人同名目录位于 `/home/nvidia/luna-test-runs/`；用户服务仍为 `luna-battery-voice-warning.service`，已启用自动启动。前一版本与实际播放报告保留在 `20261124-battery-voice-warning`。服务只读电量，不控制机器人使能或修改厂家阈值。
- 首轮 3 次扬声器测试已完成，用户确认“已听到 3 次，正常”。此后追加 10 次测试也已完成，10 次播放返回码均为 0，开始间隔约 10 秒；两轮共 13 次。详细结果见独立目录 `playback-test-*.json` 与 `test-completion-summary.json`，不要将测试播报视为真实电量报警。

## 2026-11-25 开机显示恢复与摄像头固定身份

- 当天重启后，昨天显示/语音服务与配置仍在，但 DongleClient 没有启动入口，且桌面分辨率恢复为 1520×720。新增并启用用户服务 `luna-maxhub-client.service`，程序位于 `/home/nvidia/luna-test-runs/20261125-maxhub-startup-fix/maxhub_client_guard.py`，本地同名独立版本位于 `E:\Github\Mubea-EV-Gentoluna-tests`。它保留已有客户端，仅在客户端缺失时完成现有免密准备、恢复 1920×1080@60、启动客户端；退出后再次启动，不启动第二个摄像头预览，不控制 Robot/Teleop/Tool。
- 原 `~/luna-ready-20261123/start-maxhub.sh` 已备份并改为通过上述客户端服务和当前 `luna-camera-fast-marmots.service` 启动显示；不要恢复旧版直接启动额外 camera-preview.py 的逻辑。
- D435 的彩色接口重启后从 video12 变成 video14，旧 video12 是红外，造成黑帧与 CUDA 700。当前厂家 URI 解析器不支持直接使用 `/dev/v4l/by-path/...`，所以在系统 Camera 服务新增 drop-in `/etc/systemd/system/apex-camera.service.d/70-d435-device.conf`，每次启动前运行 `/home/nvidia/luna-test-runs/20261125-camera-device-fix/resolve_color_camera.py`，通过 USB 彩色接口 03、序列号 344223024944 和 YUYV 1920×1080 能力识别实际编号，只更新相机配置的两个 RGB 来源字段。不可再写死 `/dev/video12`。相机应保留在当前 USB 物理端口；该版本固定身份路径包含端口信息。
- 已明确启用系统 `apex-camera.service` 开机启动；用户 `luna-maxhub-client.service`、`luna-camera-fast-marmots.service`、`luna-battery-voice-warning.service` 均 enabled，用户 linger 已启用。未启用 Robot/Teleop/Tool 的自动运动。
- 用户已确认画面恢复；重跑设备识别确认配置不变，原动画配置、语音程序及手肘控制参数哈希保持不变。没有执行整机重启验证，不将“enabled 已核对”写成“已实测断电重启成功”。独立版本中保留前后配置、错误与恢复证据。
