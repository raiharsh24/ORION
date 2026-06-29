import asyncio
import os
import shlex
from pathlib import Path
from app.tools.base_tool import BaseTool

class TerminalTool(BaseTool):
    """
    Executes bash commands in a system shell terminal environment.
    Blocks potentially destructive actions (e.g. process termination, system control, bulk deletes)
    until confirmed by the user.
    """
    ALLOWED_COMMANDS = {
        "ls", "cat", "echo", "pwd", "env", "whoami", "date", "uname",
        "df", "du", "head", "tail", "grep", "find", "wc", "sort",
        "uniq", "diff", "git", "npm", "node", "pip", "sleep"
    }

    BLOCKED_COMMANDS = {
        "rm", "rmdir", "mkfs", "dd", "shutdown", "reboot", "kill",
        "killall", "chmod", "chown", "sudo", "su", "curl", "wget",
        "nc", "netcat", "python", "python3", "bash", "sh", "zsh",
        "eval", "exec"
    }

    def __init__(self, workspace_root: str | None = None) -> None:
        if not workspace_root:
            workspace_root = os.getenv("WORKSPACE_ROOT", "/home/warlock/ORION")
        self.workspace_root = str(Path(workspace_root).resolve())

    @property
    def name(self) -> str:
        return "terminal"

    @property
    def description(self) -> str:
        return "Execute commands in a shell terminal. Args: cmd (str)"

    def _parse_and_validate(self, command: str) -> list[str]:
        if not command:
            raise ValueError("Empty command.")
        argv = shlex.split(command)
        if not argv:
            raise ValueError("Empty command.")
        base_cmd = os.path.basename(argv[0])

        if base_cmd in self.BLOCKED_COMMANDS:
            raise PermissionError(f"Security Alert: Command '{base_cmd}' is blocked.")
        if base_cmd not in self.ALLOWED_COMMANDS:
            raise PermissionError(f"Security Alert: Command '{base_cmd}' is not allowed.")

        return argv

    def requires_confirmation(self, **kwargs) -> bool:
        cmd = kwargs.get("cmd", "")
        if not cmd:
            return False
        try:
            self._parse_and_validate(cmd)
        except PermissionError:
            # Keep confirmation behavior consistent or block early
            return True
        except Exception:
            pass

        parts = cmd.lower().split()
        dangerous_cmds = {"rm", "kill", "pkill", "killall", "shutdown", "reboot", "dd", "mkfs"}
        for part in parts:
            if part in dangerous_cmds or any(d in part for d in dangerous_cmds):
                return True
        return False

    async def execute(self, **kwargs) -> str:
        cmd = kwargs.get("cmd")
        if not cmd:
            return "Error: Missing required parameter 'cmd'."

        try:
            argv = self._parse_and_validate(cmd)
        except Exception as e:
            return f"Error: Command validation failed: {str(e)}"

        proc = None
        try:
            sanitized_env = {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": self.workspace_root
            }

            import sys
            kwargs = {}
            if sys.platform != "win32":
                kwargs["start_new_session"] = True

            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=sanitized_env,
                **kwargs
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            except asyncio.TimeoutError:
                await self._terminate_proc(proc)
                return "Error: Command execution timed out after 15 seconds."

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            result = []
            if output:
                result.append(output)
            if error:
                result.append(f"STDERR:\n{error}")
            if not output and not error:
                result.append(f"Command exited with code {proc.returncode}")

            return "\n".join(result)
        except asyncio.CancelledError:
            from loguru import logger
            logger.info("TerminalTool task cancelled. Terminating subprocess...")
            if proc:
                await self._terminate_proc(proc)
            raise
        except Exception as e:
            return f"Error: Command execution failed: {str(e)}"

    async def _terminate_proc(self, proc) -> None:
        if not proc:
            return
        import sys
        import signal
        from loguru import logger
        try:
            if sys.platform != "win32":
                try:
                    pgid = os.getpgid(proc.pid)
                    logger.info(f"Terminating process group PGID={pgid}")
                    os.killpg(pgid, signal.SIGTERM)
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except ProcessLookupError:
                    pass
                except asyncio.TimeoutError:
                    try:
                        logger.warning(f"Process group PGID={pgid} did not exit cleanly. Sending SIGKILL.")
                        os.killpg(pgid, signal.SIGKILL)
                        await proc.wait()
                    except ProcessLookupError:
                        pass
            else:
                logger.info(f"Terminating Windows subprocess PID={proc.pid}")
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Error terminating process group: {e}")
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass



