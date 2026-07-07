# ENI-RAT — Fixed Edition

**Remote Administration Toolkit — Command & Control Framework**

A complete C2 framework designed for red team operations, security assessments, and authorized penetration testing. End-to-end AES-256 encryption, cross-platform agents, and a browser-based control panel.

**Fork of [Adam-ZS/ENI-RAT](https://github.com/Adam-ZS/ENI-RAT) by [@Adam-ZS](https://github.com/Adam-ZS).**

```
This tool is for authorized security testing and educational purposes only.
Unauthorized access to computer systems is illegal. You are responsible
for complying with all applicable laws.
```

---

## What This Fork Fixes (9 Critical Bugs)

The original had 9 bugs that prevented the C2-agent pipeline from working on Windows:

| # | Bug | Impact | Fix |
|---|-----|--------|-----|
| 1 | WebSocket RFC 6455 client masking missing | Agent never connected to C2 server | Frames now masked per protocol spec |
| 2 | Keylogger `import ctypes.windll.user32` | Agent crashed on startup | Fixed to `user32 = ctypes.windll.user32` |
| 3 | REST API tasks only in memory, not DB | Web dashboard commands never executed | `get_pending_tasks()` reads SQLite |
| 4 | Heartbeat ack collides with task response | Agent consumed wrong WebSocket frames | Heartbeat silent; drain loop handles mixed types |
| 5 | No exception guard on task execution | One failing task kills entire check-thread | Every task wrapped in try/except |
| 6 | Agent ID regenerated on every reconnect | Web dashboard targeted dead agent IDs | Hostname match reuses existing agent_id |
| 7 | No auto-reconnect on disconnect | Dead socket spin, threads never recover | Disconnect detection + exponential backoff |
| 8 | Google Fonts @import blocks dashboard | Web panel hangs on firewalled networks | System font stack, zero external deps |
| 9 | GBK encoding crashes on Windows | Emoji in print() kills server startup | UTF-8 enforced via PYTHONIOENCODING |

## What's New in This Edition

- **`start.bat`** — Double-click to launch C2 + API + Dashboard
- **Dead agent auto-detection** — 60s no heartbeat → status = dead
- **MachineGuid fingerprint** — Same machine = same agent_id across reconnects
- **Thread-safe WebSocket** — Lock-protected send/recv across threads
- **Auto-reconnect** — Agent recovers from network drops automatically

## Known Issues (Not Yet Fixed)

| Issue | Status |
|-------|--------|
| Screenshot resolution hardcoded to 1920x1080 | Fixed in source, pending rebuild |
| No file browser — single file upload/download only | Missing feature |
| No remote desktop — screenshot only, no streaming | Missing feature |
| Process injection is a stub | Not implemented |
| AV evasion uses basic user-mode patching | Weak against EDR |

---

## Quick Start

### Requirements

```bash
pip install -r requirements.txt
```

### Start the C2 Server

**Windows (Recommended):**
```
Double-click start.bat
```
Opens C2 WebSocket, REST API, and web dashboard automatically.

**Manual:**
```bash
set PYTHONIOENCODING=utf-8
python start.py
```

This starts two services:
- A WebSocket server on port 8443 (agent communications)
- A REST API and web dashboard on port 5000

Open `http://localhost:5000` in a browser to see the control panel.

### Build a Payload

```bash
python builder/builder.py --host YOUR_IP_ADDRESS
```

The builder takes your C2 server's IP or hostname and embeds it into the agent payload along with a unique AES-256 key pair. The output is a Python script that, when run on the target, connects back to your C2.

**Builder options:**

| Flag | Description |
|---|---|
| `--host` | C2 server IP or hostname (required) |
| `--ws-port` | WebSocket port (default: 8443) |
| `--api-port` | REST API port (default: 5000) |
| `--compile` | Compile to a Windows executable via PyInstaller (--noconsole, hidden) |
| `--obfuscate` | Obfuscate with PyArmor |
| `--no-persistence` | Exclude persistence mechanisms |
| `--no-sandbox-check` | Exclude sandbox/VM detection |

---

## Architecture

```
  TARGET MACHINE                   YOUR MACHINE
  +-----------------+             +----------------------+
  |   Agent          |             |   C2 Server          |
  |   (payload.py    |<--AES-256--|                      |
  |    or .exe)      |  WebSocket  |  WebSocket :8443     |
  |                  |             |  REST API  :5000     |
  |  - Keylogger     |             |  SQLite Database     |
  |  - Screenshot    |             |  Web Dashboard       |
  |  - Shell         |             |  Dead Agent Scanner  |
  |  - File ops      |             |                      |
  |  - Persistence   |             +----------+-----------+
  |  - AV evasion    |                        |
  |  - Auto-reconnect|              +----------+-----------+
  +-----------------+              |  Control Interface   |
                                   |                      |
                                   |  Web Dashboard       |
                                   |  Desktop GUI          |
                                   |  Command Line        |
                                   +----------------------+
```

---

## Agent Commands

Once an agent checks in, you can send it commands through the C2 interface.

| Command | What It Does |
|---|---|
| `shell <command>` | Execute a shell command on the target |
| `screenshot` | Capture the target's screen and return the image |
| `keylog_start` | Begin capturing keystrokes |
| `keylog_stop` | Stop the keylogger and retrieve captured data |
| `upload <path>` | Read a file from the target and exfiltrate it to the C2 |
| `download <url> <path>` | Download a file from a URL and save it to the target |
| `persist` | Install persistence on the target |
| `kill_av` | Attempt to terminate antivirus processes |
| `info` | Return system information (OS, hostname, user, IPs) |
| `sleep <seconds>` | Pause the agent for a specified duration |
| `exit` | Tell the agent to terminate |
| `selfdestruct` | Remove all traces, persistence mechanisms, and delete the agent binary |

---

## Project Structure

```
+-- server/
|   +-- c2_core.py          WebSocket C2 server and agent communication handler
|   +-- api_server.py       REST API and browser-based web dashboard
+-- client/
|   +-- payload.py          Cross-platform agent (Windows and Linux)
+-- gui/
|   +-- rat_gui.py          Desktop GUI built with CustomTkinter
+-- builder/
|   +-- builder.py          Payload builder with configuration injection
|   +-- update_ddns.sh      DDNS update script for the C2 server
+-- docs/
|   +-- specs/              Design documents
+-- start.py                Launches both C2 server and API server
+-- start.bat               One-click Windows launcher
+-- requirements.txt        Python dependencies
+-- README.md
```

---

## Encryption

All agent-to-C2 communications are encrypted with AES-256 in CBC mode. Each build generates a unique 32-byte key and 16-byte initialization vector. These are embedded in the agent payload during the build process and never transmitted over the network.

---

## Requirements

- Python 3.8 or later
- Linux or Windows for the C2 server
- Windows or Linux for agents
- Dependencies listed in requirements.txt

---

## License and Disclaimer

This software is provided for authorized security testing, research, and educational purposes. Unauthorized access to computer systems is illegal. The authors assume no liability and are not responsible for any misuse or damage caused by this program.

By using this software, you agree that you are solely responsible for complying with all applicable local, state, national, and international laws.

---

**Fixed Edition maintained by [@fg-time](https://github.com/fg-time). Original by [@Adam-ZS](https://github.com/Adam-ZS). Built for red team operations.**
