
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
from datetime import datetime, timedelta
import hashlib
import re
import threading
import json

# In-memory storage for features that need persistence
task_scheduler_db = []
backup_jobs = []
package_cache = {}


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
        body { background: #0f0f1a; color: #cdd6f4; font-family: 'Segoe UI', Ubuntu, sans-serif; min-height: 100vh; }
        body::before { content: ''; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: radial-gradient(ellipse at 20% 50%, rgba(120, 40, 180, 0.4) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(255, 100, 50, 0.3) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 80%, rgba(40, 100, 255, 0.3) 0%, transparent 50%);
            z-index: -1; pointer-events: none; }
        .panel { display: flex; align-items: center; justify-content: space-between; padding: 12px 25px;
            background: rgba(24, 24, 37, 0.85); backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255,255,255,0.05); flex-wrap: wrap; gap: 10px;
            position: sticky; top: 0; z-index: 100; }
        .icons { display: flex; gap: 12px; flex-wrap: wrap; }
        .icon-btn { width: 42px; height: 42px; border-radius: 12px; background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08); color: #fff; font-size: 20px; cursor: pointer;
            transition: all 0.3s; display: flex; align-items: center; justify-content: center; }
        .icon-btn:hover, .icon-btn.active { background: rgba(137, 180, 250, 0.2); transform: translateY(-2px); border-color: #89b4fa; }
        .stats { display: flex; gap: 20px; font-size: 13px; align-items: center; flex-wrap: wrap; }
        .stat { display: flex; align-items: center; gap: 6px; }
        .stat-value { color: #89b4fa; font-weight: 600; }
        .actions { display: flex; gap: 10px; flex-wrap: wrap; }
        .btn { padding: 8px 16px; border-radius: 8px; border: none; background: rgba(255,255,255,0.06);
            color: #cdd6f4; cursor: pointer; font-size: 13px; transition: 0.2s;
            border: 1px solid rgba(255,255,255,0.08); }
        .btn:hover { background: rgba(137, 180, 250, 0.2); }
        .btn.record { background: rgba(255, 85, 85, 0.8); color: white; }
        .btn.success { background: rgba(166, 227, 161, 0.2); color: #a6e3a1; }
        .btn.danger { background: rgba(243, 139, 168, 0.2); color: #f38ba8; }
        .content { padding: 25px; display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px; max-width: 1600px; margin: 0 auto; }
        .card { background: rgba(24, 24, 37, 0.7); backdrop-filter: blur(10px); border-radius: 16px;
            padding: 20px; border: 1px solid rgba(255,255,255,0.06); transition: transform 0.3s; }
        .card:hover { transform: translateY(-2px); }
        .card h3 { margin-bottom: 15px; color: #89b4fa; font-size: 15px; display: flex; align-items: center; gap: 8px; }
        .card.full-width { grid-column: 1 / -1; }
        .progress-bar { width: 100%; height: 22px; background: rgba(255,255,255,0.05);
            border-radius: 11px; overflow: hidden; margin: 10px 0; border: 1px solid rgba(255,255,255,0.05); }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #89b4fa, #b4befe);
            border-radius: 11px; transition: width 0.5s ease, background 0.3s ease;
            box-shadow: 0 0 10px rgba(137,180,250,0.3); }
        .progress-fill.warning { background: linear-gradient(90deg, #f9e2af, #fab387) !important;
            box-shadow: 0 0 10px rgba(249,226,175,0.3); }
        .progress-fill.danger { background: linear-gradient(90deg, #f38ba8, #ff5555) !important;
            box-shadow: 0 0 10px rgba(243,139,168,0.3); }
        .detail-text { font-size: 12px; color: #a6adc8; margin-top: 8px; line-height: 1.6; }
        .process-list, .service-list, .log-content, .file-list, .cron-list, .docker-list, .firewall-list, .ssh-list, .task-list {
            max-height: 350px; overflow-y: auto; font-size: 13px; }
        .process-item, .service-item, .file-item, .cron-item, .docker-item, .firewall-item, .ssh-item, .task-item {
            display: flex; justify-content: space-between; align-items: center; padding: 8px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.04); transition: background 0.2s; }
        .process-item:hover, .service-item:hover, .file-item:hover, .cron-item:hover, .docker-item:hover, .firewall-item:hover, .ssh-item:hover, .task-item:hover { background: rgba(255,255,255,0.03); }
        .kill-btn, .service-btn, .docker-btn, .cron-btn, .task-btn, .ssh-btn {
            background: rgba(255, 85, 85, 0.8); border: none; padding: 4px 12px; border-radius: 6px;
            color: white; cursor: pointer; font-size: 12px; opacity: 0.8; transition: 0.2s; }
        .service-btn, .docker-btn, .cron-btn, .task-btn { background: rgba(137, 180, 250, 0.3); }
        .service-btn.stop, .docker-btn.stop { background: rgba(255, 85, 85, 0.3); }
        .service-btn:hover, .kill-btn:hover, .docker-btn:hover, .cron-btn:hover, .task-btn:hover, .ssh-btn:hover { opacity: 1; transform: scale(1.05); }
        .status-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .status-badge.active, .status-badge.running { background: rgba(166, 227, 161, 0.2); color: #a6e3a1; }
        .status-badge.inactive, .status-badge.exited, .status-badge.dead { background: rgba(243, 139, 168, 0.2); color: #f38ba8; }
        .status-badge.paused { background: rgba(249, 226, 175, 0.2); color: #f9e2af; }
        #conn-status { font-size: 12px; font-weight: 600; }
        .terminal-window { background: #0c0c14; border-radius: 12px; padding: 15px;
            border: 1px solid rgba(255,255,255,0.08); font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
            font-size: 13px; color: #cdd6f4; min-height: 250px; max-height: 400px; overflow-y: auto; line-height: 1.5; }
        .terminal-input-line { display: flex; align-items: center; gap: 8px; margin-top: 5px; }
        .terminal-prompt { color: #89b4fa; font-weight: 600; white-space: nowrap; }
        .terminal-input { background: transparent; border: none; color: #cdd6f4; font-family: inherit;
            font-size: 13px; flex: 1; outline: none; }
        .terminal-line { margin: 1px 0; }
        .terminal-error { color: #f38ba8; }
        .terminal-success { color: #a6e3a1; }
        .terminal-info { color: #f9e2af; }
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
        .info-item { background: rgba(255,255,255,0.03); padding: 10px; border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.05); }
        .info-label { font-size: 11px; color: #a6adc8; text-transform: uppercase; letter-spacing: 0.5px; }
        .info-value { font-size: 14px; color: #cdd6f4; font-weight: 600; margin-top: 4px; }
        .net-interface { background: rgba(255,255,255,0.03); padding: 12px; border-radius: 10px;
            margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.05); }
        .net-name { font-weight: 600; color: #89b4fa; margin-bottom: 5px; }
        .net-stats { display: flex; gap: 15px; font-size: 12px; color: #a6adc8; flex-wrap: wrap; }
        .log-line { padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.02); font-family: monospace; font-size: 12px; }
        .log-time { color: #89b4fa; }
        .log-error { color: #f38ba8; }
        .log-warn { color: #f9e2af; }
        .hidden { display: none !important; }
        .tab-bar { display: flex; gap: 5px; margin-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.08);
            padding-bottom: 10px; flex-wrap: wrap; }
        .tab-btn { padding: 6px 14px; border-radius: 6px; border: none; background: transparent;
            color: #a6adc8; cursor: pointer; font-size: 13px; transition: 0.2s; }
        .tab-btn:hover { background: rgba(255,255,255,0.05); color: #cdd6f4; }
        .tab-btn.active { background: rgba(137, 180, 250, 0.15); color: #89b4fa; }
        .search-box { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px; padding: 8px 12px; color: #cdd6f4; font-size: 13px; width: 100%;
            margin-bottom: 10px; outline: none; }
        .search-box:focus { border-color: #89b4fa; }
        .file-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; cursor: pointer; }
        .file-row:hover { color: #89b4fa; }
        .file-icon { font-size: 16px; }
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7);
            display: none; align-items: center; justify-content: center; z-index: 1000; backdrop-filter: blur(5px); }
        .modal-overlay.show { display: flex; }
        .modal { background: #181825; border-radius: 16px; padding: 25px; max-width: 800px; width: 90%;
            max-height: 80vh; overflow-y: auto; border: 1px solid rgba(255,255,255,0.08); }
        .modal h3 { margin-bottom: 15px; color: #89b4fa; }
        .modal-close { float: right; background: none; border: none; color: #a6adc8; font-size: 20px; cursor: pointer; }
        .editor-textarea { width: 100%; min-height: 300px; background: #0c0c14;
            border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 12px; color: #cdd6f4;
            font-family: 'JetBrains Mono', monospace; font-size: 13px; resize: vertical; outline: none; }
        .editor-textarea:focus { border-color: #89b4fa; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; font-size: 12px; color: #a6adc8; margin-bottom: 5px; text-transform: uppercase; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 8px 12px; color: #cdd6f4;
            font-size: 13px; outline: none; }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color: #89b4fa; }
        .docker-stats { display: flex; gap: 15px; margin-bottom: 15px; flex-wrap: wrap; }
        .docker-stat { background: rgba(255,255,255,0.03); padding: 10px 15px; border-radius: 8px; }
        .docker-stat-label { font-size: 11px; color: #a6adc8; }
        .docker-stat-value { font-size: 18px; color: #89b4fa; font-weight: 600; }
        .empty-state { text-align: center; padding: 40px; color: #a6adc8; }
        .empty-state-icon { font-size: 48px; margin-bottom: 10px; }
    .theme-toggle { position: fixed; bottom: 20px; right: 20px; z-index: 1000; }
        .theme-btn { width: 50px; height: 50px; border-radius: 50%; border: none; 
            background: rgba(137, 180, 250, 0.2); color: #89b4fa; font-size: 24px; 
            cursor: pointer; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
        .htop-row { display: grid; grid-template-columns: 60px 1fr 80px 80px 80px 80px 100px; 
            gap: 8px; padding: 4px 10px; font-size: 12px; font-family: monospace; }
        .htop-header { background: rgba(137,180,250,0.1); font-weight: 600; color: #89b4fa; }
        .htop-row:hover { background: rgba(255,255,255,0.03); }
        .gpu-card { background: rgba(24,24,37,0.7); border-radius: 12px; padding: 15px; 
            border: 1px solid rgba(255,255,255,0.06); }
        .gpu-name { color: #89b4fa; font-weight: 600; margin-bottom: 8px; }
        .gpu-stat { display: flex; justify-content: space-between; font-size: 12px; margin: 4px 0; }
        .speed-result { background: rgba(137,180,250,0.1); padding: 15px; border-radius: 8px; 
            margin: 10px 0; text-align: center; }
        .speed-value { font-size: 32px; color: #89b4fa; font-weight: 700; }
        .db-table { width: 100%; border-collapse: collapse; font-size: 12px; }
        .db-table th { background: rgba(137,180,250,0.15); padding: 8px; text-align: left; color: #89b4fa; }
        .db-table td { padding: 6px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); }
        .db-table tr:hover { background: rgba(255,255,255,0.02); }
        .cert-item { display: flex; justify-content: space-between; align-items: center; 
            padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; margin: 5px 0; }
        .cert-valid { color: #a6e3a1; }
        .cert-expiring { color: #f9e2af; }
        .cert-expired { color: #f38ba8; }
        .backup-item { padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; margin: 5px 0; }
        .lang-select { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); 
            border-radius: 6px; padding: 4px 8px; color: #cdd6f4; font-size: 12px; }
        .mobile-panel { display: none; }
        @media (max-width: 768px) {
            .panel { flex-direction: column; align-items: stretch; }
            .icons { justify-content: center; }
            .stats { justify-content: center; }
            .actions { justify-content: center; }
            .content { grid-template-columns: 1fr; padding: 15px; }
            .htop-row { grid-template-columns: 40px 1fr 60px 60px 60px 60px 80px; font-size: 10px; }
        }
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
            <button class="icon-btn" onclick="switchTab('firewall')" id="tab-btn-firewall" title="Firewall">🔥</button>
            <button class="icon-btn" onclick="switchTab('cron')" id="tab-btn-cron" title="Cron Manager">⏰</button>
            <button class="icon-btn" onclick="switchTab('docker')" id="tab-btn-docker" title="Docker">🐳</button>
            <button class="icon-btn" onclick="switchTab('ssh')" id="tab-btn-ssh" title="SSH Keys">🔑</button>
            <button class="icon-btn" onclick="switchTab('tasks')" id="tab-btn-tasks" title="Task Scheduler">📅</button>
            <button class="icon-btn" onclick="switchTab('htop')" id="tab-btn-htop" title="Process Tree">📊</button>
            <button class="icon-btn" onclick="switchTab('gpu')" id="tab-btn-gpu" title="GPU Monitor">🎮</button>
            <button class="icon-btn" onclick="switchTab('packages')" id="tab-btn-packages" title="Packages">📦</button>
            <button class="icon-btn" onclick="switchTab('backup')" id="tab-btn-backup" title="Backups">💾</button>
            <button class="icon-btn" onclick="switchTab('speedtest')" id="tab-btn-speedtest" title="Speed Test">🚀</button>
            <button class="icon-btn" onclick="switchTab('certs')" id="tab-btn-certs" title="SSL Certs">🔐</button>
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
            <div style="display:flex; gap:10px; margin-bottom:10px; flex-wrap:wrap;">
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

    <div class="content hidden" id="tab-firewall">
        <div class="card full-width">
            <h3>🔥 Firewall Rules</h3>
            <div class="tab-bar">
                <button class="tab-btn active" onclick="loadFirewall('iptables')">iptables</button>
                <button class="tab-btn" onclick="loadFirewall('nftables')">nftables</button>
                <button class="tab-btn" onclick="loadFirewall('ufw')">UFW</button>
            </div>
            <div class="firewall-list" id="firewall-list">Loading firewall rules...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-cron">
        <div class="card full-width">
            <h3>⏰ Cron Manager</h3>
            <div style="display:flex; gap:10px; margin-bottom:15px; flex-wrap:wrap;">
                <button class="btn success" onclick="showAddCron()">+ Add Cron Job</button>
                <button class="btn" onclick="loadCron()">🔄 Refresh</button>
            </div>
            <div class="cron-list" id="cron-list">Loading cron jobs...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-docker">
        <div class="card full-width">
            <h3>🐳 Docker Monitor</h3>
            <div class="docker-stats" id="docker-stats">
                <div class="docker-stat"><div class="docker-stat-label">Containers</div><div class="docker-stat-value" id="docker-total">--</div></div>
                <div class="docker-stat"><div class="docker-stat-label">Running</div><div class="docker-stat-value" id="docker-running">--</div></div>
                <div class="docker-stat"><div class="docker-stat-label">Stopped</div><div class="docker-stat-value" id="docker-stopped">--</div></div>
                <div class="docker-stat"><div class="docker-stat-label">Images</div><div class="docker-stat-value" id="docker-images">--</div></div>
            </div>
            <div class="tab-bar">
                <button class="tab-btn active" onclick="filterDocker('all')">All</button>
                <button class="tab-btn" onclick="filterDocker('running')">Running</button>
                <button class="tab-btn" onclick="filterDocker('exited')">Stopped</button>
            </div>
            <div class="docker-list" id="docker-list">Loading containers...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-ssh">
        <div class="card full-width">
            <h3>🔑 SSH Key Manager</h3>
            <div style="display:flex; gap:10px; margin-bottom:15px; flex-wrap:wrap;">
                <button class="btn success" onclick="showGenerateKey()">+ Generate Key</button>
                <button class="btn" onclick="loadSSHKeys()">🔄 Refresh</button>
            </div>
            <div class="ssh-list" id="ssh-list">Loading SSH keys...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-tasks">
        <div class="card full-width">
            <h3>📅 Task Scheduler</h3>
            <div style="display:flex; gap:10px; margin-bottom:15px; flex-wrap:wrap;">
                <button class="btn success" onclick="showAddTask()">+ Schedule Task</button>
                <button class="btn" onclick="loadTasks()">🔄 Refresh</button>
            </div>
            <div class="task-list" id="task-list">Loading scheduled tasks...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-htop">
        <div class="card full-width">
            <h3>📊 Interactive Process Viewer (htop-style)</h3>
            <div style="display:flex; gap:10px; margin-bottom:15px; flex-wrap:wrap;">
                <button class="btn" onclick="loadHtop()">🔄 Refresh</button>
                <button class="btn" onclick="htopSort('cpu')">Sort by CPU</button>
                <button class="btn" onclick="htopSort('mem')">Sort by MEM</button>
                <button class="btn" onclick="htopSort('pid')">Sort by PID</button>
                <input type="text" class="search-box" id="htop-search" placeholder="Filter processes..." onkeyup="filterHtop()" style="width:auto; flex:1; min-width:200px;">
            </div>
            <div class="htop-header htop-row">
                <span>PID</span><span>COMMAND</span><span>CPU%</span><span>MEM%</span><span>RES</span><span>TIME</span><span>USER</span>
            </div>
            <div id="htop-list">Loading processes...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-gpu">
        <div class="card full-width">
            <h3>🎮 GPU Monitor</h3>
            <div id="gpu-content">Loading GPU info...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-packages">
        <div class="card full-width">
            <h3>📦 Package Manager</h3>
            <div style="display:flex; gap:10px; margin-bottom:15px; flex-wrap:wrap;">
                <button class="btn" onclick="loadPackages()">🔄 Refresh</button>
                <button class="btn" onclick="checkUpdates()">🔍 Check Updates</button>
                <button class="btn success" onclick="upgradeAll()">⬆️ Upgrade All</button>
            </div>
            <div class="tab-bar">
                <button class="tab-btn active" onclick="filterPackages('installed')">Installed</button>
                <button class="tab-btn" onclick="filterPackages('upgradable')">Upgradable</button>
            </div>
            <div id="package-list">Loading packages...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-backup">
        <div class="card full-width">
            <h3>💾 Backup Manager</h3>
            <div style="display:flex; gap:10px; margin-bottom:15px; flex-wrap:wrap;">
                <button class="btn success" onclick="showAddBackup()">+ New Backup Job</button>
                <button class="btn" onclick="loadBackups()">🔄 Refresh</button>
            </div>
            <div id="backup-list">Loading backup jobs...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-speedtest">
        <div class="card full-width">
            <h3>🚀 Network Speed Test</h3>
            <div style="text-align:center; padding:20px;">
                <button class="btn success" style="font-size:16px; padding:12px 30px;" onclick="runSpeedtest()">▶ Run Speed Test</button>
                <div id="speedtest-result" style="margin-top:20px;"></div>
            </div>
        </div>
    </div>

    <div class="content hidden" id="tab-certs">
        <div class="card full-width">
            <h3>🔐 SSL Certificate Manager</h3>
            <div style="display:flex; gap:10px; margin-bottom:15px; flex-wrap:wrap;">
                <button class="btn" onclick="loadCerts()">🔄 Refresh</button>
                <button class="btn success" onclick="showAddCert()">+ Add Certificate</button>
            </div>
            <div id="cert-list">Loading certificates...</div>
        </div>
    </div>

    <div class="content hidden" id="tab-terminal">
        <div class="card full-width">
            <h3>🖥️ Bash Terminal</h3>
            <div class="terminal-window" id="terminal">
                <div class="terminal-line terminal-info">Linux-System Web Terminal v2.0</div>
                <div class="terminal-line terminal-info">Full bash terminal - no restrictions</div>
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

    <div class="modal-overlay" id="cron-modal">
        <div class="modal">
            <button class="modal-close" onclick="closeCronModal()">×</button>
            <h3>➕ Add Cron Job</h3>
            <div class="form-group">
                <label>Schedule (cron expression)</label>
                <input type="text" id="cron-schedule" placeholder="*/5 * * * *" value="*/5 * * * *">
                <div style="font-size:11px;color:#a6adc8;margin-top:4px;">Format: min hour day month weekday</div>
            </div>
            <div class="form-group">
                <label>Command</label>
                <input type="text" id="cron-command" placeholder="/usr/bin/python3 /path/to/script.py">
            </div>
            <div style="display:flex; gap:10px;">
                <button class="btn success" onclick="addCron()">💾 Add Job</button>
                <button class="btn" onclick="closeCronModal()">Cancel</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="ssh-modal">
        <div class="modal">
            <button class="modal-close" onclick="closeSSHModal()">×</button>
            <h3>🔑 Generate SSH Key</h3>
            <div class="form-group">
                <label>Key Name</label>
                <input type="text" id="ssh-name" placeholder="id_rsa_render">
            </div>
            <div class="form-group">
                <label>Key Type</label>
                <select id="ssh-type">
                    <option value="rsa">RSA</option>
                    <option value="ed25519">Ed25519</option>
                    <option value="ecdsa">ECDSA</option>
                </select>
            </div>
            <div class="form-group">
                <label>Comment (optional)</label>
                <input type="text" id="ssh-comment" placeholder="user@render">
            </div>
            <div style="display:flex; gap:10px;">
                <button class="btn success" onclick="generateKey()">🔨 Generate</button>
                <button class="btn" onclick="closeSSHModal()">Cancel</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="task-modal">
        <div class="modal">
            <button class="modal-close" onclick="closeTaskModal()">×</button>
            <h3>📅 Schedule One-Time Task</h3>
            <div class="form-group">
                <label>Task Name</label>
                <input type="text" id="task-name" placeholder="backup-database">
            </div>
            <div class="form-group">
                <label>Command</label>
                <input type="text" id="task-command" placeholder="/usr/bin/pg_dump mydb > /tmp/backup.sql">
            </div>
            <div class="form-group">
                <label>Run At (YYYY-MM-DD HH:MM)</label>
                <input type="text" id="task-time" placeholder="2026-07-01 14:30">
            </div>
            <div style="display:flex; gap:10px;">
                <button class="btn success" onclick="addTask()">📅 Schedule</button>
                <button class="btn" onclick="closeTaskModal()">Cancel</button>
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
        let dockerData = [];
        let cronData = [];
        let sshData = [];
        let taskData = [];

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
            if (tab === 'firewall') loadFirewall('iptables');
            if (tab === 'cron') loadCron();
            if (tab === 'docker') loadDocker();
            if (tab === 'ssh') loadSSHKeys();
            if (tab === 'tasks') loadTasks();
            if (tab === 'htop') loadHtop();
            if (tab === 'gpu') loadGPU();
            if (tab === 'packages') loadPackages();
            if (tab === 'backup') loadBackups();
            if (tab === 'speedtest') ;
            if (tab === 'certs') loadCerts();
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

        // Services
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

        // Network
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

        // Files
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

        // Logs
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

        // System Info
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

        // Firewall
        function loadFirewall(type) {
            document.querySelectorAll('#tab-firewall .tab-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            socket.emit('get_firewall', type);
        }
        socket.on('firewall', (data) => {
            const list = document.getElementById('firewall-list');
            if (data.error) {
                list.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div>${data.error}</div>`;
            } else if (data.lines.length === 0) {
                list.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🔥</div>No firewall rules found</div>`;
            } else {
                list.innerHTML = data.lines.map(l => `<div class="log-line">${escapeHtml(l)}</div>`).join('');
            }
        });

        // Cron Manager
        function loadCron() {
            socket.emit('get_cron');
        }
        socket.on('cron', (data) => {
            cronData = data;
            const list = document.getElementById('cron-list');
            if (data.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⏰</div>No cron jobs found</div>';
            } else {
                list.innerHTML = data.map((c, i) => `
                    <div class="cron-item">
                        <div>
                            <div style="font-weight:600;">${c.schedule}</div>
                            <div style="font-size:12px; color:#a6adc8;">${c.command}</div>
                            <div style="font-size:11px; color:#89b4fa;">${c.user || 'current user'}</div>
                        </div>
                        <button class="cron-btn" onclick="removeCron(${i})">Remove</button>
                    </div>
                `).join('');
            }
        });
        function showAddCron() {
            document.getElementById('cron-modal').classList.add('show');
        }
        function closeCronModal() {
            document.getElementById('cron-modal').classList.remove('show');
        }
        function addCron() {
            const schedule = document.getElementById('cron-schedule').value;
            const command = document.getElementById('cron-command').value;
            if (!schedule || !command) { alert('Please fill all fields'); return; }
            socket.emit('add_cron', {schedule, command});
            closeCronModal();
        }
        function removeCron(index) {
            if (confirm('Remove this cron job?')) socket.emit('remove_cron', index);
        }

        // Docker Monitor
        function loadDocker() {
            socket.emit('get_docker');
        }
        socket.on('docker', (data) => {
            dockerData = data.containers;
            document.getElementById('docker-total').textContent = data.stats.total;
            document.getElementById('docker-running').textContent = data.stats.running;
            document.getElementById('docker-stopped').textContent = data.stats.stopped;
            document.getElementById('docker-images').textContent = data.stats.images;
            renderDocker('all');
        });
        function renderDocker(filter) {
            const list = document.getElementById('docker-list');
            let filtered = dockerData;
            if (filter !== 'all') filtered = dockerData.filter(c => c.status === filter);

            if (filtered.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🐳</div>No containers found</div>';
            } else {
                list.innerHTML = filtered.map(c => `
                    <div class="docker-item">
                        <div>
                            <div style="font-weight:600;">${c.name}</div>
                            <div style="font-size:12px; color:#a6adc8;">${c.image} | ${c.ports || 'no ports'}</div>
                            <div style="font-size:11px; color:#89b4fa;">Created: ${c.created}</div>
                        </div>
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span class="status-badge ${c.status}">${c.status}</span>
                            <button class="docker-btn ${c.status === 'running' ? 'stop' : ''}" 
                                    onclick="dockerAction('${c.id}', '${c.status === 'running' ? 'stop' : 'start'}')">
                                ${c.status === 'running' ? 'Stop' : 'Start'}
                            </button>
                            <button class="docker-btn" onclick="dockerAction('${c.id}', 'restart')">Restart</button>
                        </div>
                    </div>
                `).join('');
            }
        }
        function filterDocker(f) {
            document.querySelectorAll('#tab-docker .tab-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            renderDocker(f);
        }
        function dockerAction(id, action) {
            socket.emit('docker_action', {id, action});
        }

        // SSH Key Manager
        function loadSSHKeys() {
            socket.emit('get_ssh_keys');
        }
        socket.on('ssh_keys', (data) => {
            sshData = data;
            const list = document.getElementById('ssh-list');
            if (data.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔑</div>No SSH keys found</div>';
            } else {
                list.innerHTML = data.map((k, i) => `
                    <div class="ssh-item">
                        <div>
                            <div style="font-weight:600;">${k.name}</div>
                            <div style="font-size:12px; color:#a6adc8;">${k.type} | ${k.fingerprint}</div>
                            <div style="font-size:11px; color:#89b4fa;">Created: ${k.created}</div>
                        </div>
                        <div style="display:flex; gap:8px;">
                            <button class="ssh-btn" style="background:rgba(137,180,250,0.3);" onclick="copyKey(${i}, 'pub')">Copy Public</button>
                            <button class="ssh-btn" onclick="deleteKey(${i})">Delete</button>
                        </div>
                    </div>
                `).join('');
            }
        });
        function showGenerateKey() {
            document.getElementById('ssh-modal').classList.add('show');
        }
        function closeSSHModal() {
            document.getElementById('ssh-modal').classList.remove('show');
        }
        function generateKey() {
            const name = document.getElementById('ssh-name').value;
            const type = document.getElementById('ssh-type').value;
            const comment = document.getElementById('ssh-comment').value;
            if (!name) { alert('Please enter a key name'); return; }
            socket.emit('generate_ssh_key', {name, type, comment});
            closeSSHModal();
        }
        function copyKey(index, which) {
            socket.emit('copy_ssh_key', {index, which});
        }
        function deleteKey(index) {
            if (confirm('Delete this SSH key?')) socket.emit('delete_ssh_key', index);
        }
        socket.on('clipboard', (data) => {
            navigator.clipboard.writeText(data.text).then(() => {
                alert('Copied to clipboard!');
            }).catch(() => {
                alert('Key content: ' + data.text.substring(0, 100) + '...');
            });
        });

        // Task Scheduler
        function loadTasks() {
            socket.emit('get_tasks');
        }
        socket.on('tasks', (data) => {
            taskData = data;
            const list = document.getElementById('task-list');
            if (data.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📅</div>No scheduled tasks</div>';
            } else {
                list.innerHTML = data.map((t, i) => `
                    <div class="task-item">
                        <div>
                            <div style="font-weight:600;">${t.name}</div>
                            <div style="font-size:12px; color:#a6adc8;">${t.command}</div>
                            <div style="font-size:11px; color:#89b4fa;">Run at: ${t.run_at} | Status: ${t.status}</div>
                        </div>
                        <div style="display:flex; gap:8px;">
                            <button class="task-btn" style="background:rgba(137,180,250,0.3);" onclick="runTaskNow(${i})">Run Now</button>
                            <button class="task-btn" onclick="cancelTask(${i})">Cancel</button>
                        </div>
                    </div>
                `).join('');
            }
        });
        function showAddTask() {
            document.getElementById('task-modal').classList.add('show');
        }
        function closeTaskModal() {
            document.getElementById('task-modal').classList.remove('show');
        }
        function addTask() {
            const name = document.getElementById('task-name').value;
            const command = document.getElementById('task-command').value;
            const runAt = document.getElementById('task-time').value;
            if (!name || !command || !runAt) { alert('Please fill all fields'); return; }
            socket.emit('add_task', {name, command, run_at: runAt});
            closeTaskModal();
        }
        function cancelTask(index) {
            if (confirm('Cancel this scheduled task?')) socket.emit('cancel_task', index);
        }
        function runTaskNow(index) {
            socket.emit('run_task_now', index);
        }

        // Terminal
        
        // ===== HTOP =====
        let htopData = [];
        let htopSortBy = 'cpu';
        function loadHtop() {
            socket.emit('get_htop');
        }
        socket.on('htop', (data) => {
            htopData = data;
            renderHtop();
        });
        function renderHtop() {
            const list = document.getElementById('htop-list');
            let filtered = htopData;
            const q = document.getElementById('htop-search')?.value?.toLowerCase() || '';
            if (q) filtered = htopData.filter(p => p.name.toLowerCase().includes(q) || String(p.pid).includes(q));

            filtered.sort((a, b) => {
                if (htopSortBy === 'cpu') return b.cpu - a.cpu;
                if (htopSortBy === 'mem') return b.mem - a.mem;
                if (htopSortBy === 'pid') return a.pid - b.pid;
                return 0;
            });

            list.innerHTML = filtered.map(p => `
                <div class="htop-row">
                    <span>${p.pid}</span>
                    <span style="overflow:hidden; text-overflow:ellipsis;">${escapeHtml(p.name)}</span>
                    <span style="color:${p.cpu > 50 ? '#f38ba8' : p.cpu > 20 ? '#f9e2af' : '#a6e3a1'}">${p.cpu}%</span>
                    <span>${p.mem}%</span>
                    <span>${p.res}</span>
                    <span>${p.time}</span>
                    <span>${p.user}</span>
                </div>
            `).join('');
        }
        function htopSort(by) {
            htopSortBy = by;
            renderHtop();
        }
        function filterHtop() {
            renderHtop();
        }

        // ===== GPU MONITOR =====
        function loadGPU() {
            socket.emit('get_gpu');
        }
        socket.on('gpu', (data) => {
            const content = document.getElementById('gpu-content');
            if (data.error || data.gpus.length === 0) {
                content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🎮</div>${data.error || 'No GPU detected'}</div>`;
            } else {
                content.innerHTML = data.gpus.map(g => `
                    <div class="gpu-card">
                        <div class="gpu-name">${g.name}</div>
                        <div class="gpu-stat"><span>Utilization</span><span style="color:#89b4fa">${g.utilization}%</span></div>
                        <div class="progress-bar"><div class="progress-fill" style="width:${g.utilization}%"></div></div>
                        <div class="gpu-stat"><span>Memory</span><span>${g.mem_used} / ${g.mem_total} MB</span></div>
                        <div class="progress-bar"><div class="progress-fill ${g.mem_percent > 90 ? 'danger' : g.mem_percent > 70 ? 'warning' : ''}" style="width:${g.mem_percent}%"></div></div>
                        <div class="gpu-stat"><span>Temperature</span><span style="color:${g.temp > 80 ? '#f38ba8' : g.temp > 60 ? '#f9e2af' : '#a6e3a1'}">${g.temp}°C</span></div>
                        <div class="gpu-stat"><span>Power</span><span>${g.power}W</span></div>
                        <div class="gpu-stat"><span>Driver</span><span>${g.driver}</span></div>
                    </div>
                `).join('');
            }
        });

        // ===== PACKAGE MANAGER =====
        let packageData = {installed: [], upgradable: []};
        function loadPackages() {
            socket.emit('get_packages');
        }
        socket.on('packages', (data) => {
            packageData = data;
            filterPackages('installed');
        });
        function filterPackages(type) {
            document.querySelectorAll('#tab-packages .tab-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            const list = document.getElementById('package-list');
            const pkgs = packageData[type] || [];
            if (pkgs.length === 0) {
                list.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📦</div>No ${type} packages</div>`;
            } else {
                list.innerHTML = pkgs.map(p => `
                    <div class="process-item">
                        <span><strong>${p.name}</strong> ${p.version || ''} ${p.new_version ? '→ ' + p.new_version : ''}</div>
                        <span style="color:#a6adc8; font-size:11px;">${p.description || ''}</span>
                    </div>
                `).join('');
            }
        }
        function checkUpdates() {
            socket.emit('check_package_updates');
            emit('notification', {title: 'Checking', body: 'Looking for package updates...'});
        }
        function upgradeAll() {
            if (confirm('Upgrade all packages? This may take a while.')) {
                socket.emit('upgrade_packages');
            }
        }

        // ===== BACKUP MANAGER =====
        function loadBackups() {
            socket.emit('get_backups');
        }
        socket.on('backups', (data) => {
            const list = document.getElementById('backup-list');
            if (data.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">💾</div>No backup jobs configured</div>';
            } else {
                list.innerHTML = data.map((b, i) => `
                    <div class="backup-item">
                        <div style="font-weight:600;">${b.name}</div>
                        <div style="font-size:12px; color:#a6adc8;">Source: ${b.source} → ${b.destination}</div>
                        <div style="font-size:11px; color:#89b4fa;">Schedule: ${b.schedule} | Last: ${b.last_run || 'Never'} | Status: ${b.status}</div>
                        <div style="margin-top:8px; display:flex; gap:8px;">
                            <button class="btn" style="font-size:11px; padding:4px 10px;" onclick="runBackup(${i})">▶ Run Now</button>
                            <button class="btn" style="font-size:11px; padding:4px 10px; background:rgba(255,85,85,0.3);" onclick="deleteBackup(${i})">Delete</button>
                        </div>
                    </div>
                `).join('');
            }
        });
        function showAddBackup() {
            const name = prompt('Backup name:');
            if (!name) return;
            const source = prompt('Source path:', '/home');
            const dest = prompt('Destination path:', '/tmp/backup');
            const schedule = prompt('Schedule (cron):', '0 2 * * *');
            if (name && source && dest) {
                socket.emit('add_backup', {name, source, destination: dest, schedule});
            }
        }
        function runBackup(index) {
            socket.emit('run_backup', index);
        }
        function deleteBackup(index) {
            if (confirm('Delete this backup job?')) socket.emit('delete_backup', index);
        }

        // ===== SPEED TEST =====
        function runSpeedtest() {
            const result = document.getElementById('speedtest-result');
            result.innerHTML = '<div class="speed-result"><div>Running speed test...</div><div style="font-size:14px; color:#a6adc8; margin-top:10px;">This may take 30-60 seconds</div></div>';
            socket.emit('run_speedtest');
        }
        socket.on('speedtest_result', (data) => {
            const result = document.getElementById('speedtest-result');
            if (data.error) {
                result.innerHTML = `<div class="speed-result" style="color:#f38ba8">Error: ${data.error}</div>`;
            } else {
                result.innerHTML = `
                    <div class="speed-result">
                        <div style="display:flex; gap:30px; justify-content:center; flex-wrap:wrap;">
                            <div><div class="speed-value">${data.download}</div><div style="color:#a6adc8; font-size:12px;">Download Mbps</div></div>
                            <div><div class="speed-value">${data.upload}</div><div style="color:#a6adc8; font-size:12px;">Upload Mbps</div></div>
                            <div><div class="speed-value">${data.ping}</div><div style="color:#a6adc8; font-size:12px;">Ping ms</div></div>
                        </div>
                        <div style="margin-top:15px; font-size:12px; color:#a6adc8;">Server: ${data.server || 'Unknown'}</div>
                    </div>
                `;
            }
        });

        // ===== SSL CERTIFICATES =====
        function loadCerts() {
            socket.emit('get_certs');
        }
        socket.on('certs', (data) => {
            const list = document.getElementById('cert-list');
            if (data.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔐</div>No certificates found</div>';
            } else {
                list.innerHTML = data.map((c, i) => {
                    const statusClass = c.days > 30 ? 'cert-valid' : c.days > 7 ? 'cert-expiring' : 'cert-expired';
                    const statusText = c.days > 30 ? 'Valid' : c.days > 7 ? 'Expiring Soon' : 'EXPIRED';
                    return `
                        <div class="cert-item">
                            <div>
                                <div style="font-weight:600;">${c.domain}</div>
                                <div style="font-size:11px; color:#a6adc8;">Issuer: ${c.issuer} | Path: ${c.path}</div>
                            </div>
                            <div style="text-align:right;">
                                <div class="${statusClass}">${statusText}</div>
                                <div style="font-size:11px; color:#a6adc8;">${c.days} days left</div>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        });
        function showAddCert() {
            const domain = prompt('Domain name:');
            const path = prompt('Certificate path:', '/etc/letsencrypt/live/' + (domain || 'example.com') + '/fullchain.pem');
            if (domain && path) {
                socket.emit('add_cert', {domain, path});
            }
        }

        // ===== THEME TOGGLE =====
        let darkMode = true;
        function toggleTheme() {
            darkMode = !darkMode;
            if (darkMode) {
                document.body.style.background = '#0f0f1a';
                document.body.style.color = '#cdd6f4';
            } else {
                document.body.style.background = '#f0f0f5';
                document.body.style.color = '#1a1a2e';
            }
            localStorage.setItem('theme', darkMode ? 'dark' : 'light');
        }
        // Load saved theme
        if (localStorage.getItem('theme') === 'light') {
            darkMode = false;
            document.body.style.background = '#f0f0f5';
            document.body.style.color = '#1a1a2e';
        }

        // ===== LANGUAGE =====
        const i18n = {
            en: { dashboard: 'Dashboard', services: 'Services', network: 'Network', files: 'Files', logs: 'Logs', system: 'System', firewall: 'Firewall', cron: 'Cron', docker: 'Docker', ssh: 'SSH', tasks: 'Tasks', terminal: 'Terminal', htop: 'Process Tree', gpu: 'GPU', packages: 'Packages', backup: 'Backups', speedtest: 'Speed Test', certs: 'SSL Certs' },
            de: { dashboard: 'Dashboard', services: 'Dienste', network: 'Netzwerk', files: 'Dateien', logs: 'Protokolle', system: 'System', firewall: 'Firewall', cron: 'Cron', docker: 'Docker', ssh: 'SSH', tasks: 'Aufgaben', terminal: 'Terminal', htop: 'Prozesse', gpu: 'GPU', packages: 'Pakete', backup: 'Sicherungen', speedtest: 'Speedtest', certs: 'Zertifikate' }
        };
        let currentLang = localStorage.getItem('lang') || 'en';


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
    <div class="theme-toggle">
        <button class="theme-btn" onclick="toggleTheme()" title="Toggle Theme">🌓</button>
    </div>
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

# ===== FIREWALL =====
@socketio.on('get_firewall')
def handle_firewall(fw_type):
    try:
        if fw_type == 'iptables':
            result = subprocess.run(['sudo', 'iptables', '-L', '-n', '-v'], capture_output=True, text=True, timeout=10)
        elif fw_type == 'nftables':
            result = subprocess.run(['sudo', 'nft', 'list', 'ruleset'], capture_output=True, text=True, timeout=10)
        elif fw_type == 'ufw':
            result = subprocess.run(['sudo', 'ufw', 'status', 'verbose'], capture_output=True, text=True, timeout=10)
        else:
            result = subprocess.run(['sudo', 'iptables', '-L', '-n', '-v'], capture_output=True, text=True, timeout=10)

        lines = (result.stdout + result.stderr).strip().split('\n')
        emit('firewall', {'lines': lines})
    except Exception as e:
        emit('firewall', {'lines': [], 'error': f'Firewall error: {e}'})

# ===== CRON MANAGER =====
@socketio.on('get_cron')
def handle_cron():
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split('\n')
        jobs = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 6:
                    schedule = ' '.join(parts[:5])
                    command = ' '.join(parts[5:])
                    jobs.append({'schedule': schedule, 'command': command})
        emit('cron', jobs)
    except Exception as e:
        emit('cron', [])

@socketio.on('add_cron')
def handle_add_cron(data):
    try:
        schedule = data['schedule']
        command = data['command']
        entry = f"{schedule} {command}\n"

        # Get existing crontab
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=5)
        existing = result.stdout

        # Add new entry
        new_crontab = existing + entry if existing else entry

        # Write via stdin
        proc = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
        proc.communicate(input=new_crontab, timeout=5)

        emit('notification', {'title': 'Cron Added', 'body': f'Added: {schedule} {command}'})
        handle_cron()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('remove_cron')
def handle_remove_cron(index):
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split('\n')

        # Filter out comment lines and empty lines to match index
        job_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
        if 0 <= index < len(job_lines):
            target = job_lines[index]
            new_lines = [l for l in lines if l != target]
            new_crontab = '\n'.join(new_lines) + '\n'

            proc = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
            proc.communicate(input=new_crontab, timeout=5)

            emit('notification', {'title': 'Cron Removed', 'body': f'Removed: {target}'})
            handle_cron()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

# ===== DOCKER MONITOR =====
@socketio.on('get_docker')
def handle_docker():
    try:
        # Container stats
        ps_result = subprocess.run(['docker', 'ps', '-a', '--format', '{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}|{{.CreatedAt}}'], 
                                 capture_output=True, text=True, timeout=10)

        containers = []
        running = 0
        stopped = 0
        for line in ps_result.stdout.strip().split('\n'):
            if not line: continue
            parts = line.split('|')
            if len(parts) >= 4:
                status = 'running' if 'Up' in parts[3] else 'exited'
                if status == 'running': running += 1
                else: stopped += 1
                containers.append({
                    'id': parts[0][:12],
                    'name': parts[1],
                    'image': parts[2],
                    'status': status,
                    'ports': parts[4] if len(parts) > 4 else '',
                    'created': parts[5] if len(parts) > 5 else ''
                })

        # Image count
        img_result = subprocess.run(['docker', 'images', '-q'], capture_output=True, text=True, timeout=10)
        images = len([l for l in img_result.stdout.strip().split('\n') if l])

        emit('docker', {
            'containers': containers,
            'stats': {'total': len(containers), 'running': running, 'stopped': stopped, 'images': images}
        })
    except Exception as e:
        emit('docker', {'containers': [], 'stats': {'total': 0, 'running': 0, 'stopped': 0, 'images': 0}})

@socketio.on('docker_action')
def handle_docker_action(data):
    try:
        action = data['action']
        cid = data['id']

        if action == 'start':
            subprocess.run(['docker', 'start', cid], capture_output=True, text=True, timeout=30)
        elif action == 'stop':
            subprocess.run(['docker', 'stop', cid], capture_output=True, text=True, timeout=30)
        elif action == 'restart':
            subprocess.run(['docker', 'restart', cid], capture_output=True, text=True, timeout=30)
        elif action == 'remove':
            subprocess.run(['docker', 'rm', '-f', cid], capture_output=True, text=True, timeout=30)

        emit('notification', {'title': f'Docker {action}', 'body': f'Container {cid} {action}ed'})
        handle_docker()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

# ===== SSH KEY MANAGER =====
SSH_DIR = os.path.expanduser('~/.ssh')

@socketio.on('get_ssh_keys')
def handle_ssh_keys():
    try:
        keys = []
        if os.path.exists(SSH_DIR):
            for f in os.listdir(SSH_DIR):
                if f.endswith('.pub'):
                    pub_path = os.path.join(SSH_DIR, f)
                    priv_path = pub_path[:-4]

                    # Get fingerprint
                    fp_result = subprocess.run(['ssh-keygen', '-lf', pub_path], capture_output=True, text=True, timeout=5)
                    fp = fp_result.stdout.strip().split()[1] if fp_result.stdout else 'unknown'

                    # Get type
                    with open(pub_path, 'r') as file:
                        content = file.read().strip().split()
                        key_type = content[0] if content else 'unknown'

                    stat = os.stat(pub_path)
                    keys.append({
                        'name': f,
                        'type': key_type,
                        'fingerprint': fp,
                        'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                    })
        emit('ssh_keys', keys)
    except Exception as e:
        emit('ssh_keys', [])

@socketio.on('generate_ssh_key')
def handle_generate_ssh_key(data):
    try:
        name = data['name']
        key_type = data.get('type', 'rsa')
        comment = data.get('comment', '')

        os.makedirs(SSH_DIR, exist_ok=True)

        key_path = os.path.join(SSH_DIR, name)

        cmd = ['ssh-keygen', '-t', key_type, '-f', key_path, '-N', '', '-C', comment or '']
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        emit('notification', {'title': 'SSH Key Generated', 'body': f'Key saved to {key_path}'})
        handle_ssh_keys()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('copy_ssh_key')
def handle_copy_ssh_key(data):
    try:
        index = data['index']
        which = data.get('which', 'pub')

        keys = []
        if os.path.exists(SSH_DIR):
            for f in sorted(os.listdir(SSH_DIR)):
                if f.endswith('.pub'):
                    keys.append(f)

        if 0 <= index < len(keys):
            key_file = keys[index]
            if which == 'pub':
                with open(os.path.join(SSH_DIR, key_file), 'r') as f:
                    content = f.read()
            else:
                priv_file = key_file[:-4]
                with open(os.path.join(SSH_DIR, priv_file), 'r') as f:
                    content = f.read()
            emit('clipboard', {'text': content})
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('delete_ssh_key')
def handle_delete_ssh_key(index):
    try:
        keys = []
        if os.path.exists(SSH_DIR):
            for f in sorted(os.listdir(SSH_DIR)):
                if f.endswith('.pub'):
                    keys.append(f)

        if 0 <= index < len(keys):
            key_file = keys[index]
            priv_file = key_file[:-4]

            pub_path = os.path.join(SSH_DIR, key_file)
            priv_path = os.path.join(SSH_DIR, priv_file)

            if os.path.exists(pub_path): os.remove(pub_path)
            if os.path.exists(priv_path): os.remove(priv_path)

            emit('notification', {'title': 'SSH Key Deleted', 'body': f'Deleted {key_file}'})
            handle_ssh_keys()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

# ===== TASK SCHEDULER (using at) =====
scheduled_tasks = []

@socketio.on('get_tasks')
def handle_tasks():
    try:
        # Also check system at queue
        result = subprocess.run(['atq'], capture_output=True, text=True, timeout=5)
        at_jobs = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    job_id = parts[0]
                    at_jobs.append({'id': job_id, 'raw': line})

        emit('tasks', scheduled_tasks)
    except Exception as e:
        emit('tasks', scheduled_tasks)

@socketio.on('add_task')
def handle_add_task(data):
    try:
        name = data['name']
        command = data['command']
        run_at = data['run_at']

        scheduled_tasks.append({
            'name': name,
            'command': command,
            'run_at': run_at,
            'status': 'pending',
            'created': datetime.now().strftime('%Y-%m-%d %H:%M')
        })

        emit('notification', {'title': 'Task Scheduled', 'body': f'{name} at {run_at}'})
        handle_tasks()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('cancel_task')
def handle_cancel_task(index):
    try:
        if 0 <= index < len(scheduled_tasks):
            task = scheduled_tasks.pop(index)
            emit('notification', {'title': 'Task Cancelled', 'body': f'Cancelled {task["name"]}'})
            handle_tasks()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('run_task_now')
def handle_run_task_now(index):
    try:
        if 0 <= index < len(scheduled_tasks):
            task = scheduled_tasks[index]
            result = subprocess.run(task['command'], shell=True, capture_output=True, text=True, timeout=60)
            emit('notification', {
                'title': f'Task Executed: {task["name"]}',
                'body': f'Exit code: {result.returncode}\n{result.stdout[:200]}'
            })
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

# ===== TERMINAL =====
@socketio.on('terminal_command')
def handle_terminal(cmd):
    try:
        cmd = cmd.strip()
        if not cmd:
            return
        if cmd == 'help':
            emit('terminal_output', {'output': 'Full bash terminal - no restrictions. Use any command.', 'info': True})
            return
        if cmd == 'clear':
            emit('terminal_output', {'output': '__CLEAR__', 'info': True})
            return

        # Run command with 60s timeout, in real home directory
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=os.path.expanduser('~'))
        output = (result.stdout + result.stderr).strip()

        if output:
            # Preserve newlines for terminal display
            emit('terminal_output', {'output': output.replace('\n', '<br>'), 'success': result.returncode == 0, 'error': result.returncode != 0})
        else:
            emit('terminal_output', {'output': '(no output)', 'success': result.returncode == 0})
    except subprocess.TimeoutExpired:
        emit('terminal_output', {'output': 'Command timed out (60s limit)', 'error': True})
    except Exception as e:
        emit('terminal_output', {'output': str(e), 'error': True})


# ===== HTOP =====
@socketio.on('get_htop')
def handle_htop():
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'cpu_times', 'username']):
            try:
                info = proc.info
                mem_mb = info['memory_info'].rss // (1024*1024) if info['memory_info'] else 0
                cpu_time = sum(info['cpu_times']) if info['cpu_times'] else 0
                hours = int(cpu_time // 3600)
                mins = int((cpu_time % 3600) // 60)
                secs = int(cpu_time % 60)

                processes.append({
                    'pid': info['pid'],
                    'name': info['name'][:30],
                    'cpu': round(info['cpu_percent'] or 0, 1),
                    'mem': round(info['memory_percent'] or 0, 1),
                    'res': f"{mem_mb}M",
                    'time': f"{hours}:{mins:02d}:{secs:02d}",
                    'user': (info['username'] or 'unknown')[:12]
                })
            except:
                pass
        emit('htop', processes)
    except Exception as e:
        emit('htop', [])

# ===== GPU MONITOR =====
@socketio.on('get_gpu')
def handle_gpu():
    try:
        gpus = []
        # Try nvidia-smi
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,driver_version', '--format=csv,noheader,nounits'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 7:
                    mem_used = float(parts[2]) if parts[2] else 0
                    mem_total = float(parts[3]) if parts[3] else 1
                    gpus.append({
                        'name': parts[0],
                        'utilization': float(parts[1]) if parts[1] else 0,
                        'mem_used': int(mem_used),
                        'mem_total': int(mem_total),
                        'mem_percent': round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0,
                        'temp': float(parts[4]) if parts[4] else 0,
                        'power': float(parts[5]) if parts[5] else 0,
                        'driver': parts[6]
                    })

        # Try rocm-smi for AMD
        if not gpus:
            result = subprocess.run(['rocm-smi', '--showproductname', '--showuse', '--showtemp', '--showpower'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                gpus.append({'name': 'AMD GPU', 'utilization': 0, 'mem_used': 0, 'mem_total': 0, 'mem_percent': 0, 'temp': 0, 'power': 0, 'driver': 'ROCm'})

        emit('gpu', {'gpus': gpus})
    except Exception as e:
        emit('gpu', {'gpus': [], 'error': 'No GPU monitoring tools available (nvidia-smi/rocm-smi not found)'})

# ===== PACKAGE MANAGER =====
@socketio.on('get_packages')
def handle_packages():
    try:
        installed = []
        upgradable = []

        # Try apt (Debian/Ubuntu)
        if os.path.exists('/usr/bin/apt'):
            result = subprocess.run(['apt', 'list', '--installed'], capture_output=True, text=True, timeout=15)
            for line in result.stdout.strip().split('\n')[1:100]:
                if '/' in line:
                    name = line.split('/')[0]
                    installed.append({'name': name, 'version': '', 'description': ''})

            result2 = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True, text=True, timeout=15)
            for line in result2.stdout.strip().split('\n')[1:100]:
                if '/' in line:
                    parts = line.split()
                    name = parts[0].split('/')[0] if parts else ''
                    if len(parts) >= 2 and '->' in line:
                        vparts = line.split('->')
                        new_ver = vparts[-1].strip() if len(vparts) > 1 else ''
                        upgradable.append({'name': name, 'version': '', 'new_version': new_ver, 'description': ''})

        # Try dnf/yum (RHEL/CentOS)
        elif os.path.exists('/usr/bin/dnf'):
            result = subprocess.run(['dnf', 'list', 'installed'], capture_output=True, text=True, timeout=15)
            for line in result.stdout.strip().split('\n')[1:100]:
                parts = line.split()
                if len(parts) >= 2:
                    installed.append({'name': parts[0], 'version': parts[1], 'description': ''})

        emit('packages', {'installed': installed, 'upgradable': upgradable})
    except Exception as e:
        emit('packages', {'installed': [], 'upgradable': []})

@socketio.on('check_package_updates')
def handle_check_updates():
    try:
        if os.path.exists('/usr/bin/apt'):
            subprocess.run(['apt', 'update'], capture_output=True, text=True, timeout=60)
        emit('notification', {'title': 'Package Update', 'body': 'Update check complete'})
        handle_packages()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('upgrade_packages')
def handle_upgrade_packages():
    try:
        if os.path.exists('/usr/bin/apt'):
            result = subprocess.run(['apt', 'upgrade', '-y'], capture_output=True, text=True, timeout=300)
            emit('notification', {'title': 'Upgrade Complete', 'body': result.stdout[:200] or 'Done'})
        handle_packages()
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

# ===== BACKUP MANAGER =====
@socketio.on('get_backups')
def handle_backups():
    emit('backups', backup_jobs)

@socketio.on('add_backup')
def handle_add_backup(data):
    try:
        backup_jobs.append({
            'name': data['name'],
            'source': data['source'],
            'destination': data['destination'],
            'schedule': data['schedule'],
            'status': 'idle',
            'last_run': None
        })
        emit('notification', {'title': 'Backup Added', 'body': f"Job '{data['name']}' created"})
        emit('backups', backup_jobs)
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('run_backup')
def handle_run_backup(index):
    try:
        if 0 <= index < len(backup_jobs):
            job = backup_jobs[index]
            job['status'] = 'running'
            job['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M')

            os.makedirs(job['destination'], exist_ok=True)
            result = subprocess.run(['tar', '-czf', f"{job['destination']}/{job['name']}_{datetime.now().strftime('%Y%m%d_%H%M')}.tar.gz", job['source']], 
                                  capture_output=True, text=True, timeout=300)

            job['status'] = 'success' if result.returncode == 0 else 'failed'
            emit('notification', {'title': 'Backup Complete', 'body': f"'{job['name']}' {'succeeded' if result.returncode == 0 else 'failed'}"})
            emit('backups', backup_jobs)
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

@socketio.on('delete_backup')
def handle_delete_backup(index):
    try:
        if 0 <= index < len(backup_jobs):
            name = backup_jobs[index]['name']
            backup_jobs.pop(index)
            emit('notification', {'title': 'Backup Deleted', 'body': f"Job '{name}' removed"})
            emit('backups', backup_jobs)
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

# ===== SPEED TEST =====
@socketio.on('run_speedtest')
def handle_speedtest():
    try:
        # Try speedtest-cli
        result = subprocess.run(['speedtest-cli', '--simple'], capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            download = upload = ping = '0'
            for line in lines:
                if line.startswith('Ping:'):
                    ping = line.split()[1]
                elif line.startswith('Download:'):
                    download = line.split()[1]
                elif line.startswith('Upload:'):
                    upload = line.split()[1]
            emit('speedtest_result', {'download': download, 'upload': upload, 'ping': ping, 'server': 'speedtest.net'})
        else:
            # Fallback: try curl to fast.com or similar
            emit('speedtest_result', {'error': 'speedtest-cli not installed. Run: apt install speedtest-cli'})
    except Exception as e:
        emit('speedtest_result', {'error': str(e)})

# ===== SSL CERTIFICATES =====
@socketio.on('get_certs')
def handle_certs():
    try:
        certs = []
        # Check Let's Encrypt certs
        le_dir = '/etc/letsencrypt/live'
        if os.path.exists(le_dir):
            for domain in os.listdir(le_dir):
                cert_path = os.path.join(le_dir, domain, 'fullchain.pem')
                if os.path.exists(cert_path):
                    result = subprocess.run(['openssl', 'x509', '-in', cert_path, '-noout', '-dates', '-issuer', '-subject'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        not_after = None
                        issuer = domain
                        for line in result.stdout.split('\n'):
                            if 'notAfter=' in line:
                                not_after = line.split('=')[1]
                            if 'issuer=' in line:
                                issuer = line.split('O=')[1].split('/')[0] if 'O=' in line else line

                        if not_after:
                            expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                            days_left = (expiry - datetime.now()).days
                            certs.append({
                                'domain': domain,
                                'path': cert_path,
                                'issuer': issuer,
                                'days': days_left,
                                'expiry': not_after
                            })

        # Check custom certs from config
        emit('certs', certs)
    except Exception as e:
        emit('certs', [])

@socketio.on('add_cert')
def handle_add_cert(data):
    try:
        if os.path.exists(data['path']):
            result = subprocess.run(['openssl', 'x509', '-in', data['path'], '-noout', '-dates'], 
                                  capture_output=True, text=True, timeout=5)
            not_after = None
            for line in result.stdout.split('\n'):
                if 'notAfter=' in line:
                    not_after = line.split('=')[1]
            if not_after:
                expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                days_left = (expiry - datetime.now()).days
                emit('notification', {'title': 'Certificate Added', 'body': f"{data['domain']} - {days_left} days left"})
        else:
            emit('notification', {'title': 'Error', 'body': 'Certificate file not found'})
    except Exception as e:
        emit('notification', {'title': 'Error', 'body': str(e)})

# ===== STATS EMITTER =====
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
