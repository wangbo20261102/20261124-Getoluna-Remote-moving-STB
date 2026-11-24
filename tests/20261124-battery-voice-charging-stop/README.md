# 开始充电即停止语音

2026-11-24 按用户最新规则部署，服务名仍为 `luna-battery-voice-warning.service`，只将 ExecStart 切换到本独立版本。前一版本和 3 次、10 次播放报告保留。

- 任一有效电池 SOC < 30% 且未确认充电时，触发“warning，请立即充电”，每 10 秒播报一次。
- 触发后保持提醒，不因 SOC 回跳、暂时丢失反馈或语音服务重启自行解除。
- 检测到任一已连接、在位、无电池错误且反馈新鲜的电池开始充电时，解除提醒，并中断正在播放的语音；充电中即使仍低于 30% 也不播报。
- 停止充电后若仍低于 30%，重新触发。整机断电自然停止；同一次开机的提醒状态保存在 `/run/user/1000/luna-battery-voice-warning/latch.json`，不跨整机重启继承。
- 不新增软件静音按钮，不控制机械臂或修改厂家电量阈值。摄像头、MAXHUB 和原有电量显示源文件不变。

验证：11 项测试全部通过，包括模拟正在播放时收到充电反馈并取消播放、阈值边界、10 秒间隔、数据过期不伪造充电、服务重启保留与整机重启清除提醒。本轮测试使用隔离状态和假播放器，未注入实机数据或新增实机测试播报。

部署后实机状态：`charging_detected=true`、`alarm_latched=false`、`playing=false`、`last_error=null`，语音服务 active；显示服务 active，DongleClient PID 7497 未改变。

回退配置保存在机器人本目录 `service-before-charging-stop.conf`。本版本语音素材与上一版本相同。
