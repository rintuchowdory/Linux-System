Linux-System
A modern Linux system management dashboard built with GTK4 and Python.
 Python 
 GTK 
 License 
Features

    Live System Stats — CPU, RAM, Network (↓↑), Disk, Uptime
    Quick Launch Bar — Home, Settings, Trash, Browser, Editor, Calendar, Terminal
    Macro Recorder — Record and replay keyboard macros
    Theme Switcher — Dark, Light, Cyber, Minimal themes
    Process Manager — View, search, and kill processes (SIGTERM / SIGKILL)
    Notification Area — System notification history

Installation
bash

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

Kali Linux Setup
bash

sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 python3-psutil
pip install pynput

License
MIT
