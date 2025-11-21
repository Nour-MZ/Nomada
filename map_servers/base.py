# map_servers/base.py

from dataclasses import dataclass
from typing import Dict


@dataclass
class ServerParams:
    """
    Minimal MCP-style server configuration.

    This mirrors the idea of MCP `ServerParams` (e.g., StdioServerParameters)
    but is simplified for HTTP-based map APIs. Each map server has:

    - name: internal name of the server.
    - base_url: root URL for HTTP requests.
    - description: human-readable description.
    - commands: mapping of logical operations to relative endpoints.
    """

    name: str
    base_url: str
    description: str
    commands: Dict[str, str]
