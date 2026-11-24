# 低于 30% 的语音提醒

语音：**warning，请立即充电**。离线合成，英文使用 Microsoft Zira，中文使用 Microsoft Huihui，合并为约 4.11 秒的 WAV。通过机器人现有扬声器输出，不改系统音量或当前摄像头 / MAXHUB 显示。

触发：任一电池数据有效且电量严格小于 30%。充电中的低电量也触发；两块电池同时低电量只播放一条公共提醒。按单调时间控制相邻播报开始间隔不少于 10 秒；真实循环轮询分辨率为 0.2 秒。

停止：没有有效低电量电池（两块均达到 30%、连接丢失或数据过期）时停止新增播报，并终止仍在播放的本条提醒。数据缺失不会凭旧百分比持续播报。

只读输入：`/run/luna-battery-screen/status.json`。本服务没有机器人运动、使能、复位或配置接口。

机器人目录：`/home/nvidia/luna-test-runs/20261124-battery-voice-warning`

用户服务：`luna-battery-voice-warning.service`，已启用自动启动。状态：`/run/user/1000/luna-battery-voice-warning/status.json`。该服务独立于显示服务，不修改原有电池屏与旧音频模块；原有充电事件/临界电量语音仍保留。

## 验证

- 4 项策略测试覆盖 29% / 30% 边界、任一电池、充电中、陈旧/断连/无效数据、两块低电量不重复和 10 秒间隔。
- 使用同一音频与播放路径执行 `--test-playbacks 3`。测试绕过触发条件进行播报，不更改实机电量或图像文字；具体结果和开始间隔见 `playback-test-*.json`。
- 首轮 3 次均完整播放、返回码为 0，开始间隔约 10 秒；用户现场确认“已听到 3 次，正常”。随后按用户追加要求执行独立的 10 次播报测试，保留两轮各自报告。
- 追加 10 次也已完成：10 次播放返回码均为 0，9 个相邻开始间隔均在 10 秒 ±0.2 秒内。详细汇总为 `test-completion-summary.json`。两轮合计 13 次。
- 显示与原有电池屏源文件校验记录为 `unchanged-display-files.sha256`。

## 停用

```sh
systemctl --user disable --now luna-battery-voice-warning.service
```

仅停用新增语音，摄像头、MAXHUB 和原有电池显示继续运行。
