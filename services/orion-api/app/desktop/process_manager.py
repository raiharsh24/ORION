import os
import sys
import subprocess
from typing import List, Dict, Any

class ProcessManager:
    """
    Manages and tracks active system processes.
    Uses direct /proc parses on Linux for fast, dependency-free results,
    and falls back to 'ps' command execution on macOS/Unix.
    """
    def __init__(self) -> None:
        """Initialize the ProcessManager."""
        pass

    async def list_processes(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of all currently running system processes.

        Returns:
            List[Dict[str, Any]]: List of process metadata dictionaries.
        """
        processes = []

        if sys.platform != "linux":
            # Fallback to executing POSIX 'ps' command on Non-Linux OS
            try:
                proc = subprocess.run(
                    ["ps", "-ax", "-o", "pid,state,comm"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                if proc.returncode == 0:
                    lines = proc.stdout.splitlines()[1:]  # Skip header
                    for line in lines:
                        parts = line.split(None, 2)
                        if len(parts) >= 3:
                            processes.append({
                                "pid": int(parts[0]),
                                "name": parts[2].strip(),
                                "status": parts[1].strip()
                            })
            except Exception:
                pass
            return processes

        # Linux direct /proc scanner - highly performant & reliable
        try:
            for pid_str in os.listdir("/proc"):
                if pid_str.isdigit():
                    pid = int(pid_str)
                    proc_dir = os.path.join("/proc", pid_str)
                    try:
                        # Fetch process command name
                        comm_path = os.path.join(proc_dir, "comm")
                        if os.path.exists(comm_path):
                            with open(comm_path, "r", encoding="utf-8", errors="ignore") as f:
                                name = f.read().strip()
                        else:
                            name = "unknown"

                        # Fetch process status
                        stat_path = os.path.join(proc_dir, "stat")
                        status = "unknown"
                        if os.path.exists(stat_path):
                            with open(stat_path, "r", encoding="utf-8", errors="ignore") as f:
                                stat_content = f.read().strip()
                                rparen = stat_content.rfind(")")
                                if rparen != -1 and rparen + 2 < len(stat_content):
                                    status_char = stat_content[rparen + 2]
                                    status_map = {
                                        'R': "running",
                                        'S': "sleeping",
                                        'D': "waiting",
                                        'Z': "zombie",
                                        'T': "stopped",
                                        't': "tracing",
                                        'W': "paging",
                                        'X': "dead",
                                        'x': "dead",
                                        'K': "wakekill",
                                        'P': "parked",
                                    }
                                    status = status_map.get(status_char, f"unknown ({status_char})")
                        
                        processes.append({
                            "pid": pid,
                            "name": name,
                            "status": status
                        })
                    except Exception:
                        pass
        except Exception:
            pass

        return processes

    async def terminate_process(self, pid: int) -> bool:
        """
        Kills a specific process by its PID.

        Args:
            pid (int): Process Identifier.

        Returns:
            bool: True if process was successfully terminated.
        """
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False

    async def is_running(self, app_name: str) -> bool:
        """
        Checks if any active process name matches the app_name query.

        Args:
            app_name (str): Process name or pattern.

        Returns:
            bool: True if running.
        """
        procs = await self.list_processes()
        query = app_name.lower()
        for p in procs:
            if query in p["name"].lower():
                return True
        return False
