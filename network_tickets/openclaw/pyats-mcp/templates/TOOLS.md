# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## Network Devices (pyATS)

**当用户提问涉及网络设备、接口、路由、配置、日志、ping：必须触发 `pyats` skill，并使用 `exec` 工具执行。**

强制规则：
- **禁止**在没有执行工具的情况下回复“没权限 / 连接不稳定 / 设备故障 / 未找到工具”等推测性结论
- **禁止**尝试在本地安装或查找 pyATS Python 包（pyATS 运行在远程容器）
- **禁止**使用 `read`/`cat` 查找 `testbed.yaml`，也**禁止**向用户索要该文件路径
- **禁止**执行 `pyats ...` 这类本地命令（会报 Command not found）
- 若命令失败：**直接返回工具输出的 error / 原始输出**，不要编造原因
- **失败不要气馁：最多尝试 5 次**，每次换一个命令/思路
- 不要把具体设备名、接口名、IP、计数器写进任何文档里（只在当次回复里展示）
