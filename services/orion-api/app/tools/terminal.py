import asyncio
from app.tools.base_tool import BaseTool

class TerminalTool(BaseTool):
    """
    Executes bash commands in a system shell terminal environment.
    Blocks potentially destructive actions (e.g. process termination, system control, bulk deletes)
    until confirmed by the user.
    """
    @property
    def name(self) -> str:
        return "terminal"

    @property
    def description(self) -> str:
        return "Execute commands in a shell terminal. Args: cmd (str)"

    def requires_confirmation(self, **kwargs) -> bool:
        cmd = kwargs.get("cmd", "")
        if not cmd:
            return False
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
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            
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
        except asyncio.TimeoutError:
            return "Error: Command execution timed out after 30 seconds."
        except Exception as e:
            return f"Error: Command execution failed: {str(e)}"
