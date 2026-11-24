# 摄像头 / MAXHUB 实时电量叠加

2026-11-24 已部署。用户已确认 MAXHUB 大屏显示两块电池电量，画面正常。

- 画面右上角显示两块电池各自 SOC 及充电/使用状态。
- 任一电池 SOC < 30% 时，对应电池文字变红，画面下方出现红色“电量低于 30%，请优先充电”。30% 本身保持正常颜色。
- 电量数据缺失、断连或过期时显示黄色未知提示，不保留旧的正常百分比。
- 复用 `/run/luna-battery-screen/status.json` 的只读数据；每 0.5 秒检查一次，前端文本原子更新。既检查上游 fresh 标记，也检查状态文件更新时间。
- 在现有机器人本地 D435 预览上叠加；MAXHUB 对同一桌面投屏，因此同步显示。未改 Apex / PICO 的原始 ROS 图像话题或 WebRTC 服务。
- 未修改机械臂控制、厂家电量保护阈值、J6 限位、冻结基准或旧版 MAXHUB 启动与守护源文件。DongleClient PID 7497 未重启。

## 运行位置

独立部署目录：`/home/nvidia/luna-test-runs/20261124-camera-battery-overlay`

用户服务：`luna-camera-battery-overlay.service`，已启用当前运行与用户会话启动。该服务与旧 `luna-maxhub-preview-guard.service` 互斥；旧服务原文件保留且原先即未启用。

运行状态：`/run/user/1000/luna-camera-battery-overlay/display-state.json`

日志：部署目录内 `preview-*.log` 和该用户服务日志。新预览收到 60 帧并有新鲜心跳后才退出旧预览；持续无图像心跳时重启预览，不重启 Robot / Teleop / Tool / DongleClient。

## 验证

- Windows 与机器人各通过 5 项策略测试，覆盖 29%/30% 边界、任一电池、充电时低电量、过期、断连和无效数据。
- `qa/live-display.png` 是部署后实际显示器画面；`qa/low-29-30.png`、`qa/stale.png` 是离线渲染样例。低电量样例未注入实机数据。
- 新预览持续收到摄像头帧；两块电池显示数据 fresh=true。
- 原版预览、原版守护和原版用户服务通过 `original-files.sha256` 校验。旧测试基准核验见 `baseline-verification.json`。
- 用户现场确认：“已显示，画面正常”。

## 回退

在机器人用户会话中依次执行：

```sh
systemctl --user disable --now luna-camera-battery-overlay.service
systemctl --user start luna-maxhub-preview-guard.service
```

原版守护会恢复无叠加的旧预览。此回退不重启 MAXHUB 客户端，不调用机械臂使能、复位或运动接口。
