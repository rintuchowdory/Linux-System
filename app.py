#!/usr/bin/env python3
import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import psutil
import os
import subprocess
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', ping_timeout=60, ping_interval=25)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Linux-System Dashboard</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0f0f1a;
            color: #cdd6f4;
            font-family: 'Segoe UI', Ubuntu, sans-serif;
            min-height: 100vh;
        }
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: 
                radial-gradient(ellipse at 20% 50%, rgba(120, 40, 180, 0.4) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(255, 100, 50, 0.3) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 80%, rgba(40, 100, 255, 0.3) 0%, transparent 50%);
            z-index: -1;
            pointer-events: none;
        }
        .panel {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 25px;
            background: rgba(24, 24, 37, 0.85);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255,255,255,0.05);
            flex-wrap: wrap;
            gap: 10px;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .icons { display: flex; gap: 12px; }
        .icon-btn {
            width: 42px; height: 42px;
            border-radius: 12px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
            color: #fff;
            font-size: 20px;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .icon-btn:hover { 
            background: rgba(137, 180, 250, 0.2); 
            transform: translateY(-2px);
        }
        .stats { display: flex; gap: 20px; font-size: 13px; align-items: center; }
        .stat { display: flex; align-items: center; gap: 6px; }
        .stat-value { color: #89b4fa; font-weight: 600; }
        .actions { display: flex; gap: 10px; }
        .btn {
            padding: 8px 16px;
            border-radius: 8px;
            border: none;
            background: rgba(255,255,255,0.06);
            color: #cdd6f4;
            cursor: pointer;
            font-size: 13px;
            transition: 0.2s;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .btn:hover { background: rgba(137, 180, 250, 0.2); }
        .btn.record { background: rgba(255, 85, 85, 0.8); color: white; }
        .content {
            padding: 25px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .card {
            background: rgba(24, 24, 37, 0.7);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.06);
            transition: transform 0.3s;
        }
        .card:hover { transform: translateY(-2px); }
        .card h3 { margin-bottom: 15px; color: #89b4fa; font-size: 15px; }
        .progress-bar {
            width: 100%; height: 22px;
            background: rgba(255,255,255,0.05);
            border-radius: 11px;
            overflow: hidden;
            margin: 10px 0;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #89b4fa, #b4befe);
            border-radius: 11px;
            transition: width 0.5s ease, background 0.3s ease;
            box-shadow: 0 0 10px rgba(137,180,250,0.3);
        }
        .progress-fill.warning { 
            background: linear-gradient(90deg, #f9e2af, #fab387) !important; 
            box-shadow: 0 0 10px rgba(249,226,175,0.3);
        }
        .progress-fill.danger { 
            background: linear-gradient(90deg, #f38ba8, #ff5555) !important; 
            box-shadow: 0 0 10px rgba(243,139,168,0.3);
        }
        .detail-text { font-size: 12px; color: #a6adc8; margin-top: 8px; line-height: 1.6; }
        .process-list {
            max-height: 350px;
            overflow-y: auto;
        }
        .process-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            font-size: 13px;
            transition: background 0.2s;
        }
        .process-item:hover { background: rgba(255,255,255,0.03); }
        .kill-btn {
            background: rgba(255, 85, 85, 0.8);
            border: none;
            padding: 4px 12px;
            border-radius: 6px;
            color: white;
            cursor: pointer;
            font-size: 12px;
            opacity: 0.8;
            transition: 0.2s;
        }
        .kill-btn:hover { opacity: 1; transform: scale(1.05); }
        #conn-status { font-size: 12px; font-weight: 600; }
        .terminal-card { grid-column: 1 / -1; }
        .terminal-window {
            background: #0c0c14;
            border-radius: 12px;
            padding: 15px;
            border: 1px solid rgba(255,255,255,0.08);
            font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
            font-size: 13px;
            color: #cdd6f4;
            min-height: 250px;
            max-height: 400px;
            overflow-y: auto;
            line-height: 1.5;
        }
        .terminal-input-line {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 5px;
        }
        .terminal-prompt {
            color: #89b4fa;
            font-weight: 600;
            white-space: nowrap;
        }
        .terminal-input {
            background: transparent;
            border: none;
            color: #cdd6f4;
            font-family: inherit;
            font-size: 13px;
            flex: 1;
            outline: none;
        }
        .terminal-line { margin: 1px 0; }
        .terminal-error { color: #f38ba8; }
        .terminal-success { color: #a6e3a1; }
        .terminal-info { color: #f9e2af; }
    </style>
</head>
<body>
    <div class="panel">
        <div class="icons">
            <button class="icon-btn" onclick="alert('Home')">🏠</button>
            <button class="icon-btn" onclick="alert('Settings')">⚙️</button>
            <button class="icon-btn" onclick="alert('Trash')">🗑️</button>
            <button class="icon-btn" onclick="alert('Browser')">🌐</button>
            <button class="icon-btn" onclick="alert('Editor')">📝</button>
            <button class="icon-btn" onclick="alert('Calendar')">📅</button>
            <button class="icon-btn" onclick="alert('Terminal')">💻</button>
        </div>
        <div class="stats">
            <div class="stat" id="conn-status" style="color: #64748b">● connecting</div>
            <div class="stat">CPU: <span class="stat-value" id="cpu">--</span></div>
            <div class="stat">RAM: <span class="stat-value" id="ram">--</span></div>
            <div class="stat">↓<span id="net-down">--</span> ↑<span id="net-up">--</span> KB/s</div>
            <div class="stat">Disk: <span class="stat-value" id="disk">--</span></div>
            <div class="stat">Up: <span id="uptime">--</span></div>
        </div>
        <div class="actions">
            <button class="btn record" id="recordBtn" onclick="toggleRecord()">● Record</button>
            <button class="btn" onclick="alert('Replay')">▶ Replay</button>
            <button class="btn" onclick="alert('Remix')">Remix</button>
            <button class="btn" onclick="loadProcesses()">⚙ Processes</button>
        </div>
    </div>
    
    <div class="content">
        <div class="card">
            <h3>CPU Usage</h3>
            <div class="progress-bar"><div class="progress-fill" id="cpu-bar" style="width: 0%"></div></div>
            <div class="detail-text" id="cpu-cores">Waiting for data...</div>
        </div>
        <div class="card">
            <h3>Memory Usage</h3>
            <div class="progress-bar"><div class="progress-fill" id="ram-bar" style="width: 0%"></div></div>
            <div class="detail-text" id="ram-details">Waiting for data...</div>
        </div>
        <div class="card">
            <h3>Disk Usage</h3>
            <div class="progress-bar"><div class="progress-fill" id="disk-bar" style="width: 0%"></div></div>
            <div class="detail-text" id="disk-details">Waiting for data...</div>
        </div>
        <div class="card" id="process-card" style="display:none;">
            <h3>Top Processes</h3>
            <div class="process-list" id="process-list"></div>
        </div>
        <div class="card terminal-card">
            <h3>💻 Bash Terminal</h3>
            <div class="terminal-window" id="terminal">
                <div class="terminal-line terminal-info">Linux-System Web Terminal v1.0</div>
                <div class="terminal-line terminal-info">Type 'help' for available commands</div>
            </div>
            <div class="terminal-input-line">
                <span class="terminal-prompt">user@render:~$</span>
                <input type="text" class="terminal-input" id="terminal-input" placeholder="" 
                       autocomplete="off" spellcheck="false"
                       onkeydown="if(event.key==='Enter'){runCommand(this.value);this.value='';}">
            </div>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        const socket = io({ transports: ['websocket', 'polling'] });
        
        socket.on('connect', () => {
            const el = document.getElementById('conn-status');
            el.textContent = '● live';
            el.style.color = '#22c55e';
        });
        
        socket.on('disconnect', () => {
            const el = document.getElementById('conn-status');
            el.textContent = '● offline';
            el.style.color = '#ef4444';
        });
        
        function setBar(id, value) {
            const el = document.getElementById(id);
            el.style.width = Math.min(value, 100) + '%';
            el.classList.remove('warning', 'danger');
            if (value >= 90) el.classList.add('danger');
            else if (value >= 70) el.classList.add('warning');
        }
        
        socket.on('stats', (data) => {
            document.getElementById('cpu').textContent = data.cpu + '%';
            document.getElementById('ram').textContent = data.ram + '%';
            document.getElementById('net-down').textContent = data.net_down;
            document.getElementById('net-up').textContent = data.net_up;
            document.getElementById('disk').textContent = data.disk + '%';
            document.getElementById('uptime').textContent = data.uptime;
            
            setBar('cpu-bar', data.cpu);
            setBar('ram-bar', data.ram);
            setBar('disk-bar', data.disk);
            
            document.getElementById('cpu-cores').innerHTML = data.cores.map((c,i) => 
                `Core ${i}: ${c}%`).join('<br>');
            document.getElementById('ram-details').innerHTML = 
                `Used: ${data.ram_used}GB / Total: ${data.ram_total}GB`;
            document.getElementById('disk-details').innerHTML = 
                `Used: ${data.disk_used}GB / Total: ${data.disk_total}GB`;
        });
        
        socket.on('processes', (data) => {
            const list = document.getElementById('process-list');
            if (!data || data.length === 0) {
                list.innerHTML = '<div class="process-item">No processes found</div>';
            } else {
                list.innerHTML = data.map(p => `
                    <div class="process-item">
                        <span>PID ${p.pid} | ${p.name} | CPU ${p.cpu}% | MEM ${p.mem}%</span>
                        <button class="kill-btn" onclick="confirmKill(${p.pid}, '${p.name.replace(/'/g, "\\\\'")}')">Kill</button>
                    </div>
                `).join('');
            }
            document.getElementById('process-card').style.display = 'block';
        });
        
        socket.on('notification', (data) => {
            alert(data.title + ': ' + data.body);
        });
        
        socket.on('terminal_output', (data) => {
            const term = document.getElementById('terminal');
            const line = document.createElement('div');
            line.className = 'terminal-line';
            if (data.error) line.className += ' terminal-error';
            else if (data.success) line.className += ' terminal-success';
            else if (data.info) line.className += ' terminal-info';
            line.innerHTML = data.output;
            term.appendChild(line);
            term.scrollTop = term.scrollHeight;
        });
        
        let recording = false;
        function toggleRecord() {
            recording = !recording;
            const btn = document.getElementById('recordBtn');
            btn.textContent = recording ? '■ Stop' : '● Record';
            btn.classList.toggle('record');
            socket.emit('record', recording);
        }
        
        function loadProcesses() {
            socket.emit('get_processes');
        }
        
        function confirmKill(pid, name) {
            if (confirm(`Kill process ${name} (PID ${pid})?`)) {
                socket.emit('kill_process', pid);
            }
        }
        
        function runCommand(cmd) {
            if (!cmd.trim()) return;
            const term = document.getElementById('terminal');
            const line = document.createElement('div');
            line.className = 'terminal-line';
            line.innerHTML = '<span class="terminal-prompt">user@render:~$</span> ' + escapeHtml(cmd);
            term.appendChild(line);
            socket.emit('terminal_command', cmd);
            term.scrollTop = term.scrollHeight;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Focus terminal input on load
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('terminal-input').focus();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('get_processes')
def handle_processes():
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            processes.append({
                'pid': info['pid'],
                'name': info['name'][:20],
                'cpu': round(info['cpu_percent'] or 0, 1),
                'mem': round(info['memory_percent'] or 0, 1)
            })
        except:
            pass
    processes.sort(key=lambda x: x['cpu'], reverse=True)
    emit('processes', processes[:20])

@socketio.on('kill_process')
def handle_kill(pid):
    try:
        os.kill(int(pid), 15)
        emit('notification', {'title': 'Killed', 'body': f'PID {pid} terminated'})
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('terminal_command')
def handle_terminal(cmd):
    """Safe command execution for web terminal"""
    allowed = ['ls', 'pwd', 'whoami', 'uname', 'date', 'uptime', 'ps', 'df', 'free', 'echo', 'cat', 'head', 'tail', 'wc', 'help', 'clear']
    try:
        parts = cmd.strip().split()
        if not parts:
            return
        base = parts[0]
        if base == 'help':
            emit('terminal_output', {'output': 'Available commands: ' + ', '.join(allowed), 'info': True})
        elif base == 'clear':
            emit('terminal_output', {'output': '__CLEAR__', 'info': True})
        elif base in allowed:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5, cwd='/tmp')
            output = (result.stdout + result.stderr).strip()
            emit('terminal_output', {'output': output.replace('\n', '<br>') or '(no output)', 'success': result.returncode == 0, 'error': result.returncode != 0})
        else:
            emit('terminal_output', {'output': f"Command '{base}' not allowed. Type 'help' for list.", 'error': True})
    except subprocess.TimeoutExpired:
        emit('terminal_output', {'output': 'Command timed out (5s limit)', 'error': True})
    except Exception as e:
        emit('terminal_output', {'output': str(e), 'error': True})

def emit_stats():
    last_net = psutil.net_io_counters()
    boot_time = psutil.boot_time()
    
    while True:
        gevent.sleep(1)  # ✅ True gevent sleep, doesn't block event loop
        try:
            net = psutil.net_io_counters()
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            uptime = time.time() - boot_time
            
            socketio.emit('stats', {
                'cpu': round(psutil.cpu_percent(), 1),
                'ram': round(ram.percent, 1),
                'ram_used': round(ram.used / (1024**3), 2),
                'ram_total': round(ram.total / (1024**3), 2),
                'net_down': round((net.bytes_recv - last_net.bytes_recv) / 1024, 1),
                'net_up': round((net.bytes_sent - last_net.bytes_sent) / 1024, 1),
                'disk': round(disk.percent, 1),
                'disk_used': round(disk.used / (1024**3), 2),
                'disk_total': round(disk.total / (1024**3), 2),
                'uptime': f"{int(uptime//3600)}h {int((uptime%3600)//60)}m",
                'cores': psutil.cpu_percent(percpu=True)
            })
            last_net = net
        except Exception as e:
            print(f"Stats error: {e}")
            gevent.sleep(1)

# ✅ Use gevent.spawn for true background greenlet
gevent.spawn(emit_stats)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)