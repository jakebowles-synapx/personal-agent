"""Tool definitions for the agent."""

import json
import logging
from typing import Any

from src.microsoft.auth import MicrosoftAuth
from src.microsoft.graph_client import GraphClient
from src.microsoft.copilot_client import MeetingInsightsClient

logger = logging.getLogger(__name__)

# Tool definitions for the Responses API
# Note: Responses API uses a flat structure with name/description/parameters at top level
TOOLS = [
    {
        "type": "function",
        "name": "get_calendar_events",
        "description": "Get calendar events from Microsoft 365. Can look forward and/or backward in time. Use this when the user asks about their schedule, meetings, or calendar - both upcoming AND past events.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead from today (default: 7, max: 30)",
                },
                "past_days": {
                    "type": "integer",
                    "description": "Number of days to look back from today (default: 0, max: 30). Use this to get past events.",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_past_events",
        "description": "Get past calendar events from recent days. Use this when the user asks about meetings they had recently, what happened last week, or needs to recall past events.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default: 7, max: 30)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_today_events",
        "description": "Get today's calendar events. Use this when the user specifically asks about today's schedule or meetings.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_events_for_date",
        "description": "Get calendar events for a specific date. Use this when the user asks about events on a particular day like 'January 30th' or 'last Monday'. Convert the date to YYYY-MM-DD format.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "The date in YYYY-MM-DD format (e.g., '2025-01-30' for January 30th, 2025)",
                },
            },
            "required": ["date"],
        },
    },
    {
        "type": "function",
        "name": "get_meetings_for_date",
        "description": "Get Teams online meetings for a specific date. Use this when the user wants to find meetings on a particular day to get summaries or transcripts. Convert the date to YYYY-MM-DD format.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "The date in YYYY-MM-DD format (e.g., '2025-01-30' for January 30th, 2025)",
                },
            },
            "required": ["date"],
        },
    },
    {
        "type": "function",
        "name": "get_emails",
        "description": "Get recent emails from the user's inbox. Use this when the user asks about their emails or messages.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of emails to return (default: 10, max: 25)",
                },
                "search": {
                    "type": "string",
                    "description": "Optional search query to filter emails by subject, sender, or content",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
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
    {
        "type": "function",
        "name": "get_teams_chats",
        "description": "Get recent Teams chat conversations. Use this when the user asks about their Teams messages or chats.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of chats to return (default: 10)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
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
                },
            },
            "required": ["chat_id"],
        },
    },
    {
        "type": "function",
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
                },
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "get_recent_files",
        "description": "Get recently accessed files from OneDrive. Use this when the user asks about their recent documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of files to return (default: 10)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_recent_meetings",
        "description": "Get Teams online meetings from the calendar. Use this when the user asks about past meetings, wants to find a meeting to summarize, or needs meeting details. Returns meeting subject, time, organizer, and join URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Number of days to look back (default: 30, max: 90)",
                },
                "days_forward": {
                    "type": "integer",
                    "description": "Number of days to look ahead (default: 0)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of meetings to return (default: 10)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_meeting_summary",
        "description": "ALWAYS use this tool when the user asks to 'summarize a meeting', 'get meeting notes', 'get transcript', or 'what happened in meeting X'. This tool retrieves Copilot AI insights (action items, meeting notes) and transcript content. You can call it with just the meeting subject - it will search the calendar automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "The meeting subject/title to search for (e.g., 'Underwriting Discovery p.4')",
                },
                "join_url": {
                    "type": "string",
                    "description": "Optional: The Teams meeting join URL if known",
                },
                "organizer_email": {
                    "type": "string",
                    "description": "Optional: Email address of the meeting organizer",
                },
            },
            "required": ["subject"],
        },
    },
    {
        "type": "function",
        "name": "get_all_transcripts",
        "description": "Get all available meeting transcripts the user has access to. Use this to discover which meetings have transcripts available before trying to get a specific meeting summary. Returns a list of transcripts with meeting IDs and organizer info.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of transcripts to return (default: 50)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_transcript_by_meeting_id",
        "description": "Get transcript content for a specific meeting using its meeting ID (from get_all_transcripts). Use this when you have the meeting_id from the transcript list.",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_id": {
                    "type": "string",
                    "description": "The online meeting ID (from get_all_transcripts results)",
                },
            },
            "required": ["meeting_id"],
        },
    },
    {
        "type": "function",
        "name": "list_meetings_with_transcripts",
        "description": "List online meetings you organized and check which ones have transcripts available. Use this to debug transcript access issues and see what meetings have transcript data.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
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
                past_days = min(arguments.get("past_days", 0), 30)
                result = await graph.get_calendar_events(days=days, past_days=past_days)
                return {"events": result, "count": len(result)}

            elif tool_name == "get_past_events":
                days = min(arguments.get("days", 7), 30)
                result = await graph.get_past_events(days=days)
                return {"events": result, "count": len(result)}

            elif tool_name == "get_today_events":
                result = await graph.get_today_events()
                return {"events": result, "count": len(result)}

            elif tool_name == "get_events_for_date":
                date_str = arguments.get("date")
                if not date_str:
                    return {"error": "date is required in YYYY-MM-DD format"}
                result = await graph.get_events_for_date(date_str=date_str)
                return {"events": result, "count": len(result), "date": date_str}

            elif tool_name == "get_meetings_for_date":
                date_str = arguments.get("date")
                if not date_str:
                    return {"error": "date is required in YYYY-MM-DD format"}
                meetings_client = MeetingInsightsClient(access_token)
                result = await meetings_client.get_meetings_for_date(date_str=date_str)
                return {"meetings": result, "count": len(result), "date": date_str}

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

            elif tool_name == "get_recent_meetings":
                meetings_client = MeetingInsightsClient(access_token)
                days_back = min(arguments.get("days_back", 30), 90)
                days_forward = min(arguments.get("days_forward", 0), 30)
                limit = min(arguments.get("limit", 10), 25)
                result = await meetings_client.get_recent_meetings(
                    days_back=days_back,
                    days_forward=days_forward,
                    limit=limit,
                )
                return {"meetings": result, "count": len(result)}

            elif tool_name == "get_meeting_summary":
                subject = arguments.get("subject")
                join_url = arguments.get("join_url")
                organizer_email = arguments.get("organizer_email")

                if not subject and not join_url:
                    return {"error": "subject is required to find the meeting."}

                meetings_client = MeetingInsightsClient(access_token)
                result = await meetings_client.get_meeting_summary(
                    subject=subject,
                    join_url=join_url,
                    organizer_email=organizer_email,
                )
                return result

            elif tool_name == "get_all_transcripts":
                meetings_client = MeetingInsightsClient(access_token)
                limit = min(arguments.get("limit", 50), 100)
                result = await meetings_client.get_all_available_transcripts()
                return result

            elif tool_name == "get_transcript_by_meeting_id":
                meeting_id = arguments.get("meeting_id")
                if not meeting_id:
                    return {"error": "meeting_id is required. Get it from get_all_transcripts first."}
                meetings_client = MeetingInsightsClient(access_token)
                result = await meetings_client.get_meeting_summary(meeting_id=meeting_id)
                return result

            elif tool_name == "list_meetings_with_transcripts":
                meetings_client = MeetingInsightsClient(access_token)
                result = await meetings_client.list_online_meetings_with_transcripts()
                return {
                    "meetings": result,
                    "count": len(result),
                    "with_transcripts": sum(1 for m in result if m.get("has_transcripts")),
                    "note": "Only shows meetings you organized. Transcripts require transcription to be enabled during the meeting."
                }

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except PermissionError as e:
            logger.error(f"Permission error executing {tool_name}: {e}")
            return {"error": str(e), "needs_reconnection": True}
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}", exc_info=True)
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}
