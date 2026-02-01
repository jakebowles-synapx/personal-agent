"""Tool definitions for the agent."""

import json
import logging
from typing import Any

from src.microsoft.auth import MicrosoftAuth
from src.microsoft.graph_client import GraphClient

logger = logging.getLogger(__name__)

# Tool definitions for the Responses API
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_calendar_events",
            "description": "Get upcoming calendar events from Microsoft 365. Use this when the user asks about their schedule, meetings, or calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look ahead (default: 7, max: 30)",
                        "default": 7,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_events",
            "description": "Get today's calendar events. Use this when the user specifically asks about today's schedule or meetings.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_emails",
            "description": "Get recent emails from the user's inbox. Use this when the user asks about their emails or messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of emails to return (default: 10, max: 25)",
                        "default": 10,
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional search query to filter emails by subject, sender, or content",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_email_details",
            "description": "Get the full content of a specific email by its ID. Use this after get_emails to read a specific email in detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The ID of the email to retrieve",
                    },
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_teams_chats",
            "description": "Get recent Teams chat conversations. Use this when the user asks about their Teams messages or chats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of chats to return (default: 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_chat_messages",
            "description": "Get messages from a specific Teams chat. Use this after get_teams_chats to read messages from a conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "The ID of the chat to retrieve messages from",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of messages to return (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["chat_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files in OneDrive and SharePoint. Use this when the user asks about finding documents or files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find files",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of files to return (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_files",
            "description": "Get recently accessed files from OneDrive. Use this when the user asks about their recent documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of files to return (default: 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        },
    },
]


class ToolExecutor:
    """Executes tools called by the LLM."""

    def __init__(self, auth: MicrosoftAuth) -> None:
        self.auth = auth

    async def execute(self, user_id: str, tool_name: str, arguments: dict) -> dict[str, Any]:
        """Execute a tool and return the result."""
        logger.info(f"Executing tool {tool_name} for user {user_id} with args: {arguments}")

        # Check if user is connected to Microsoft
        if not self.auth.is_connected(user_id):
            return {
                "error": "Microsoft 365 not connected. Please use /connect to link your account.",
                "needs_connection": True,
            }

        # Get access token
        access_token = await self.auth.get_access_token(user_id)
        if not access_token:
            return {
                "error": "Failed to get access token. Please reconnect with /connect.",
                "needs_connection": True,
            }

        # Create Graph client
        graph = GraphClient(access_token)

        try:
            # Route to appropriate method
            if tool_name == "get_calendar_events":
                days = min(arguments.get("days", 7), 30)
                result = await graph.get_calendar_events(days=days)
                return {"events": result, "count": len(result)}

            elif tool_name == "get_today_events":
                result = await graph.get_today_events()
                return {"events": result, "count": len(result)}

            elif tool_name == "get_emails":
                limit = min(arguments.get("limit", 10), 25)
                search = arguments.get("search")
                result = await graph.get_emails(limit=limit, search=search)
                return {"emails": result, "count": len(result)}

            elif tool_name == "get_email_details":
                email_id = arguments.get("email_id")
                if not email_id:
                    return {"error": "email_id is required"}
                result = await graph.get_email(email_id)
                return {"email": result}

            elif tool_name == "get_teams_chats":
                limit = min(arguments.get("limit", 10), 25)
                result = await graph.get_teams_chats(limit=limit)
                return {"chats": result, "count": len(result)}

            elif tool_name == "get_chat_messages":
                chat_id = arguments.get("chat_id")
                if not chat_id:
                    return {"error": "chat_id is required"}
                limit = min(arguments.get("limit", 20), 50)
                result = await graph.get_chat_messages(chat_id=chat_id, limit=limit)
                return {"messages": result, "count": len(result)}

            elif tool_name == "search_files":
                query = arguments.get("query")
                if not query:
                    return {"error": "query is required"}
                limit = min(arguments.get("limit", 10), 25)
                result = await graph.search_files(query=query, limit=limit)
                return {"files": result, "count": len(result)}

            elif tool_name == "get_recent_files":
                limit = min(arguments.get("limit", 10), 25)
                result = await graph.get_recent_files(limit=limit)
                return {"files": result, "count": len(result)}

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except PermissionError as e:
            logger.error(f"Permission error executing {tool_name}: {e}")
            return {"error": str(e), "needs_reconnection": True}
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}", exc_info=True)
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}
