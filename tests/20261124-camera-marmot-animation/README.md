# 密集轨迹与站立土拨鼠动画

2026-11-24 按用户最新要求生成并部署到现有摄像头预览 / MAXHUB 投屏。

- 第一行：乌龟沿原区域单向慢爬，速度仍为全高清画面约 11.52 像素/秒。爬过的路线逐渐出现密集小点，点宽 2 像素，间隔约 1 像素；到右端后隐藏 0.6 秒，再从左侧开始，不掉头。
- 第二行：蜗牛替换为两只面对面的棕色土拨鼠，原地直立、交替挥爪，循环播放卡通对打。16 帧透明动画，其中 15 帧画面各不相同；不再横向爬行。
- 继续只在对应电池充电且数据有效时显示动画。电量文字、低于 30% 的红色提示、开始充电停止语音等规则均保留。

## 接口

配置为本目录 `animations.json`。新增支持 `kind=marmots`、`motion=stationary`、`trail_dot_size`。`trail_dots` 设置为 77，`trail_dot_size` 设置为 2 时，乌龟路线为当前密集点线。

`motion=forward_wrap` 保留单向行走和循环重现；`motion=stationary` 仅播放原地动作。其他大小、位置、周期配置沿用此前接口。`cycle_seconds` 保留原往返周期基准；单向行走时间为其一半，以保持原有移动速度。

## 运行和验证

机器人目录：`/home/nvidia/luna-test-runs/20261124-camera-marmot-animation`

当前用户服务：`luna-camera-marmot-animation.service`，已启用自动启动。上一版 `luna-camera-animal-trails.service` 的源文件与配置保留，已停止并取消自动启动。

新预览收到 60 帧并确认心跳新鲜后才停止上一版。MAXHUB DongleClient PID 7497 保持运行，机械臂控制及语音服务未重启。

9 项检查通过，覆盖电量边界、失联过期、乌龟速度与重现、土拨鼠原地动作和点线密度。离线渲染及实际显示器画面见 `qa/phase-10.png`、`qa/live-display.png`。素材源代码为 `make_marmots.py`；上一版乌龟素材原样复用。

原始冻结基准核验见 `baseline-verification.json`。

## 回退到上一版

```sh
systemctl --user disable --now luna-camera-marmot-animation.service
systemctl --user enable --now luna-camera-animal-trails.service
```

仅切换预览，不重启 MAXHUB 客户端或语音服务。
