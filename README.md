python3 << 'PYEOF'
readme = '''# Linux-System

A modern Linux system management dashboard built with GTK4 and Python.

![Python](https://img.shields.io/badge/python-3.13-blue)
![GTK](https://img.shields.io/badge/GTK-4.0-orange)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Live System Stats** — CPU, RAM, Network (↓↑), Disk, Uptime
- **Quick Launch Bar** — Home, Settings, Trash, Browser, Editor, Calendar, Terminal
- **Macro Recorder** — Record and replay keyboard macros
- **Theme Switcher** — Dark, Light, Cyber, Minimal themes
- **Process Manager** — View, search, and kill processes (SIGTERM / SIGKILL)
- **Notification Area** — System notification history

## Installation

```bash
# Clone
git clone https://github.com/rintuchowdory/Linux-System.git
cd Linux-System

# Create virtual environment
python3 -m venv .venv --system-site-packages
source .venv/bin/activate

# Install dependencies
pip install psutil pynput

# Run
python3 main.py
