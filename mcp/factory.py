"""
mcp/factory.py
==============
Auto-detect whether the configured endpoint is mcpo (OpenAPI REST, port 8000)
or a direct blender-mcp JSON-RPC server (port 9876), and return the right client.

Detection order:
  1. If connection_mode is "mcpo"  → MCPOClient
  2. If connection_mode is "direct" → BlenderMCPClient
  3. If connection_mode is "auto"   → try MCPOClient first, then BlenderMCPClient

The returned object exposes the same interface either way.
"""
from __future__ import annotations

from config.registry import get


def make_client(host: str | None = None,
                port: int | None = None,
                mode: str | None = None,
                timeout: float = 10.0):
    """
    Build the correct MCP client.

    Parameters
    ----------
    host    : hostname/IP (default: from config)
    port    : port number (default: from config)
    mode    : "mcpo" | "direct" | "auto"  (default: from config, then "auto")
    timeout : connection timeout in seconds

    Returns
    -------
    MCPOClient  or  BlenderMCPClient
    """
    host = host or get("mcp_host", "localhost")
    port = port or int(get("mcp_port", 8000))
    mode = mode or get("connection_mode", "auto")

    from mcp.mcpo_client  import MCPOClient
    from mcp.client       import BlenderMCPClient

    if mode == "mcpo":
        return MCPOClient(host, port, timeout=timeout)

    if mode == "direct":
        return BlenderMCPClient(host, port, timeout=timeout)

    # "auto" — sniff which one answers
    # Try mcpo first (it returns a proper OpenAPI JSON on /openapi.json)
    try:
        c = MCPOClient(host, port, timeout=min(timeout, 4.0))
        if c.ping():
            return c
    except Exception:
        pass

    # Fall back to direct JSON-RPC
    return BlenderMCPClient(host, port, timeout=timeout)


def detect_mode(host: str, port: int, timeout: float = 4.0) -> str:
    """
    Return "mcpo", "direct", or "none" depending on what's listening.
    Used by the connection panel to show which server was found.
    """
    from mcp.mcpo_client import MCPOClient, MCPOConnectionError
    from mcp.client      import BlenderMCPClient, MCPConnectionError

    try:
        if MCPOClient(host, port, timeout=timeout).ping():
            return "mcpo"
    except Exception:
        pass

    try:
        if BlenderMCPClient(host, port, timeout=timeout).ping():
            return "direct"
    except Exception:
        pass

    return "none"
