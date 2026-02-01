"""Tool definitions for the agent."""

import json
import logging
from typing import Any

from src.microsoft.auth import MicrosoftAuth
from src.microsoft.graph_client import GraphClient
from src.microsoft.copilot_client import MeetingInsightsClient
from src.harvest import HarvestClient
from src.config import settings

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
    {
        "type": "function",
        "name": "get_file_content",
        "description": "Downloads and extracts text content from a file using its file_id and drive_id. Supports .docx, .xlsx, .pptx, .pdf, and text files. Use read_document instead if you want to search and read in one step.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The ID of the file to download (get this from search_files or get_recent_files)",
                },
                "drive_id": {
                    "type": "string",
                    "description": "The drive ID (required for SharePoint files, get this from search_files results)",
                },
            },
            "required": ["file_id"],
        },
    },
    {
        "type": "function",
        "name": "read_document",
        "description": "ALWAYS use this tool when the user asks to read, open, summarize, or analyze a document. Searches for the document by name, downloads it, and extracts the text content. Supports .docx, .xlsx, .pptx, .pdf, and text files. This is the preferred tool for reading documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The name or partial name of the file to find and read (e.g., 'FRP SOW', 'quarterly report', 'budget.xlsx')",
                },
            },
            "required": ["filename"],
        },
    },
    {
        "type": "function",
        "name": "get_messages_from_person",
        "description": "Get recent messages from a specific person. Searches both emails and Teams chat messages. Use this when the user asks 'what did X say?', 'any messages from X?', 'what was the latest from X?', or similar queries about a specific person.",
        "parameters": {
            "type": "object",
            "properties": {
                "person": {
                    "type": "string",
                    "description": "The name or email of the person to search for (e.g., 'Charlie', 'John Smith', 'john@company.com')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of messages to return from each source (default: 15)",
                },
                "teams_chat_type": {
                    "type": "string",
                    "enum": ["oneOnOne", "group", "all"],
                    "description": "Filter Teams messages by chat type: 'oneOnOne' for 1:1/direct chats only, 'group' for group chats only, 'all' for both (default: all)",
                },
                "include_context": {
                    "type": "boolean",
                    "description": "If true, include your replies in the results to show full conversation context (default: false)",
                },
                "unread_only": {
                    "type": "boolean",
                    "description": "If true, only return unread emails (default: false). Note: Teams doesn't have per-message read status.",
                },
            },
            "required": ["person"],
        },
    },
]

# Harvest tools - only included when Harvest is configured
HARVEST_TOOLS = [
    {
        "type": "function",
        "name": "harvest_get_team",
        "description": "Get all team members from Harvest with their roles and weekly capacity. Use this when the user asks 'who's on my team?', 'show team members', 'list the team', or wants to see team capacity.",
        "parameters": {
            "type": "object",
            "properties": {
                "is_active": {
                    "type": "boolean",
                    "description": "Filter by active status (default: true for active team members only)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "harvest_get_team_member",
        "description": "Get details for a specific team member including their project assignments. Use this when the user asks 'how's [name] doing?', 'show me [name]'s assignments', or wants info about a specific person.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The Harvest user ID (get from harvest_get_team first)",
                },
            },
            "required": ["user_id"],
        },
    },
    {
        "type": "function",
        "name": "harvest_get_time_entries",
        "description": "Get time entries from Harvest with optional filters. Use this when the user asks 'what did [name] work on?', 'hours logged this week', 'show time entries', or wants to see tracked time.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (e.g., '2025-01-20')",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (e.g., '2025-01-27')",
                },
                "user_id": {
                    "type": "integer",
                    "description": "Filter by specific user ID",
                },
                "project_id": {
                    "type": "integer",
                    "description": "Filter by specific project ID",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "harvest_get_projects",
        "description": "Get projects from Harvest with client and budget info. Use this when the user asks 'what projects are active?', 'show current projects', 'list projects', or wants to see project overview.",
        "parameters": {
            "type": "object",
            "properties": {
                "is_active": {
                    "type": "boolean",
                    "description": "Filter by active status (default: true for active projects only)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "harvest_get_project_details",
        "description": "Get detailed info for a specific project including budget status. Use this when the user asks 'how's [project] going?', 'budget status for [project]', or wants detailed project info.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The Harvest project ID (get from harvest_get_projects first)",
                },
            },
            "required": ["project_id"],
        },
    },
    {
        "type": "function",
        "name": "harvest_team_report",
        "description": "Get team utilization report showing hours by person. Use this when the user asks 'team utilization', 'who worked most this week?', 'team hours summary', or wants to see how the team spent their time.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (default: 7 days ago)",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (default: today)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "harvest_project_report",
        "description": "Get project hours summary showing time spent by project. Use this when the user asks 'project hours summary', 'where is time going?', 'time by project', or wants to see project-level time allocation.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (default: 7 days ago)",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (default: today)",
                },
            },
            "required": [],
        },
    },
]


class ToolExecutor:
    """Executes tools called by the LLM."""

    def __init__(self, auth: MicrosoftAuth) -> None:
        self.auth = auth

    def _is_harvest_tool(self, tool_name: str) -> bool:
        """Check if a tool is a Harvest tool."""
        return tool_name.startswith("harvest_")

    def _is_harvest_connected(self) -> bool:
        """Check if Harvest is configured."""
        return bool(settings.harvest_account_id and settings.harvest_access_token)

    def _get_harvest_client(self) -> HarvestClient:
        """Get a Harvest client instance."""
        return HarvestClient(
            account_id=settings.harvest_account_id,
            access_token=settings.harvest_access_token,
        )

    async def execute(self, user_id: str, tool_name: str, arguments: dict) -> dict[str, Any]:
        """Execute a tool and return the result."""
        logger.info(f"Executing tool {tool_name} for user {user_id} with args: {arguments}")

        # Handle Harvest tools
        if self._is_harvest_tool(tool_name):
            return await self._execute_harvest_tool(tool_name, arguments)

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

            elif tool_name == "get_file_content":
                file_id = arguments.get("file_id")
                if not file_id:
                    return {"error": "file_id is required. Use search_files or get_recent_files to find the file ID first."}
                drive_id = arguments.get("drive_id")
                logger.info(f"get_file_content: file_id={file_id}, drive_id={drive_id}")
                result = await graph.get_file_content(file_id=file_id, drive_id=drive_id)
                logger.info(f"get_file_content result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                if "content" in result:
                    logger.info(f"get_file_content: got {len(result.get('content', ''))} chars of content")
                elif "error" in result:
                    logger.error(f"get_file_content error: {result.get('error')}")
                return result

            elif tool_name == "read_document":
                filename = arguments.get("filename")
                if not filename:
                    return {"error": "filename is required (name or partial name of the document to read)"}

                logger.info(f"read_document: searching for '{filename}'")

                # Step 1: Search for the file
                files = await graph.search_files(query=filename, limit=5)
                if not files:
                    return {"error": f"No files found matching '{filename}'", "suggestion": "Try a different search term"}

                logger.info(f"read_document: found {len(files)} files, using first match: {files[0].get('name')}")

                # Step 2: Get the first matching file's content
                file = files[0]
                file_id = file.get("id")
                drive_id = file.get("drive_id")

                if not file_id:
                    return {"error": "Could not get file ID from search results"}

                logger.info(f"read_document: downloading file_id={file_id}, drive_id={drive_id}")
                result = await graph.get_file_content(file_id=file_id, drive_id=drive_id)

                # Add search info to result
                result["search_query"] = filename
                result["matched_file"] = file.get("name")
                if len(files) > 1:
                    result["other_matches"] = [f.get("name") for f in files[1:]]

                if "content" in result:
                    logger.info(f"read_document: got {len(result.get('content', ''))} chars of content")
                elif "error" in result:
                    logger.error(f"read_document error: {result.get('error')}")

                return result

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

            elif tool_name == "get_messages_from_person":
                person = arguments.get("person")
                if not person:
                    return {"error": "person is required (name or email of the person to search for)"}
                limit = min(arguments.get("limit", 15), 30)
                teams_chat_type = arguments.get("teams_chat_type")
                if teams_chat_type == "all":
                    teams_chat_type = None
                include_context = arguments.get("include_context", False)
                unread_only = arguments.get("unread_only", False)

                # Get emails from person
                emails = await graph.get_emails_from_person(
                    person=person, limit=limit, unread_only=unread_only
                )

                # Get Teams messages from person
                teams_messages = await graph.get_teams_messages_from_person(
                    person=person, limit=limit, chat_type=teams_chat_type, include_context=include_context
                )

                return {
                    "person": person,
                    "teams_chat_type_filter": teams_chat_type or "all",
                    "include_context": include_context,
                    "unread_only": unread_only,
                    "emails": emails,
                    "email_count": len(emails),
                    "teams_messages": teams_messages,
                    "teams_count": len(teams_messages),
                }

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except PermissionError as e:
            logger.error(f"Permission error executing {tool_name}: {e}")
            return {"error": str(e), "needs_reconnection": True}
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}", exc_info=True)
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}

    async def _execute_harvest_tool(self, tool_name: str, arguments: dict) -> dict[str, Any]:
        """Execute a Harvest tool."""
        from datetime import datetime, timedelta, timezone

        if not self._is_harvest_connected():
            return {
                "error": "Harvest not configured. Please set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN.",
                "needs_configuration": True,
            }

        harvest = self._get_harvest_client()

        try:
            if tool_name == "harvest_get_team":
                is_active = arguments.get("is_active", True)
                result = await harvest.get_users(is_active=is_active)
                return {"team_members": result, "count": len(result)}

            elif tool_name == "harvest_get_team_member":
                user_id = arguments.get("user_id")
                if not user_id:
                    return {"error": "user_id is required. Use harvest_get_team first to get user IDs."}

                # Get user details and their project assignments
                user = await harvest.get_user(user_id)
                assignments = await harvest.get_user_project_assignments(user_id)

                return {
                    "user": user,
                    "project_assignments": assignments,
                    "assignment_count": len(assignments),
                }

            elif tool_name == "harvest_get_time_entries":
                from_date = arguments.get("from_date")
                to_date = arguments.get("to_date")
                user_id = arguments.get("user_id")
                project_id = arguments.get("project_id")

                # Default to last 7 days if no dates provided
                if not from_date and not to_date:
                    to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

                result = await harvest.get_time_entries(
                    from_date=from_date,
                    to_date=to_date,
                    user_id=user_id,
                    project_id=project_id,
                )

                total_hours = sum(entry["hours"] for entry in result)
                return {
                    "time_entries": result,
                    "count": len(result),
                    "total_hours": round(total_hours, 2),
                    "from_date": from_date,
                    "to_date": to_date,
                }

            elif tool_name == "harvest_get_projects":
                is_active = arguments.get("is_active", True)
                result = await harvest.get_projects(is_active=is_active)
                return {"projects": result, "count": len(result)}

            elif tool_name == "harvest_get_project_details":
                project_id = arguments.get("project_id")
                if not project_id:
                    return {"error": "project_id is required. Use harvest_get_projects first to get project IDs."}

                # Get project details and budget status
                project = await harvest.get_project(project_id)
                budget = await harvest.get_project_budget(project_id)

                return {
                    "project": project,
                    "budget_status": budget,
                }

            elif tool_name == "harvest_team_report":
                from_date = arguments.get("from_date")
                to_date = arguments.get("to_date")

                # Default to last 7 days if no dates provided
                if not to_date:
                    to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if not from_date:
                    from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

                result = await harvest.get_team_time_report(from_date=from_date, to_date=to_date)
                return result

            elif tool_name == "harvest_project_report":
                from_date = arguments.get("from_date")
                to_date = arguments.get("to_date")

                # Default to last 7 days if no dates provided
                if not to_date:
                    to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if not from_date:
                    from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

                result = await harvest.get_project_time_report(from_date=from_date, to_date=to_date)
                return result

            else:
                return {"error": f"Unknown Harvest tool: {tool_name}"}

        except PermissionError as e:
            logger.error(f"Harvest permission error: {e}")
            return {"error": str(e), "needs_configuration": True}
        except Exception as e:
            logger.error(f"Error executing Harvest tool {tool_name}: {e}", exc_info=True)
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}
