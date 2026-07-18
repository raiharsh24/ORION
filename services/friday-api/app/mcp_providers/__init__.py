from app.mcp_runtime.base import MCPConnectionConfig, MCPTransportType


def provider_config(
    server_name: str,
    command: str,
    args: list | None = None,
    **kwargs,
) -> MCPConnectionConfig:
    return MCPConnectionConfig(
        server_name=server_name,
        transport=MCPTransportType.STDIO,
        command=command,
        args=args or [],
        **kwargs,
    )


__all__ = ["provider_config"]
