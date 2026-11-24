# 厂家 30% 电量设置核对

本轮只读检查，没有切换模式、使能机械臂、修改电量阈值或限位。

## 当前实机参数与厂家界面定义

从 `http://6.6.7.6:8080/api/Config/AMR/GetParam`、`/api/Config/Chassis/GetParam`、`/api/Config/GetAllParam` 读取成功，ErrorCode=0。

| 参数 | 当前实机值 | 厂家界面定义/范围 |
|---|---:|---|
| energy.threshold.force_charge | 30 | 开始强制充电阈值；界面允许范围为 [低电量报警阈值,100) |
| energy.threshold.low_alarm | 20 | 低电量报警阈值；界面允许范围为 (0,30] |
| energy.enable_auto_charge | true | 启用自动充电 |
| robot.power_off.delay_time | 3.0 秒 | 底盘关机延时；界面范围 [0,300] 秒，不是电量百分比 |

中文定义来自本机原厂底盘前端 `static/js/app.294b6902481793bd68e2.js`，完整只读副本已保存。此处“当前实机值”不宣称为所有出厂机器的默认值。

已暴露的 AMR、Chassis 和系统参数中，未发现“低于 30% 单独关闭右臂 J6”的设置。已检查 Apex 后端可读源码、环境配置和本地 SDK L1 源码，未发现基于电池 SOC 的 J6 禁止使能逻辑。这不覆盖未公开的底盘固件、BMS 或关节驱动器内部逻辑。

## 厂家原始手册

从厂家资源页获取《Gento Luna轮式双臂机器人产品使用说明书》，PDF 和提取文本保存于本目录。

- 原始 PDF：https://drive.google.com/file/d/1R9ApABLZ0kmlDKsaYNNtv2Pgc248w2iq/view
- 资源索引：https://docs.gentorobotics.ai/zh-CN/resources/downloads/
- 手册 3.9.2 说明：启用回充后，SOC 低于设定阈值且没有执行任务时进入自动回充；需完成充电站安装和地图配置。
- 文本检索未找到 30% 触发单独 J6 断电的说明，也没有取得 BMS 欠压切断和伺服母线欠压的具体保护门槛。
- SDK 错误字典将 0x3220 定义为 DC bus under voltage、0xFF26 为 Control power under voltage、0xFF80/0xFF81 为主电源丢失/异常。此前捕获的 100 整臂状态和 102/106 系统错误并不等价于这些具体欠压码。

## 实时供电复核

最新只读底盘快照 `power-threshold-live-state-20261124.json`：

- 电池 1：38%，约 50.3 V，充电约 4.7 A，19℃，errorCode=0。
- 电池 2：37%，约 50.3 V，充电约 5.0 A，20℃，errorCode=0。
- 两块均在位、已连接且充电中，底盘正常，driverErrorCodeVec 为空，exceptions=[0,0,0]。
- energyLevel 从此前原始值 2 变为 1，仅记录变化；未取得该枚举的厂家定义，不据此推断机械臂供电状态。

结论：本机确有 30% 的补能策略阈值，尚无证据认定它会切断 J6。供电假设仍需验证；充电中的 BMS 正常读数不能排除故障瞬间的局部供电压降。区分 SOC 策略、BMS 保护和驱动器欠压，需要在下一次合规静态使能时同步记录实际供电与具体关节故障码，必要时由厂家读取驱动器保护参数并测量局部供电。本轮不触发运动来验证。
