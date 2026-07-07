# ENI-RAT 修复版 (Fixed Edition)

> **中文** | [English](#english)

**远程管理工具包 — C2 命令与控制框架**

面向红队行动、安全评估和授权渗透测试的完整 C2 框架。端到端 AES-256 加密、跨平台 Agent、浏览器控制面板。

**基于 [Adam-ZS/ENI-RAT](https://github.com/Adam-ZS/ENI-RAT) 修复，原作者 [@Adam-ZS](https://github.com/Adam-ZS)。**

```
本工具仅限授权安全测试和教育用途。
未经授权访问计算机系统属于违法行为。使用者须遵守所有适用法律。
```

---

## 本 Fork 修复内容（9 个关键 Bug）

原始版本有 9 个 Bug 导致 C2-Agent 管道在 Windows 上完全不可用：

| # | Bug | 影响 | 修复 |
|---|-----|------|------|
| 1 | WebSocket 客户端帧缺少 RFC 6455 Masking | Agent 永远连不上 C2 服务器 | 按协议规范为帧添加掩码 |
| 2 | Keylogger  语法错误 | Agent 启动即崩溃 | 修正为  |
| 3 | REST API 任务只写内存不查 DB | Web 面板发命令 Agent 拿不到 |  改为读 SQLite |
| 4 | 心跳 ack 与任务响应帧碰撞 | Agent 消费了错误的 WebSocket 帧 | 心跳静默处理；循环排空混合响应 |
| 5 | 任务执行无异常保护 | 一个任务失败整个线程崩 | 所有任务包 try/except |
| 6 | 每次重连生成新 Agent ID | Web 面板命令发到僵尸 Agent | hostname 匹配复用已有 agent_id |
| 7 | 断线不重连 | 死 socket 空转，线程永不复原 | 断线检测 + 指数退避重试 |
| 8 | Google Fonts @import 阻塞面板 | 防火墙环境下页面卡死 | 改用系统字体，零外部依赖 |
| 9 | Windows GBK 编码崩溃 | emoji 导致服务器启动失败 | PYTHONIOENCODING=utf-8 |

## 新增功能

- **`start.bat`** — 双击一键启动 C2 + API + 面板
- **死 Agent 自动检测** — 60 秒无心跳 → 状态标 dead
- **MachineGuid 指纹** — 同机器重连保持相同 agent_id
- **WebSocket 线程安全** — send/recv 锁保护
- **自动重连** — 网络恢复后 Agent 自己回来

## 已知未修复

| 问题 | 状态 |
|------|------|
| 截图分辨率硬编码 1920x1080 | 源码已修，待重新构建 |
| 无文件管理器 — 仅支持单文件上传/下载 | 功能缺失 |
| 无远程桌面 — 仅截图，无实时画面 | 功能缺失 |
| 进程注入仅为空壳函数 | 未实现 |
| AV 免杀仅用户态 patch（VirtualProtect） | 对抗 EDR 较弱 |

---

## 快速开始

### 环境

```bash
pip install -r requirements.txt
```

### 启动 C2 服务器

**Windows（推荐）：**
```
双击 start.bat
```
自动启动 C2 WebSocket、REST API 和 Web 面板。

**手动：**
```bash
set PYTHONIOENCODING=utf-8
python start.py
```

启动两个服务：
- WebSocket 服务器端口 8443（Agent 通信）
- REST API 和 Web 面板端口 5000

浏览器打开  进入控制面板。

### 构建 Payload

```bash
python builder/builder.py --host 你的IP地址
```

Builder 将 C2 服务器 IP 嵌入 Payload，同时生成唯一的 AES-256 密钥对。

**Builder 参数：**

| 参数 | 说明 |
|------|------|
|  | C2 服务器 IP 或主机名（必填） |
|  | WebSocket 端口（默认 8443） |
|  | REST API 端口（默认 5000） |
|  | PyInstaller 编译为 Windows 可执行文件（无窗口） |
|  | PyArmor 混淆 |
|  | 不安装持久化 |
|  | 跳过沙箱/虚拟机检测 |

---

## 架构

```
  目标机器                        你的机器
  +-----------------+             +----------------------+
  |   Agent          |             |   C2 服务器           |
  |   (payload.py    |<--AES-256--|                      |
  |    或 .exe)      |  WebSocket  |  WebSocket :8443     |
  |                  |             |  REST API  :5000     |
  |  - 键盘记录      |             |  SQLite 数据库       |
  |  - 屏幕截图      |             |  Web 面板            |
  |  - Shell 执行    |             |  死 Agent 检测       |
  |  - 文件操作      |             |                      |
  |  - 持久化        |             +----------+-----------+
  |  - AV 免杀       |                        |
  |  - 自动重连      |              +----------+-----------+
  +-----------------+              |  控制界面            |
                                   |                      |
                                   |  Web 面板            |
                                   |  桌面 GUI            |
                                   |  命令行              |
                                   +----------------------+
```

---

## Agent 命令

Agent 上线后通过 C2 面板发送命令：

| 命令 | 功能 |
|------|------|
|  | 在目标执行系统命令 |
|  | 截取屏幕并回传图片 |
|  | 开始键盘记录 |
|  | 停止键盘记录并回传 |
|  | 窃取目标文件 |
|  | 下载文件到目标 |
|  | 安装持久化 |
|  | 尝试终止杀软进程 |
|  | 返回系统信息 |
|  | 暂停 Agent 指定时长 |
|  | 退出 Agent |
|  | 清除所有痕迹并删除自身 |

---

## 项目结构

```
+-- server/
|   +-- c2_core.py          WebSocket C2 服务器
|   +-- api_server.py       REST API 和 Web 面板
+-- client/
|   +-- payload.py          跨平台 Agent
+-- gui/
|   +-- rat_gui.py          桌面 GUI
+-- builder/
|   +-- builder.py          Payload 构建器
|   +-- update_ddns.sh      DDNS 更新脚本
+-- docs/
|   +-- specs/              设计文档
+-- start.py                启动脚本
+-- start.bat               Windows 一键启动
+-- requirements.txt        Python 依赖
```

---

## 加密

Agent 与 C2 之间所有通信使用 AES-256 CBC 模式加密。每次构建生成唯一的 32 字节密钥和 16 字节 IV，嵌入 Payload，绝不通过网络传输。

---

## 系统要求

- Python 3.8+
- C2 服务器：Linux 或 Windows
- Agent：Windows 或 Linux
- 依赖见 requirements.txt

---

## 许可证与免责声明

本软件仅供授权安全测试、研究和教育用途。未经授权访问计算机系统属于违法行为。作者不承担任何责任，不对任何滥用或损害负责。

使用本软件即表示你同意遵守所有适用的地方、州、国家和国际法律。

---

**修复版维护者 [@fg-time](https://github.com/fg-time)。原作者 [@Adam-ZS](https://github.com/Adam-ZS)。为红队行动而生。**

---

<a name="english"></a>
## English

**Fork of [Adam-ZS/ENI-RAT](https://github.com/Adam-ZS/ENI-RAT) by [@Adam-ZS](https://github.com/Adam-ZS)** — C2 framework with 9 critical bugs fixed for Windows deployment.

### Bug Fixes Summary

| # | Bug | Fix |
|---|-----|-----|
| 1 | WebSocket client masking missing | RFC 6455 compliant masking |
| 2 | Keylogger import syntax error | Fixed  access |
| 3 | REST API task queue isolated from C2 | DB-driven task queue |
| 4 | Heartbeat/task response race | Silent heartbeat + drain loop |
| 5 | No exception guard on tasks | try/except wrapper |
| 6 | Agent ID regenerated each reconnect | Hostname-based ID reuse |
| 7 | No auto-reconnect | Disconnect detection + backoff |
| 8 | Google Fonts @import | System font stack |
| 9 | GBK encoding crash | PYTHONIOENCODING=utf-8 |

### New Features

-  — one-click launcher
- Dead agent detection (60s timeout)
- MachineGuid fingerprint
- Thread-safe WebSocket
- Auto-reconnect

### Known Issues

| Issue | Status |
|-------|--------|
| Screenshot resolution hardcoded | Fixed, pending rebuild |
| No file browser | Missing |
| No remote desktop | Missing |
| Process injection stub | Not implemented |
| Basic AV evasion | Weak against EDR |

**Fixed Edition by [@fg-time](https://github.com/fg-time). Original by [@Adam-ZS](https://github.com/Adam-ZS). Built for red team operations.**
