# 2026-11-25 Apex 阻抗成功版本冻结记录

用户确认修复效果后要求保存全部资料，并明确一并同步现有GitHub仓库。本次仅采集、归档、索引和同步；没有继续修改运行逻辑、参数或服务状态。

正式Apex后端已部署且SHA-256为 `060945ed9b2efeced2767840369ede8cfe527d53c04fbc2a12ee35118b126f6d`。原始Apex待机→阻抗按钮已验证成功，双臂2，6次新鲜反馈ready=true、error=false；14项后端测试及两轮临时接口实机验证保留。Robot二进制与SDK未替换。当前工具质量配置为双侧1.5kg，本次冻结未改变该值；早先1.8kg记录仍作为历史证据保留。

## 冻结副本

- 两份完整快照合计14,991个文件/链接条目，捕获原始字节1,863,123,570，压缩后640,413,477字节。
- 本地：`archives/20261125-apex-impedance-frozen`；机器人：`/home/nvidia/luna-archive-exports/20261125-apex-impedance-frozen`。
- [冻结发布页](https://github.com/wangbo20261102/20261124-Getoluna-Remote-moving-STB/releases/tag/apex-impedance-frozen-20261125) 提供两份tar.gz、来源清单和SHA-256清单；旧发布与冻结基准保留。
- 23项当前部署文件与机器人、本地current-config镜像一致；校验见 `manifests/20261125-apex-frozen/synchronization-verification.json`。
- 完整逐文件清单、校验和采集范围见 `manifests/20261125-apex-frozen/`。被更新的旧索引/镜像原件保存在 `manifests/history/20261125-before-apex-freeze/`。

## 采集边界

用户在冻结前自行恢复了Robot/Teleop/Tool/底盘桥；本次没有为归档启停任何服务，也没有SDK控制会话或运动指令。当前快照状态为双臂2、ready=true、error=false。设备时钟不同，保留各端原始时间，不调整时钟。

实时底盘遥测采集前缀为332,167,954字节，源文件在采集期间增长到332,208,958字节；该文件的后续新增内容不属于此次冻结范围。未发生文件截断，无采集错误。不是硬盘镜像、控制器EEPROM备份或后台持续同步。

`tests/20261125-apex-impedance-entry-fix/src` 的旧源码研究未采用、未部署；该目录的发布说明有明确记录。正式运行只更新Apex后端，不应误用旧Robot参考源码。
