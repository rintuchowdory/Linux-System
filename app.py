#!/usr/bin/env python3
from flask import Flask, render_template_string
from flask_socketio import SocketIO
import psutil
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Linux-System Dashboard</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #1e1e2e;
            color: #cdd6f4;
            font-family: 'Segoe UI', Ubuntu, sans-serif;
            min-height: 100vh;
        }
        .panel {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 15px 30px;
            background: #181825;
            border-bottom: 2px solid #313244;
        }
        .icons { display: flex; gap: 15px; }
        .icon-btn {
            width: 40px; height: 40px;
            border-radius: 10px;
            background: #313244;
            border: none;
            color: #cdd6f4;
            font-size: 18px;
            cursor: pointer;
            transition: 0.3s;
        }
        .icon-btn:hover { background: #89b4fa; color: #1e1e2e; }
        .stats { display: flex; gap: 25px; font-size: 14px; }
        .stat { display: flex; align-items: center; gap: 8px; }
        .stat-value { color: #89b4fa; font-weight: bold; }
        .actions { display: flex; gap: 10px; }
        .btn {
            padding: 8px 16px;
            border-radius: 8px;
            border: none;
            background: #313244;
            color: #cdd6f4;
            cursor: pointer;
            font-size: 13px;
        }
        .btn:hover { background: #89b4fa; color: #1e1e2e; }
        .btn.record { background: #ff5555; }
        .content {
            padding: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background: #181825;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }
        .card h3 { margin-bottom: 15px; color: #89b4fa; }
        .progress-bar {
            width: 100%; height: 20px;
            background: #313244;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #89b4fa, #b4befe);
            border-radius: 10px;
            transition: width 0.5s;
        }
        .process-list {
            max-height: 400px;
            overflow-y: auto;
        }
        .process-item {
            display: flex;
            justify-content: space-between;
            padding: 8px;
            border-bottom: 1px solid #313244;
            font-size: 13px;
        }
        .kill-btn {
            background: #ff5555;
            border: none;
            padding: 4px 12px;
            border-radius: 6px;
            color: white;
            cursor: pointer;
        }
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
            <div class="stat">CPU: <span class="stat-value" id="cpu">--%</span></div>
            <div class="stat">RAM: <span class="stat-value" id="ram">--%</span></div>
            <div class="stat">↓<span id="net-down">--</span> ↑<span id="net-up">--</span> KB/s</div>
            <div class="stat">Disk: <span class="stat-value" id="disk">--%</span></div>
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
            <div id="cpu-cores"></div>
        </div>
        <div class="card">
            <h3>Memory Usage</h3>
            <div class="progress-bar"><div class="progress-fill" id="ram-bar" style="width: 0%"></div></div>
            <div id="ram-details"></div>
        </div>
        <div class="card">
            <h3>Disk Usage</h3>
            <div class="progress-bar"><div class="progress-fill" id="disk-bar" style="width: 0%"></div></div>
            <div id="disk-details"></div>
        </div>
        <div class="card" id="process-card" style="display:none;">
            <h3>Top Processes</h3>
            <div class="process-list" id="process-list"></div>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        const socket = io();
        
        socket.on('stats', (data) => {
            document.getElementById('cpu').textContent = data.cpu + '%';
            document.getElementById('ram').textContent = data.ram + '%';
            document.getElementById('net-down').textContent = data.net_down;
            document.getElementById('net-up').textContent = data.net_up;
            document.getElementById('disk').textContent = data.disk + '%';
            document.getElementById('uptime').textContent = data.uptime;
            
            document.getElementById('cpu-bar').style.width = data.cpu + '%';
            document.getElementById('ram-bar').style.width = data.ram + '%';
            document.getElementById('disk-bar').style.width = data.disk + '%';
            
            document.getElementById('cpu-cores').innerHTML = data.cores.map((c,i) => 
                `Core ${i}: ${c}%`).join('<br>');
            document.getElementById('ram-details').innerHTML = 
                `Used: ${data.ram_used}GB / Total: ${data.ram_total}GB`;
            document.getElementById('disk-details').innerHTML = 
                `Used: ${data.disk_used}GB / Total: ${data.disk_total}GB`;
        });
        
        socket.on('processes', (data) => {
            const list = document.getElementById('process-list');
            list.innerHTML = data.map(p => `
                <div class="process-item">
                    <span>PID ${p.pid} | ${p.name} | CPU ${p.cpu}% | MEM ${p.mem}%</span>
                    <button class="kill-btn" onclick="killProcess(${p.pid})">Kill</button>
                </div>
            `).join('');
            document.getElementById('process-card').style.display = 'block';
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
        
        function killProcess(pid) {
            socket.emit('kill_process', pid);
        }
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
    socketio.emit('processes', processes[:20])

@socketio.on('kill_process')
def handle_kill(pid):
    try:
        import os
        os.kill(int(pid), 15)
        socketio.emit('notification', {'title': 'Killed', 'body': f'PID {pid} terminated'})
    except Exception as e:
        socketio.emit('notification', {'title': 'Error', 'body': str(e)})

def emit_stats():
    last_net = psutil.net_io_counters()
    boot_time = psutil.boot_time()
    
    while True:
        time.sleep(1)
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

if __name__ == '__main__':
    threading.Thread(target=emit_stats, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
