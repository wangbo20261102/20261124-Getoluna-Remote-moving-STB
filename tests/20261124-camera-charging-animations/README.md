# 摄像头 / MAXHUB 充电动画

2026-11-24 已部署，用户已确认“已看到，动画正常”。

保留原有两行电量、充电文字、红色低电量提示与过期提示。对应电池确认充电且数据有效时，在文字后方显示透明背景的彩色爬行动画：

- 电池 1：绿色乌龟，摆腿、轻微起伏，40 秒往返一次。
- 电池 2：暖色蜗牛，身体轻微起伏，60 秒往返一次。
- 动画各 16 帧，12.5 fps；各自在独立区域往返，转向时翻转朝向。停止充电、断连或数据过期后隐藏。
- 动画不改摄像头源话题或机械臂控制，只叠加到现有本地预览与 MAXHUB 投屏桌面。语音规则继续由独立的充电静音版本处理。

## 自定义接口

配置文件：本目录 `animations.json`。机器人对应路径为 `/home/nvidia/luna-test-runs/20261124-camera-charging-animations/animations.json`。

| 字段 | 含义 |
|---|---|
| schema_version | 配置版本，当前为 1 |
| enabled | 总开关，运行中自动读取；false 隐藏两只动物 |
| batteries.1 / batteries.2 | 每块电池的动画配置 |
| kind | turtle 或 snail |
| width / height | 动画画布大小，像素 |
| x_fraction / y_fraction | 起点相对摄像头画面的位置 |
| travel_fraction | 水平活动范围，占画面宽度的比例 |
| cycle_seconds | 完整往返周期，秒 |

除 enabled 外，修改位置、大小、种类或周期后，需要重启动画预览服务；不需要重启摄像头采集、MAXHUB 客户端或机械臂控制模块。配置非法时不应用未经校验的参数。

运行状态：`/run/user/1000/luna-camera-charging-animations/display-state.json` 与 `animation-state.json`，后者记录 desired 和 applied 状态。

内部控制接口：`ipc:///run/user/1000/luna-camera-charging-animations/animation.sock`。仅本机用户可访问，不开放网络端口。FFmpeg 命令 `overlay@battery1 enable 0/1`、`overlay@battery2 enable 0/1` 控制各动画可见性。正常运行由只读电池状态自动驱动，不应使用该接口代替实机充电反馈。

## 服务与保留记录

当前用户服务：`luna-camera-charging-animations.service`，已启用自动启动。

上一版 `luna-camera-battery-overlay.service` 保留原文件，停用自动启动。新预览收到 60 帧且心跳新鲜后才停旧服务。DongleClient PID 7497 保持运行，语音服务不重启。

验证：5 项电量显示策略检查通过；离线动画合成通过；两个动画启用、隐藏的 4 条控制命令均得到 `0 Success`；实际预览与两张间隔约 4 秒的显示器画面保存于 `qa`；用户已现场确认大屏动画正常。完整历史基准核验见 `baseline-verification.json`。

## 回退

```sh
systemctl --user disable --now luna-camera-charging-animations.service
systemctl --user enable --now luna-camera-battery-overlay.service
```

回退仅切换预览，保留 MAXHUB 客户端与现行语音充电静音规则。
