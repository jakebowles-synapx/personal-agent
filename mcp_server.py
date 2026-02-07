#!/usr/bin/env python3
"""MCP server entry point for Microsoft 365 and Harvest tools.

This server exposes tools for accessing Microsoft 365 data (calendar, email, Teams,
files, meeting transcripts) and Harvest time tracking data via the Model Context
Protocol (MCP).

Usage:
    python mcp_server.py

Configure in Claude Code settings (.claude/settings.json or global):
{
    "mcpServers": {
        "personal-tools": {
            "command": "python",
            "args": ["/path/to/personal-agent/mcp_server.py"],
            "env": {}
        }
    }
}

Prerequisites:
- Run 'python auth_server.py' first to authenticate with Microsoft 365
- Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env for Harvest tools
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.mcp.server import main

if __name__ == "__main__":
    main()
