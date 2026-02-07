"""MCP server implementation for Microsoft 365 and Harvest tools."""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.mcp.tools import ToolHandler

logger = logging.getLogger(__name__)

# Create the MCP server
server = Server("personal-tools")

# Create tool handler
tool_handler = ToolHandler()

# Define all available tools
TOOL_DEFINITIONS = [
    # Calendar
    Tool(
        name="get_calendar_events",
        description="Get calendar events from Microsoft 365. Can look forward and/or backward in time.",
        inputSchema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to look ahead (default: 7, max: 30)"},
                "past_days": {"type": "integer", "description": "Days to look back (default: 0, max: 30)"},
            },
        },
    ),
    Tool(
        name="get_today_events",
        description="Get today's calendar events.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_events_for_date",
        description="Get calendar events for a specific date (YYYY-MM-DD format).",
        inputSchema={
            "type": "object",
            "properties": {"date": {"type": "string", "description": "Date in YYYY-MM-DD format"}},
            "required": ["date"],
        },
    ),
    Tool(
        name="get_past_events",
        description="Get past calendar events from recent days.",
        inputSchema={
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "Days to look back (default: 7, max: 30)"}},
        },
    ),
    # Email
    Tool(
        name="get_emails",
        description="Get emails from a folder. Supports search and pagination.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max emails to return (default: 10, max: 50)"},
                "skip": {"type": "integer", "description": "Skip N emails for pagination"},
                "search": {"type": "string", "description": "Search query to filter emails"},
                "folder": {
                    "type": "string",
                    "description": "Mail folder (default: inbox). Options: inbox, sentitems, drafts, deleteditems",
                },
            },
        },
    ),
    Tool(
        name="get_sent_emails",
        description="Get emails you have sent.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max emails to return (default: 10, max: 50)"},
                "skip": {"type": "integer", "description": "Skip N emails for pagination"},
            },
        },
    ),
    Tool(
        name="get_email_details",
        description="Get full content of a specific email by its ID.",
        inputSchema={
            "type": "object",
            "properties": {"email_id": {"type": "string", "description": "The email ID"}},
            "required": ["email_id"],
        },
    ),
    Tool(
        name="get_messages_from_person",
        description="Get recent messages from a specific person (emails and Teams).",
        inputSchema={
            "type": "object",
            "properties": {
                "person": {"type": "string", "description": "Name or email of the person"},
                "limit": {"type": "integer", "description": "Max messages per source (default: 15)"},
                "teams_chat_type": {
                    "type": "string",
                    "enum": ["oneOnOne", "group", "all"],
                    "description": "Filter Teams by chat type",
                },
                "include_context": {"type": "boolean", "description": "Include your replies for context"},
                "unread_only": {"type": "boolean", "description": "Only return unread emails"},
            },
            "required": ["person"],
        },
    ),
    # Teams
    Tool(
        name="get_teams_chats",
        description="Get recent Teams chat conversations.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max chats to return (default: 10, max: 50)"},
                "skip": {"type": "integer", "description": "Skip N chats for pagination"},
            },
        },
    ),
    Tool(
        name="get_chat_messages",
        description="Get messages from a specific Teams chat.",
        inputSchema={
            "type": "object",
            "properties": {
                "chat_id": {"type": "string", "description": "The chat ID"},
                "limit": {"type": "integer", "description": "Max messages (default: 20, max: 50)"},
                "skip": {"type": "integer", "description": "Skip N messages for pagination"},
            },
            "required": ["chat_id"],
        },
    ),
    Tool(
        name="get_my_teams_messages",
        description="Get Teams messages you have sent recently.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max messages to return (default: 20)"},
            },
        },
    ),
    # Files
    Tool(
        name="search_files",
        description="Search files in OneDrive and SharePoint.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max files (default: 10)"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_recent_files",
        description="Get recently accessed files from OneDrive.",
        inputSchema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max files (default: 10)"}},
        },
    ),
    Tool(
        name="read_document",
        description="Search for and read a document's content. Supports .docx, .xlsx, .pptx, .pdf, and text files.",
        inputSchema={
            "type": "object",
            "properties": {"filename": {"type": "string", "description": "Name or partial name of the file"}},
            "required": ["filename"],
        },
    ),
    Tool(
        name="get_file_content",
        description="Get content of a specific file by its ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "The file ID"},
                "drive_id": {"type": "string", "description": "Drive ID (for SharePoint files)"},
            },
            "required": ["file_id"],
        },
    ),
    # Meetings
    Tool(
        name="get_recent_meetings",
        description="Get Teams online meetings from calendar.",
        inputSchema={
            "type": "object",
            "properties": {
                "days_back": {"type": "integer", "description": "Days to look back (default: 30, max: 90)"},
                "days_forward": {"type": "integer", "description": "Days to look ahead (default: 0)"},
                "limit": {"type": "integer", "description": "Max meetings (default: 10)"},
            },
        },
    ),
    Tool(
        name="get_meeting_summary",
        description="Get meeting summary with Copilot AI insights and transcript. Search by subject.",
        inputSchema={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Meeting subject to search for"},
                "join_url": {"type": "string", "description": "Optional: Teams meeting join URL"},
                "organizer_email": {"type": "string", "description": "Optional: Organizer email"},
            },
            "required": ["subject"],
        },
    ),
    Tool(
        name="get_all_transcripts",
        description="Get all available meeting transcripts.",
        inputSchema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max transcripts (default: 50)"}},
        },
    ),
    Tool(
        name="get_transcript_by_meeting_id",
        description="Get transcript for a specific meeting using its meeting ID.",
        inputSchema={
            "type": "object",
            "properties": {"meeting_id": {"type": "string", "description": "The online meeting ID"}},
            "required": ["meeting_id"],
        },
    ),
    Tool(
        name="get_meetings_for_date",
        description="Get Teams online meetings for a specific date.",
        inputSchema={
            "type": "object",
            "properties": {"date": {"type": "string", "description": "Date in YYYY-MM-DD format"}},
            "required": ["date"],
        },
    ),
    # Harvest
    Tool(
        name="harvest_get_projects",
        description="Get projects from Harvest with client and budget info.",
        inputSchema={
            "type": "object",
            "properties": {"is_active": {"type": "boolean", "description": "Filter by active (default: true)"}},
        },
    ),
    Tool(
        name="harvest_get_project_details",
        description="Get detailed info for a specific Harvest project including budget status.",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "integer", "description": "The Harvest project ID"}},
            "required": ["project_id"],
        },
    ),
    Tool(
        name="harvest_get_time_entries",
        description="Get time entries from Harvest with optional filters.",
        inputSchema={
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "user_id": {"type": "integer", "description": "Filter by user ID"},
                "project_id": {"type": "integer", "description": "Filter by project ID"},
            },
        },
    ),
    Tool(
        name="harvest_get_team",
        description="Get all team members from Harvest with roles and capacity.",
        inputSchema={
            "type": "object",
            "properties": {"is_active": {"type": "boolean", "description": "Filter by active (default: true)"}},
        },
    ),
    Tool(
        name="harvest_get_team_member",
        description="Get details for a specific team member including project assignments.",
        inputSchema={
            "type": "object",
            "properties": {"user_id": {"type": "integer", "description": "The Harvest user ID"}},
            "required": ["user_id"],
        },
    ),
    Tool(
        name="harvest_team_report",
        description="Get team utilization report showing hours by person.",
        inputSchema={
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            },
        },
    ),
    Tool(
        name="harvest_project_report",
        description="Get project hours summary showing time by project.",
        inputSchema={
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            },
        },
    ),
    Tool(
        name="harvest_today_tracking",
        description="Get time entries being tracked today.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="harvest_my_time",
        description="Get the current user's recent time entries.",
        inputSchema={
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "Days to look back (default: 7)"}},
        },
    ),
    Tool(
        name="harvest_running_timers",
        description="Find any currently running timers.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="harvest_client_report",
        description="Get time summary by client.",
        inputSchema={
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            },
        },
    ),
    # Connection status
    Tool(
        name="check_connection_status",
        description="Check connection status for Microsoft 365 and Harvest.",
        inputSchema={"type": "object", "properties": {}},
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools."""
    return TOOL_DEFINITIONS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool call: {name} with args: {arguments}")

    try:
        # Route to appropriate handler method
        handler_method = getattr(tool_handler, name, None)
        if not handler_method:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        # Call the handler
        result = await handler_method(**arguments)

        # Return result as JSON
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def run_server():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for the MCP server."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
