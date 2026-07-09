import sys
import socket
import subprocess
import urllib.request
import json
import uvicorn
from app.core.config import settings

def check_singleton(port: int = 8000):
    # Check if port is in use
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        in_use = s.connect_ex(("127.0.0.1", port)) == 0

    if not in_use:
        return

    # Port is occupied. Find the PID(s) holding the port.
    pids = []
    try:
        output = subprocess.check_output(["lsof", "-t", "-i", f":{port}"], text=True)
        pids = [int(p.strip()) for p in output.strip().split("\n") if p.strip()]
    except Exception:
        pass

    if not pids:
        try:
            output = subprocess.check_output(["ss", "-lptn", f"sport = :{port}"], text=True)
            import re
            pids = [int(pid) for pid in re.findall(r"pid=(\d+)", output)]
        except Exception:
            pass

    pid = pids[0] if pids else None
    
    # Get command line of the PID
    command = "Unknown"
    if pid:
        try:
            with open(f"/proc/{pid}/cmdline", "r") as f:
                command = f.read().replace("\x00", " ").strip()
        except Exception:
            pass

    # Check if it's FRIDAY
    is_friday = False
    # 1. Try health API
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/health")
        with urllib.request.urlopen(req, timeout=0.5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("assistant") == "FRIDAY" or data.get("status") == "online":
                    is_friday = True
    except Exception:
        pass

    # 2. Try command line fallback
    if not is_friday and command != "Unknown":
        cmd_lower = command.lower()
        if "run.py" in cmd_lower or "app.main" in cmd_lower or "friday-api" in cmd_lower:
            is_friday = True

    if is_friday:
        print(f"\n✓ FRIDAY backend already running.")
        print(f"PID: {pid if pid else 'Unknown'}")
        print(f"Port: {port}")
        print("No new instance started.\n")
        sys.exit(0)
    else:
        print(f"\nPort {port} is occupied by another process.")
        print(f"PID: {pid if pid else 'Unknown'}")
        print(f"Command: {command}")
        print("Cannot start FRIDAY.\n")
        sys.exit(1)

if __name__ == "__main__":
    # Perform singleton startup check
    check_singleton(port=8000)

    # Bootstrap uvicorn with host/port mapping
    # Reload is active in Debug mode
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
