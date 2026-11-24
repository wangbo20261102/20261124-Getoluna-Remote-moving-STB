# 土拨鼠快速对打版本

2026-11-24 按用户“全部保持，仅加快持续双手对打”要求部署。

唯一动画参数变化：电池 2 的 `action_fps` 从默认 12.5 调整为 37.5，对打动作节奏为原来的 3 倍。16 帧动作循环约从 1.28 秒缩短至 0.427 秒。

乌龟和土拨鼠图像素材字节未变；两组平移速度、位置、大小、密集点线、右侧消失与左侧重现规则均不变。摄像头、电量显示、红色提示和充电静音规则保持原样。

机器人目录：`/home/nvidia/luna-test-runs/20261124-camera-fast-marmots`。

用户服务：`luna-camera-fast-marmots.service`。前一版 `luna-camera-real-marmot-trails.service` 源文件保留，切换后停止并取消自动启动。新预览出图后才停旧预览，MAXHUB DongleClient 不重启。

配置接口新增 `action_fps`，只控制角色内部动作，不影响横向位移；取值 1–60，修改后需重启预览服务。

已核验：移除新加的 action_fps 字段后配置与前一版完全一致，两份 GIF 素材 SHA-256 相同，9 项既有显示与运动检查通过。

回退：

```sh
systemctl --user disable --now luna-camera-fast-marmots.service
systemctl --user enable --now luna-camera-real-marmot-trails.service
```
