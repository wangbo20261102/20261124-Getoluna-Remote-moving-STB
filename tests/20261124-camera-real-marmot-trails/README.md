# 参考照片外观的移动对打土拨鼠

2026-11-24 按用户提供的土拨鼠照片作为外观参考，使用 imagegen 生成 4×4、16 帧透明图集。生成原图保存在项目 `assets/marmot-atlas.png`，原始生成文件也保留在 Codex generated_images。`pack_generated_atlas.py` 仅执行网格拆帧、统一裁切和播放格式编码，不重绘照片。

- 第一行乌龟：保持原速度、单向慢爬、密集点线、到右侧隐藏 0.6 秒后从左重现。
- 第二行土拨鼠：棕色厚毛、小圆耳、深色鼻子，贴近参考照片的写实外观；两只面对面对打，整组向右移动。密集点线、起点、活动范围和重现规则与乌龟一致，不再原地停留，也不掉头。
- 土拨鼠组使用原第二行动画的独立慢速：全高清画面约 7.68 像素/秒；乌龟约 11.52 像素/秒。各自循环，不强制同步。
- 两条路线均为约 77 个小点、点宽 2 像素、间隔约 1 像素。对打动作是 16 帧、12.5 fps 的循环；平移由显示引擎独立控制。
- 对应电池确认充电且数据有效才显示。原电量文字、低于 30% 红色提示、检测到充电后停止语音等规则保留。

## 运行位置与接口

机器人目录：`/home/nvidia/luna-test-runs/20261124-camera-real-marmot-trails`

用户服务：`luna-camera-real-marmot-trails.service`。配置仍为 `animations.json`，支持类型、位置、大小、速度基准、点数与点大小。原有版本分别保留在独立目录，未覆盖冻结基准。

内部动画控制仅使用本机用户 IPC：`ipc:///run/user/1000/luna-camera-real-marmot-trails/animation.sock`，不控制机器人运动。

## 验证和回退

9 项检查通过，包括电量边界与过期、两组动画同轨迹且独立速度、边界重现和密集点线。离线渲染与实际画面位于 `qa`。原始冻结基准核验见 `baseline-verification.json`。

回退到前一版原地对打卡通土拨鼠：

```sh
systemctl --user disable --now luna-camera-real-marmot-trails.service
systemctl --user enable --now luna-camera-marmot-animation.service
```

回退仅切换显示预览，不重启 MAXHUB 客户端、机械臂控制或语音服务。
