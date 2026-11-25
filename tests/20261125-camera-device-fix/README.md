# 2026-11-25 D435 黑屏 / USB 枚举修复

重启后 D435 序列号 344223024944 的 RGB 接口移至 `/dev/video14`，旧配置仍写 `/dev/video12`，而该编号现在是红外通道。程序选择 UYVY 1280×720，出现 CUDA illegal memory access 700，仍有服务进程和黑帧，因此 GUI Camera 绿灯不能证明采集正常。

固定身份为 USB 彩色接口 03，稳定链接：`/dev/v4l/by-path/platform-14160000.pcie-pci-0004:01:00.0-usb-0:2:1.3-video-index0`。厂家当前 URI 解析器只接受 `/dev/video数字`，不接受该完整符号链接 URI；直接传稳定路径的中间尝试失败日志保留，随后改为启动前解析实际编号。

新增 Camera 服务 drop-in `70-d435-device.conf`，每次启动前运行 `resolve_color_camera.py`：等待接口就绪，核验序列号、USB interface 03、YUYV 1920×1080 能力，然后只替换 `head_cam_source` 和 `camera_sources.head_left` 两个来源字段。其他 YAML 字节不变，1920×1080、30 FPS、码率、房间号等不变。没有改 Robot/Teleop/Tool 或 MAXHUB；不修改冻结基准。

USB 端口路径稳定性依赖相机接在当前机器人端口；移到其他 USB 物理端口时会明确启动失败，而不会误开深度/红外相机。

修改前后配置、设备映射、采集故障日志和修复后验证存于本目录。回退需要恢复 `apex-color1080.before.yaml` 并移除新增 drop-in，再重启 Camera；回退到写死 video12 的版本不保证在新的枚举顺序下有画面。
