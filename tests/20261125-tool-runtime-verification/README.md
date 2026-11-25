# 2026-11-25 工具参数运行时核验

用户确认“空载，双腕已支撑，FXPlatform 已断开”后，仅启动 `apex-robot.service`，随后调用 `/control/set_ready`；未执行 Home、模式切换、遥操、夹爪或搬运动作。

通过运行中的 `/marvin_robot_node/get_parameters` 同时读取 `left_tool`、`right_tool`，两组均为：

`[1.8, 0, 0, 0, 0.004, 0, 0, 0.004, 0, 0.03]`

原始返回见 `robot-parameter-response.txt`。已确认 Robot 进程实际加载保存的参数，不是仅查看硬盘文件，也不是 FXPlatform 输入框显示。

Set ready 返回成功；连续 6 次控制器反馈均新鲜、ready=true、error=false，各部件状态均为 0（待机）。当前没有关节保持使能，应继续保留物理支撑，直到现场正常进入所需控制模式。

配置与 SDK 校验不变；MAXHUB 客户端 PID 5625 保留，摄像头、显示、语音服务 active。启动前后状态、参数响应、控制器采样、启动日志及 `verification-result.json` 保留。

证据范围：Robot 运行参数服务读回与控制器通信健康状态；不是控制器 EEPROM 的独立读回或整机断电重启验证。FXPlatform 仍可能显示其默认全 0 输入框，不能据此重复覆盖参数。
