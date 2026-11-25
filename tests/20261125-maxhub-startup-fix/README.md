# 2026-11-25 MAXHUB 重启后未启动修复

## 诊断事实

- 本次联机时机器人刚重启约 16 分钟；WT12 USB `1ff7:0f52` 在位，但 `DongleClient` 无进程。
- 昨天的 `luna-camera-fast-marmots.service`、`luna-battery-voice-warning.service` 均 active/enabled，电池反馈新鲜，65% / 64%，两块均在充电。配置没有丢失。
- 用户与系统启动配置中未发现 DongleClient / start-maxhub / exceedshare 的启动入口。原脚本是手动入口，免密准备正常可执行；免密不等于开机自动启动。
- 启动客户端后日志确认 `Connect broker succuss: 0`，说明已连 WT12 broker，不能仅据此宣称大屏实际画面已确认。
- DP-1 重启后为 1520×720，已恢复昨天的 1920×1080@60。

## 修改

新增用户服务 `luna-maxhub-client.service` 和本目录 guard。开机自动运行；若已有当前用户的 DongleClient，则保留该进程；没有时等待桌面、WT12 和现有免密授权准备完成，恢复 1920×1080 后启动唯一客户端。客户端退出后再次启动。状态：`/run/user/1000/luna-maxhub-client/status.json`。

用户要求保存后，另已明确启用系统服务 `apex-camera.service` 的开机启动，并核对三个用户显示/语音服务均 enabled、用户 linger 已启用。原 `~/luna-ready-20261123/start-maxhub.sh` 已备份并改为调用现有 Camera 和两个显示服务，不再写死 video12，不再直接启动第二个预览。重跑摄像头识别程序确认 changed=false，不会反复改写正确配置。

仅监督显示客户端，不调用机器人控制、模式、Home、运动或语音/摄像头启动接口，不启动第二个预览。充电动画、电量红色阈值、语音充电停止规则和手肘缩放均保留。

客户端存在与 broker 连接不能保证接收屏已开始展示；如果 WT12 要求按中央按钮，仍需现场按下。此版本未执行整机重启测试，也未通过杀掉正在工作的投屏来做故障注入。

摄像头设备修复后已在机器人桌面看到真实彩色场景及原电量/动画，用户也已确认“可以识别了，完美”。本次没有发送机器人运动命令；未通过断电或整机重启中断现有工作来验证下一次开机。

回退：`systemctl --user disable --now luna-maxhub-client.service`。已由服务启动的客户端属于服务进程组，会随停服务而退出；安装前已有的手动客户端不属于新服务进程组。摄像头预览与语音服务不受该回退控制。
