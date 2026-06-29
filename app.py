#!/usr/bin/env python3
import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, render_template_string, send_file
from flask_socketio import SocketIO, emit
import psutil
import os
import subprocess
import time
import gevent
import platform
from datetime import datetime

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
        .icon-btn:hover, .icon-btn.active { 
            background: rgba(137, 180, 250, 0.2); 
            transform: translateY(-2px);
            border-color: #89b4fa;
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
            max-width: 1600px;
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
        .card h3 { margin-bottom: 15px; color: #89b4fa; font-size: 15px; display: flex; align-items: center; gap: 8px; }
        .card.full-width { grid-column: 1 / -1; }
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
        .process-list, .service-list, .log-content, .file-list {
            max-height: 350px;
            overflow-y: auto;
            font-size: 13px;
        }
        .process-item, .service-item, .file-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            transition: background 0.2s;
        }
        .process-item:hover, .service-item:hover, .file-item:hover { background: rgba(255,255,255,0.03); }
        .kill-btn, .service-btn {
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
        .service-btn { background: rgba(137, 180, 250, 0.3); }
        .service-btn.stop { background: rgba(255, 85, 85, 0.3); }
        .service-btn:hover, .kill-btn:hover { opacity: 1; transform: scale(1.05); }
        .status-badge {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .status-badge.active { background: rgba(166, 227, 161, 0.2); color: #a6e3a1; }
        .status-badge.inactive { background: rgba(243, 139, 168, 0.2); color: #f38ba8; }
        #conn-status { font-size: 12px; font-weight: 600; }
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
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
        }
        .info-item {
            background: rgba(255,255,255,0.03);
            padding: 10px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .info-label { font-size: 11px; color: #a6adc8; text-transform: uppercase; letter-spacing: 0.5px; }
        .info-value { font-size: 14px; color: #cdd6f4; font-weight: 600; margin-top: 4px; }
        .net-interface {
            background: rgba(255,255,255,0.03);
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 10px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .net-name { font-weight: 600; color: #89b4fa; margin-bottom: 5px; }
        .net-stats { display: flex; gap: 15px; font-size: 12px; color: #a6adc8; }
        .log-line { padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.02); font-family: monospace; font-size: 12px; }
        .log-time { color: #89b4fa; }
        .log-error { color: #f38ba8; }
        .log-warn { color: #f9e2af; }
        .hidden { display: none !important; }
        .tab-bar {
            display: flex;
            gap: 5px;
            margin-bottom: 15px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding-bottom: 10px;
        }
        .tab-btn {
            padding: 6px 14px;
            border-radius: 6px;
            border: none;
            background: transparent;
            color: #a6adc8;
            cursor: pointer;
            font-size: 13px;
            transition: 0.2s;
        }
        .tab-btn:hover { background: rgba(255,255,255,0.05); color: #cdd6f4; }
        .tab-btn.active { background: rgba(137, 180, 250, 0.15); color: #89b4fa; }
        .search-box {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 8px 12px;
            color: #cdd6f4;
            font-size: 13px;
            width: 100%;
            margin-bottom: 10px;
            outline: none;
        }
        .search-box:focus { border-color: #89b4fa; }
        .file-row {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 6px 0;
            cursor: pointer;
        }
        .file-row:hover { color: #89b4fa; }
        .file-icon { font-size: 16px; }
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.7);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            backdrop-filter: blur(5px);
        }
        .modal-overlay.show { display: flex; }
        .modal {
            background: #181825;
            border-radius: 16px;
            padding: 25px;
            max-width: 800px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .modal h3 { margin-bottom: 15px; color: #89b4fa; }
        .modal-close {
            float: right;
            background: none;
            border: none;
            color: #a6adc8;
            font-size: 20px;
            cursor: pointer;
        }
        .editor-textarea {
            width: 100%;
            min-height: 300px;
            background: #0c0c14;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 12px;
            color: #cdd6f4;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            resize: vertical;
            outline: none;
        }
        .editor-textarea:focus { border-color: #89b4fa; }
    </style>
</head>
<body>
    <div class="panel">
        <div class="icons">
            <button class="icon-btn active" onclick="switchTab('dashboard')" id="tab-btn-dashboard" title="Dashboard">🏠</button>
            <button class="icon-btn" onclick="switchTab('services')" id="tab-btn-services" title="Services">⚙️</button>
            <button class="icon-btn" onclick="switchTab('network')" id="tab-btn-network" title="Network">🌐</button>
            <button class="icon-btn" onclick="switchTab('files')" id="tab-btn-files" title="Files">📁</button>
            <button class="icon-btn" onclick="switchTab('logs')" id="tab-btn-logs" title="Logs">📋</button>
            <button class="icon-btn" onclick="switchTab('system')" id="tab-btn-system" title="System Info">💻</button>
            <button class="icon-btn" onclick="switchTab('terminal')" id="tab-btn-terminal" title="Terminal">🖥️</button>
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
    
    <div class="content" id="tab-dashboard">
        <div class="card">
            <h3>🔥 CPU Usage</h3>
            <div class="progress-bar"><div class="progress-fill" id="cpu-bar" style="width: 0%"></div></div>
            <div class="detail-text" id="cpu-cores">Waiting for data...</div>
        </div>
        <div class="card">
            <h3>💾 Memory Usage</h3>
            <div class="progress-bar"><div class="progress-fill" id="ram-bar" style="width: 0%"></div></div>
            <div class="detail-text" id="ram-details">Waiting for data...</div>
        </div>
        <div class="card">
            <h3>💿 Disk Usage</h3>
            <div class="progress-bar"><div class="progress-fill" id="disk-bar" style="width: 0%"></div></div>
            <div class="detail-text" id="disk-details">Waiting for data...</div>
        </div>
        <div class="card" id="process-card" style="display:none;">
            <h3>⚙️ Top Processes</h3>
            <div class="process-list" id="process-list"></div>
        </div>
    </div>

    <div class="content hidden" id="tab-services">
        <div class="card full-width">
            <h3>🔧 System Services</h3>
            <div class="tab-bar">
                <button class="tab-btn active" onclick="filterServices('all')">All</button>
                <button class="tab-btn" onclick="filterServices('active')">Active</button>
                <button class="tab-btn" onclick="filterServices('inactive')">Inactive</button>
            </div>
            <div class="service-list" id="service-list">Loading services...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-network">
        <div class="card">
            <h3>🌐 Network Interfaces</h3>
            <div id="network-interfaces">Loading...</div>
        </div>
        <div class="card">
            <h3>🔗 Active Connections</h3>
            <div class="process-list" id="connection-list">Loading...</div>
        </div>
        <div class="card">
            <h3>🔒 Open Ports</h3>
            <div class="process-list" id="port-list">Loading...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-files">
        <div class="card full-width">
            <h3>📁 File Manager</h3>
            <div style="display:flex; gap:10px; margin-bottom:10px;">
                <button class="btn" onclick="loadFiles('/tmp')">/tmp</button>
                <button class="btn" onclick="loadFiles('/home')">/home</button>
                <button class="btn" onclick="loadFiles('/var/log')">/var/log</button>
                <button class="btn" onclick="goBack()">⬅ Back</button>
            </div>
            <div class="file-list" id="file-list">Loading...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-logs">
        <div class="card full-width">
            <h3>📋 System Logs</h3>
            <input type="text" class="search-box" id="log-search" placeholder="Search logs..." onkeyup="searchLogs()">
            <div class="tab-bar">
                <button class="tab-btn active" onclick="loadLogs('syslog')">syslog</button>
                <button class="tab-btn" onclick="loadLogs('auth')">auth</button>
                <button class="tab-btn" onclick="loadLogs('kern')">kernel</button>
                <button class="tab-btn" onclick="loadLogs('dmesg')">dmesg</button>
            </div>
            <div class="log-content" id="log-content">Loading logs...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-system">
        <div class="card full-width">
            <h3>💻 System Information</h3>
            <div class="info-grid" id="system-info">Loading...</div>
        </div>
        <div class="card">
            <h3>🌡️ Sensors</h3>
            <div class="detail-text" id="sensors-info">Loading...</div>
        </div>
        <div class="card">
            <h3>🔋 Battery</h3>
            <div class="detail-text" id="battery-info">Loading...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-terminal">
        <div class="card full-width">
            <h3>🖥️ Bash Terminal</h3>
            <div class="terminal-window" id="terminal">
                <div class="terminal-line terminal-info">Linux-System Web Terminal v2.0</div>
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

    <div class="modal-overlay" id="file-modal">
        <div class="modal">
            <button class="modal-close" onclick="closeModal()">×</button>
            <h3>📝 File Editor</h3>
            <div id="file-path" style="color:#a6adc8; font-size:12px; margin-bottom:10px;"></div>
            <textarea class="editor-textarea" id="file-editor"></textarea>
            <div style="margin-top:15px; display:flex; gap:10px;">
                <button class="btn" style="background:rgba(166,227,161,0.2);color:#a6e3a1;" onclick="saveFile()">💾 Save</button>
                <button class="btn" style="background:rgba(243,139,168,0.2);color:#f38ba8;" onclick="closeModal()">Cancel</button>
            </div>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        const socket = io({ transports: ['websocket', 'polling'] });
        let currentPath = '/tmp';
        let currentFile = '';
        let servicesData = [];
        let logsData = [];
        
        function switchTab(tab) {
            document.querySelectorAll('.content').forEach(c => c.classList.add('hidden'));
            document.getElementById('tab-' + tab).classList.remove('hidden');
            document.querySelectorAll('.icon-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-btn-' + tab).classList.add('active');
            
            if (tab === 'services') loadServices();
            if (tab === 'network') loadNetwork();
            if (tab === 'files') loadFiles(currentPath);
            if (tab === 'logs') loadLogs('syslog');
            if (tab === 'system') loadSystemInfo();
        }
        
        socket.on('connect', () => {
            document.getElementById('conn-status').textContent = '● live';
            document.getElementById('conn-status').style.color = '#22c55e';
        });
        
        socket.on('disconnect', () => {
            document.getElementById('conn-status').textContent = '● offline';
            document.getElementById('conn-status').style.color = '#ef4444';
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
                        <button class="kill-btn" onclick="confirmKill(${p.pid}, '${p.name.replace(/'/g, "\\'")}')">Kill</button>
                    </div>
                `).join('');
            }
            document.getElementById('process-card').style.display = 'block';
        });
        
        socket.on('notification', (data) => alert(data.title + ': ' + data.body));
        
        function loadServices() {
            socket.emit('get_services');
        }
        socket.on('services', (data) => {
            servicesData = data;
            renderServices('all');
        });
        function renderServices(filter) {
            const list = document.getElementById('service-list');
            let filtered = servicesData;
            if (filter !== 'all') filtered = servicesData.filter(s => s.status === filter);
            
            list.innerHTML = filtered.map(s => `
                <div class="service-item">
                    <div>
                        <div style="font-weight:600;">${s.name}</div>
                        <div style="font-size:11px; color:#a6adc8;">${s.description || 'No description'}</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span class="status-badge ${s.status}">${s.status}</span>
                        <button class="service-btn ${s.status === 'active' ? 'stop' : ''}" 
                                onclick="toggleService('${s.name}', '${s.status === 'active' ? 'stop' : 'start'}')">
                            ${s.status === 'active' ? 'Stop' : 'Start'}
                        </button>
                        <button class="service-btn" onclick="toggleService('${s.name}', 'restart')">Restart</button>
                    </div>
                </div>
            `).join('');
        }
        function filterServices(f) {
            document.querySelectorAll('#tab-services .tab-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            renderServices(f);
        }
        function toggleService(name, action) {
            socket.emit('service_action', {name, action});
        }
        
        function loadNetwork() {
            socket.emit('get_network');
        }
        socket.on('network', (data) => {
            document.getElementById('network-interfaces').innerHTML = data.interfaces.map(i => `
                <div class="net-interface">
                    <div class="net-name">${i.name}</div>
                    <div class="net-stats">
                        <span>📥 ${i.bytes_recv} MB</span>
                        <span>📤 ${i.bytes_sent} MB</span>
                        <span>📦 ${i.packets_recv} pkts</span>
                        <span>❌ ${i.errin} errs</span>
                        <span>🗑️ ${i.dropin} drops</span>
                    </div>
                    <div class="detail-text" style="margin-top:5px;">IP: ${i.addresses.join(', ') || 'No IP'}</div>
                </div>
            `).join('');
            
            document.getElementById('connection-list').innerHTML = data.connections.slice(0, 20).map(c => `
                <div class="process-item">
                    <span>${c.status} | ${c.laddr} → ${c.raddr || 'N/A'} | PID: ${c.pid || 'N/A'}</span>
                </div>
            `).join('');
            
            document.getElementById('port-list').innerHTML = data.ports.map(p => `
                <div class="process-item">
                    <span>Port ${p.port} | ${p.protocol} | PID: ${p.pid} | ${p.name}</span>
                </div>
            `).join('');
        });
        
        function loadFiles(path) {
            currentPath = path;
            socket.emit('get_files', path);
        }
        function goBack() {
            const parts = currentPath.split('/').filter(Boolean);
            if (parts.length > 0) {
                parts.pop();
                loadFiles('/' + parts.join('/'));
            }
        }
        socket.on('files', (data) => {
            document.getElementById('file-list').innerHTML = 
                (data.parent ? `<div class="file-row" onclick="goBack()"><span class="file-icon">📁</span> ..</div>` : '') +
                data.items.map(f => `
                    <div class="file-row" onclick="${f.is_dir ? `loadFiles('${f.path}')` : `editFile('${f.path}')`}">
                        <span class="file-icon">${f.is_dir ? '📁' : '📄'}</span>
                        <span style="flex:1;">${f.name}</span>
                        <span style="color:#a6adc8; font-size:11px;">${f.size || ''}</span>
                    </div>
                `).join('');
        });
        function editFile(path) {
            currentFile = path;
            socket.emit('read_file', path);
        }
        socket.on('file_content', (data) => {
            document.getElementById('file-path').textContent = data.path;
            document.getElementById('file-editor').value = data.content;
            document.getElementById('file-modal').classList.add('show');
        });
        function closeModal() {
            document.getElementById('file-modal').classList.remove('show');
        }
        function saveFile() {
            socket.emit('write_file', {path: currentFile, content: document.getElementById('file-editor').value});
            closeModal();
        }
        
        function loadLogs(type) {
            document.querySelectorAll('#tab-logs .tab-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            socket.emit('get_logs', type);
        }
        function searchLogs() {
            const q = document.getElementById('log-search').value.toLowerCase();
            const lines = logsData.filter(l => l.toLowerCase().includes(q));
            renderLogs(lines);
        }
        function renderLogs(lines) {
            document.getElementById('log-content').innerHTML = lines.slice(-100).map(l => {
                let cls = '';
                if (l.includes('ERROR') || l.includes('error')) cls = 'log-error';
                else if (l.includes('WARN') || l.includes('warning')) cls = 'log-warn';
                return `<div class="log-line ${cls}">${escapeHtml(l)}</div>`;
            }).join('');
        }
        socket.on('logs', (data) => {
            logsData = data.lines;
            renderLogs(logsData);
        });
        
        function loadSystemInfo() {
            socket.emit('get_system_info');
        }
        socket.on('system_info', (data) => {
            document.getElementById('system-info').innerHTML = Object.entries(data).map(([k,v]) => `
                <div class="info-item">
                    <div class="info-label">${k}</div>
                    <div class="info-value">${v}</div>
                </div>
            `).join('');
            
            document.getElementById('sensors-info').innerHTML = data.sensors || 'No sensor data available';
            document.getElementById('battery-info').innerHTML = data.battery || 'No battery detected';
        });
        
        socket.on('terminal_output', (data) => {
            const term = document.getElementById('terminal');
            if (data.output === '__CLEAR__') { term.innerHTML = ''; return; }
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
            if (confirm(`Kill process ${name} (PID ${pid})?`)) socket.emit('kill_process', pid);
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

@app.route('/download/<path:filepath>')
def download_file(filepath):
    try:
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return str(e), 404

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

@socketio.on('get_services')
def handle_services():
    try:
        result = subprocess.run(['systemctl', 'list-units', '--type=service', '--no-pager', '--no-legend', '-a'], 
                              capture_output=True, text=True, timeout=10)
        services = []
        for line in result.stdout.strip().split('\n')[:50]:
            parts = line.split()
            if len(parts) >= 4:
                name = parts[0]
                status = 'active' if parts[3] == 'running' else 'inactive'
                desc = ' '.join(parts[4:]) if len(parts) > 4 else 'No description'
                services.append({'name': name, 'status': status, 'description': desc})
        emit('services', services)
    except Exception as e:
        emit('services', [{'name': 'Error', 'status': 'inactive', 'description': str(e)}])

@socketio.on('service_action')
def handle_service_action(data):
    try:
        action = data['action']
        name = data['name']
        result = subprocess.run(['sudo', 'systemctl', action, name], 
                              capture_output=True, text=True, timeout=10)
        emit('notification', {
            'title': f'Service {action}', 
            'body': f'{name}: {result.stdout or result.stderr or "Done"}'
        })
        handle_services()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('get_network')
def handle_network():
    try:
        interfaces = []
        io_counters = psutil.net_io_counters(pernic=True)
        addrs = psutil.net_if_addrs()
        
        for name, io in io_counters.items():
            addr_list = [a.address for a in addrs.get(name, []) if a.family == 2]
            interfaces.append({
                'name': name,
                'bytes_recv': round(io.bytes_recv / (1024*1024), 2),
                'bytes_sent': round(io.bytes_sent / (1024*1024), 2),
                'packets_recv': io.packets_recv,
                'errin': io.errin,
                'dropin': io.dropin,
                'addresses': addr_list
            })
        
        connections = []
        for conn in psutil.net_connections(kind='inet')[:30]:
            try:
                connections.append({
                    'status': conn.status,
                    'laddr': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else 'N/A',
                    'raddr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                    'pid': conn.pid
                })
            except:
                pass
        
        ports = []
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == 'LISTEN' and conn.laddr:
                try:
                    proc = psutil.Process(conn.pid) if conn.pid else None
                    ports.append({
                        'port': conn.laddr.port,
                        'protocol': 'TCP',
                        'pid': conn.pid or 'N/A',
                        'name': proc.name() if proc else 'Unknown'
                    })
                except:
                    pass
        
        emit('network', {
            'interfaces': interfaces,
            'connections': connections,
            'ports': list({p['port']: p for p in ports}.values())[:20]
        })
    except Exception as e:
        emit('network', {'interfaces': [], 'connections': [], 'ports': [], 'error': str(e)})

@socketio.on('get_files')
def handle_files(path):
    try:
        items = []
        parent = os.path.dirname(path) if path != '/' else None
        for entry in os.scandir(path):
            try:
                stat = entry.stat()
                size = ''
                if not entry.is_dir():
                    s = stat.st_size
                    if s < 1024: size = f'{s} B'
                    elif s < 1024*1024: size = f'{s/1024:.1f} KB'
                    else: size = f'{s/(1024*1024):.1f} MB'
                
                items.append({
                    'name': entry.name,
                    'path': entry.path,
                    'is_dir': entry.is_dir(),
                    'size': size
                })
            except PermissionError:
                continue
        
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        emit('files', {'items': items, 'parent': parent})
    except Exception as e:
        emit('files', {'items': [{'name': f'Error: {e}', 'path': '', 'is_dir': False, 'size': ''}], 'parent': None})

@socketio.on('read_file')
def handle_read_file(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(50000)
        emit('file_content', {'path': path, 'content': content})
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': f'Cannot read file: {e}'})

@socketio.on('write_file')
def handle_write_file(data):
    try:
        with open(data['path'], 'w', encoding='utf-8') as f:
            f.write(data['content'])
        emit('notification', {'title': 'Saved', 'body': f'File saved: {data["path"]}'})
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': f'Cannot save file: {e}'})

@socketio.on('get_logs')
def handle_logs(log_type):
    try:
        commands = {
            'syslog': ['tail', '-n', '100', '/var/log/syslog'] if os.path.exists('/var/log/syslog') else ['journalctl', '-n', '100', '--no-pager'],
            'auth': ['tail', '-n', '100', '/var/log/auth.log'] if os.path.exists('/var/log/auth.log') else ['journalctl', '-n', '100', '--no-pager', '-u', 'systemd-logind'],
            'kern': ['journalctl', '-n', '100', '--no-pager', '-k'],
            'dmesg': ['dmesg', '-T']
        }
        
        cmd = commands.get(log_type, commands['syslog'])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        lines = (result.stdout + result.stderr).strip().split('\n')
        emit('logs', {'lines': lines[-100:]})
    except Exception as e:
        emit('logs', {'lines': [f'Error reading logs: {e}']})

@socketio.on('get_system_info')
def handle_system_info():
    try:
        boot_time = psutil.boot_time()
        uptime = time.time() - boot_time
        
        sensors = 'No sensors available'
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                sensors = '<br>'.join([f"{k}: {v[0].current}°C" for k, v in temps.items()])
        except:
            pass
        
        battery = 'No battery'
        try:
            bat = psutil.sensors_battery()
            if bat:
                battery = f"{bat.percent}% {'(Charging)' if bat.power_plugged else '(Discharging)'}"
        except:
            pass
        
        info = {
            'Hostname': platform.node(),
            'OS': f"{platform.system()} {platform.release()}",
            'Kernel': platform.version(),
            'Architecture': platform.machine(),
            'Processor': platform.processor() or 'Unknown',
            'CPU Cores': f"{psutil.cpu_count(logical=False)} physical / {psutil.cpu_count()} logical",
            'Total RAM': f"{round(psutil.virtual_memory().total / (1024**3), 2)} GB",
            'Uptime': f"{int(uptime//3600)}h {int((uptime%3600)//60)}m",
            'Python': platform.python_version(),
            'Boot Time': datetime.fromtimestamp(boot_time).strftime('%Y-%m-%d %H:%M:%S'),
            'sensors': sensors,
            'battery': battery
        }
        emit('system_info', info)
    except Exception as e:
        emit('system_info', {'Error': str(e)})

@socketio.on('terminal_command')
def handle_terminal(cmd):
    allowed = ['ls', 'pwd', 'whoami', 'uname', 'date', 'uptime', 'ps', 'df', 'free', 'echo', 'cat', 'head', 'tail', 'wc', 'help', 'clear', 'mkdir', 'touch', 'rm', 'cp', 'mv', 'find', 'grep', 'awk', 'sed', 'sort', 'uniq', 'curl', 'wget', 'ping', 'netstat', 'ss', 'ip', 'ifconfig', 'route', 'traceroute', 'nslookup', 'dig', 'top', 'htop', 'vmstat', 'iostat', 'mpstat', 'sar', 'lsof', 'fuser', 'killall', 'pkill', 'pgrep', 'nice', 'renice', 'chown', 'chmod', 'stat', 'file', 'md5sum', 'sha256sum', 'base64', 'tar', 'gzip', 'gunzip', 'zip', 'unzip', 'rsync', 'scp', 'ssh', 'git', 'python3', 'python', 'pip', 'node', 'npm', 'npx', 'yarn', 'docker', 'docker-compose', 'kubectl', 'helm', 'terraform', 'ansible', 'vagrant', 'make', 'gcc', 'g++', 'go', 'rustc', 'javac', 'java', 'mvn', 'gradle', 'bundle', 'gem', 'ruby', 'perl', 'php', 'composer', 'lua', 'tcl', 'sqlite3', 'mysql', 'psql', 'mongo', 'redis-cli', 'memcached', 'nginx', 'apache2', 'httpd', 'systemctl', 'service', 'journalctl', 'dmesg', 'sysctl', 'modprobe', 'lsmod', 'insmod', 'rmmod', 'depmod', 'update-rc.d', 'chkconfig', 'crontab', 'at', 'batch', 'sleep', 'watch', 'timeout', 'nohup', 'disown', 'jobs', 'fg', 'bg', 'kill', 'xargs', 'parallel', 'tee', 'script', 'screen', 'tmux', 'expect', 'ssh-keygen', 'ssh-agent', 'ssh-add', 'sftp', 'ftp', 'smbclient', 'mount', 'umount', 'fdisk', 'parted', 'mkfs', 'fsck', 'blkid', 'lsblk', 'ncdu', 'tree', 'locate', 'updatedb', 'which', 'whereis', 'type', 'alias', 'export', 'source', 'eval', 'exec', 'bash', 'sh', 'zsh', 'fish', 'csh', 'tcsh', 'dash', 'ksh', 'mksh', 'yash', 'busybox', 'env', 'printenv', 'set', 'unset', 'readonly', 'declare', 'typeset', 'local', 'function', 'return', 'exit', 'true', 'false', 'test', '[', '[[', ']]', ']', 'echo', 'printf', 'read', 'readarray', 'mapfile', 'select', 'case', 'esac', 'if', 'then', 'else', 'elif', 'fi', 'for', 'while', 'until', 'do', 'done', 'in', 'break', 'continue', 'shift', 'getopts', 'source', '.', 'trap', 'wait', 'caller', 'command', 'builtin', 'enable', 'disable', 'help', 'history', 'fc', 'bg', 'fg', 'jobs', 'disown', 'suspend', 'kill', 'wait', 'umask', 'ulimit', 'times', 'pwd', 'cd', 'pushd', 'popd', 'dirs', 'echo', 'printf', 'read', 'readonly', 'set', 'shift', 'shopt', 'source', 'suspend', 'test', 'time', 'times', 'trap', 'true', 'type', 'typeset', 'ulimit', 'umask', 'unalias', 'unset', 'alias', 'bind', 'builtin', 'caller', 'command', 'declare', 'echo', 'enable', 'eval', 'exec', 'exit', 'export', 'false', 'fc', 'fg', 'getopts', 'hash', 'help', 'history', 'jobs', 'kill', 'let', 'local', 'logout', 'mapfile', 'popd', 'printf', 'pushd', 'pwd', 'read', 'readarray', 'readonly', 'return', 'set', 'shift', 'shopt', 'source', 'suspend', 'test', 'time', 'times', 'trap', 'true', 'type', 'typeset', 'ulimit', 'umask', 'unalias', 'unset', 'wait']
    try:
        parts = cmd.strip().split()
        if not parts:
            return
        base = parts[0]
        if base == 'help':
            emit('terminal_output', {'output': 'Available commands: ' + ', '.join(allowed[:50]) + '... (and more)', 'info': True})
        elif base == 'clear':
            emit('terminal_output', {'output': '__CLEAR__', 'info': True})
        elif base in allowed or any(cmd.startswith(a) for a in allowed):
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10, cwd='/tmp')
            output = (result.stdout + result.stderr).strip()
            emit('terminal_output', {'output': output.replace('\n', '<br>') or '(no output)', 'success': result.returncode == 0, 'error': result.returncode != 0})
        else:
            emit('terminal_output', {'output': f"Command '{base}' not allowed. Type 'help' for list.", 'error': True})
    except subprocess.TimeoutExpired:
        emit('terminal_output', {'output': 'Command timed out (10s limit)', 'error': True})
    except Exception as e:
        emit('terminal_output', {'output': str(e), 'error': True})

def emit_stats():
    last_net = psutil.net_io_counters()
    boot_time = psutil.boot_time()
    
    while True:
        gevent.sleep(1)
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

gevent.spawn(emit_stats)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
