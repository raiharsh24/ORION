from app.mcp_providers import provider_config
from app.mcp_runtime.base import MCPConnectionConfig


def filesystem_server_config(
    server_name: str = "filesystem",
    allowed_directory: str = "/tmp",
    command: str | None = None,
    timeout_seconds: float = 30.0,
) -> MCPConnectionConfig:
    cmd = command or "python"
    return provider_config(
        server_name=server_name,
        command=cmd,
        args=[
            "-m",
            "app.mcp_providers.filesystem.server",
            "--allowed-dir",
            allowed_directory,
        ],
        timeout_seconds=timeout_seconds,
        auto_reconnect=False,
    )


__all__ = ["filesystem_server_config"]
