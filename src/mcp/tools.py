"""Tool handlers for MCP server - maps MCP calls to Microsoft/Harvest clients."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.microsoft.auth import MicrosoftAuth
from src.microsoft.graph_client import GraphClient
from src.microsoft.copilot_client import MeetingInsightsClient
from src.harvest.client import HarvestClient
from src.config import settings

logger = logging.getLogger(__name__)

# Default user ID for single-user mode
DEFAULT_USER_ID = "default"


class ToolHandler:
    """Handles tool execution for MCP server."""

    def __init__(self) -> None:
        self.auth = MicrosoftAuth()

    def _is_harvest_connected(self) -> bool:
        """Check if Harvest is configured."""
        return bool(settings.harvest_account_id and settings.harvest_access_token)

    def _get_harvest_client(self) -> HarvestClient:
        """Get a Harvest client instance."""
        return HarvestClient(
            account_id=settings.harvest_account_id,
            access_token=settings.harvest_access_token,
        )

    async def _get_graph_client(self) -> GraphClient | None:
        """Get an authenticated Graph client."""
        if not self.auth.is_connected(DEFAULT_USER_ID):
            return None
        access_token = await self.auth.get_access_token(DEFAULT_USER_ID)
        if not access_token:
            return None
        return GraphClient(access_token)

    async def _get_meetings_client(self) -> MeetingInsightsClient | None:
        """Get an authenticated Meetings client."""
        if not self.auth.is_connected(DEFAULT_USER_ID):
            return None
        access_token = await self.auth.get_access_token(DEFAULT_USER_ID)
        if not access_token:
            return None
        return MeetingInsightsClient(access_token)

    # ==================== CALENDAR TOOLS ====================

    async def get_calendar_events(self, days: int = 7, past_days: int = 0) -> dict[str, Any]:
        """Get calendar events from Microsoft 365."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        days = min(days, 30)
        past_days = min(past_days, 30)
        result = await graph.get_calendar_events(days=days, past_days=past_days)
        return {"events": result, "count": len(result)}

    async def get_today_events(self) -> dict[str, Any]:
        """Get today's calendar events."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        result = await graph.get_today_events()
        return {"events": result, "count": len(result)}

    async def get_events_for_date(self, date: str) -> dict[str, Any]:
        """Get calendar events for a specific date."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        result = await graph.get_events_for_date(date_str=date)
        return {"events": result, "count": len(result), "date": date}

    async def get_past_events(self, days: int = 7) -> dict[str, Any]:
        """Get past calendar events from the last N days."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        days = min(days, 30)
        result = await graph.get_past_events(days=days)
        return {"events": result, "count": len(result)}

    # ==================== EMAIL TOOLS ====================

    async def get_emails(
        self, limit: int = 10, skip: int = 0, search: str | None = None, folder: str = "inbox"
    ) -> dict[str, Any]:
        """Get emails from a folder (inbox, sentitems, drafts, etc.)."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        limit = min(limit, 50)
        result = await graph.get_emails(limit=limit, skip=skip, search=search, folder=folder)
        return {"emails": result, "count": len(result), "skip": skip, "folder": folder, "has_more": len(result) == limit}

    async def get_sent_emails(self, limit: int = 10, skip: int = 0) -> dict[str, Any]:
        """Get emails you have sent."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        limit = min(limit, 50)
        result = await graph.get_sent_emails(limit=limit)
        return {"emails": result, "count": len(result), "skip": skip}

    async def get_email_details(self, email_id: str) -> dict[str, Any]:
        """Get full content of a specific email."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        result = await graph.get_email(email_id)
        return {"email": result}

    async def get_messages_from_person(
        self,
        person: str,
        limit: int = 15,
        teams_chat_type: str | None = None,
        include_context: bool = False,
        unread_only: bool = False,
    ) -> dict[str, Any]:
        """Get messages from a specific person (emails and Teams)."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        limit = min(limit, 30)
        if teams_chat_type == "all":
            teams_chat_type = None

        emails = await graph.get_emails_from_person(person=person, limit=limit, unread_only=unread_only)
        teams_messages = await graph.get_teams_messages_from_person(
            person=person, limit=limit, chat_type=teams_chat_type, include_context=include_context
        )

        return {
            "person": person,
            "emails": emails,
            "email_count": len(emails),
            "teams_messages": teams_messages,
            "teams_count": len(teams_messages),
        }

    # ==================== TEAMS TOOLS ====================

    async def get_teams_chats(self, limit: int = 10, skip: int = 0) -> dict[str, Any]:
        """Get recent Teams chat conversations."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        limit = min(limit, 50)
        result = await graph.get_teams_chats(limit=limit, skip=skip)
        return {"chats": result, "count": len(result), "skip": skip, "has_more": len(result) == limit}

    async def get_chat_messages(self, chat_id: str, limit: int = 20, skip: int = 0) -> dict[str, Any]:
        """Get messages from a specific Teams chat."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        limit = min(limit, 50)
        result = await graph.get_chat_messages(chat_id=chat_id, limit=limit)
        return {"messages": result, "count": len(result), "skip": skip, "has_more": len(result) == limit}

    async def get_my_teams_messages(self, limit: int = 20) -> dict[str, Any]:
        """Get Teams messages you have sent recently."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        # Get current user info
        me = await graph.get_me()
        my_name = me.get("name", "").lower()

        # Get recent chats
        chats = await graph.get_teams_chats(limit=30)

        my_messages = []
        for chat in chats:
            chat_id = chat["id"]
            try:
                messages = await graph.get_chat_messages(chat_id=chat_id, limit=30)
                for msg in messages:
                    from_name = msg.get("from", "").lower()
                    if my_name and my_name in from_name:
                        msg["chat_id"] = chat_id
                        msg["chat_topic"] = chat.get("topic", "")
                        msg["chat_type"] = chat.get("chat_type", "")
                        my_messages.append(msg)

                        if len(my_messages) >= limit:
                            break
            except Exception:
                continue

            if len(my_messages) >= limit:
                break

        # Sort by date descending
        my_messages.sort(key=lambda x: x.get("created", ""), reverse=True)
        return {"messages": my_messages[:limit], "count": len(my_messages[:limit])}

    # ==================== FILES TOOLS ====================

    async def search_files(self, query: str, limit: int = 10) -> dict[str, Any]:
        """Search files in OneDrive and SharePoint."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        limit = min(limit, 25)
        result = await graph.search_files(query=query, limit=limit)
        return {"files": result, "count": len(result)}

    async def get_recent_files(self, limit: int = 10) -> dict[str, Any]:
        """Get recently accessed files from OneDrive."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        limit = min(limit, 25)
        result = await graph.get_recent_files(limit=limit)
        return {"files": result, "count": len(result)}

    async def read_document(self, filename: str) -> dict[str, Any]:
        """Search for and read a document's content."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        # Search for the file
        files = await graph.search_files(query=filename, limit=5)
        if not files:
            return {"error": f"No files found matching '{filename}'", "suggestion": "Try a different search term"}

        # Get the first matching file's content
        file = files[0]
        file_id = file.get("id")
        drive_id = file.get("drive_id")

        if not file_id:
            return {"error": "Could not get file ID from search results"}

        result = await graph.get_file_content(file_id=file_id, drive_id=drive_id)
        result["search_query"] = filename
        result["matched_file"] = file.get("name")
        if len(files) > 1:
            result["other_matches"] = [f.get("name") for f in files[1:]]

        return result

    async def get_file_content(self, file_id: str, drive_id: str | None = None) -> dict[str, Any]:
        """Get content of a specific file by ID."""
        graph = await self._get_graph_client()
        if not graph:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        return await graph.get_file_content(file_id=file_id, drive_id=drive_id)

    # ==================== MEETING TOOLS ====================

    async def get_recent_meetings(self, days_back: int = 30, days_forward: int = 0, limit: int = 10) -> dict[str, Any]:
        """Get Teams online meetings from calendar."""
        meetings = await self._get_meetings_client()
        if not meetings:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        days_back = min(days_back, 90)
        days_forward = min(days_forward, 30)
        limit = min(limit, 25)
        result = await meetings.get_recent_meetings(days_back=days_back, days_forward=days_forward, limit=limit)
        return {"meetings": result, "count": len(result)}

    async def get_meeting_summary(
        self,
        subject: str,
        join_url: str | None = None,
        organizer_email: str | None = None,
    ) -> dict[str, Any]:
        """Get meeting summary including Copilot AI insights and transcript."""
        meetings = await self._get_meetings_client()
        if not meetings:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        return await meetings.get_meeting_summary(
            subject=subject,
            join_url=join_url,
            organizer_email=organizer_email,
        )

    async def get_all_transcripts(self, limit: int = 50) -> dict[str, Any]:
        """Get all available meeting transcripts."""
        meetings = await self._get_meetings_client()
        if not meetings:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        return await meetings.get_all_available_transcripts()

    async def get_transcript_by_meeting_id(self, meeting_id: str) -> dict[str, Any]:
        """Get transcript for a specific meeting."""
        meetings = await self._get_meetings_client()
        if not meetings:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        return await meetings.get_meeting_summary(meeting_id=meeting_id)

    async def get_meetings_for_date(self, date: str) -> dict[str, Any]:
        """Get Teams online meetings for a specific date."""
        meetings = await self._get_meetings_client()
        if not meetings:
            return {"error": "Microsoft 365 not connected. Run 'python auth_server.py' to authenticate."}

        result = await meetings.get_meetings_for_date(date_str=date)
        return {"meetings": result, "count": len(result), "date": date}

    # ==================== HARVEST TOOLS ====================

    async def harvest_get_projects(self, is_active: bool = True) -> dict[str, Any]:
        """Get projects from Harvest."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()
        result = await harvest.get_projects(is_active=is_active)
        return {"projects": result, "count": len(result)}

    async def harvest_get_project_details(self, project_id: int) -> dict[str, Any]:
        """Get detailed info for a specific project."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()
        project = await harvest.get_project(project_id)
        budget = await harvest.get_project_budget(project_id)
        return {"project": project, "budget_status": budget}

    async def harvest_get_time_entries(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        user_id: int | None = None,
        project_id: int | None = None,
    ) -> dict[str, Any]:
        """Get time entries from Harvest."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()

        # Default to last 7 days
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

    async def harvest_get_team(self, is_active: bool = True) -> dict[str, Any]:
        """Get team members from Harvest."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()
        result = await harvest.get_users(is_active=is_active)
        return {"team_members": result, "count": len(result)}

    async def harvest_get_team_member(self, user_id: int) -> dict[str, Any]:
        """Get details for a specific team member."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()
        user = await harvest.get_user(user_id)
        assignments = await harvest.get_user_project_assignments(user_id)
        return {"user": user, "project_assignments": assignments, "assignment_count": len(assignments)}

    async def harvest_team_report(self, from_date: str | None = None, to_date: str | None = None) -> dict[str, Any]:
        """Get team utilization report."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()

        if not to_date:
            to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not from_date:
            from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        return await harvest.get_team_time_report(from_date=from_date, to_date=to_date)

    async def harvest_project_report(self, from_date: str | None = None, to_date: str | None = None) -> dict[str, Any]:
        """Get project hours summary."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()

        if not to_date:
            to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not from_date:
            from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        return await harvest.get_project_time_report(from_date=from_date, to_date=to_date)

    async def harvest_today_tracking(self) -> dict[str, Any]:
        """Get time entries being tracked today."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()
        result = await harvest.get_today_time_entries()
        total_hours = sum(entry["hours"] for entry in result)
        return {
            "time_entries": result,
            "count": len(result),
            "total_hours": round(total_hours, 2),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

    async def harvest_my_time(self, days: int = 7) -> dict[str, Any]:
        """Get current user's recent time entries."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()
        days = min(days, 30)
        result = await harvest.get_my_time_entries(days=days)
        total_hours = sum(entry["hours"] for entry in result)
        return {"time_entries": result, "count": len(result), "total_hours": round(total_hours, 2), "days": days}

    async def harvest_running_timers(self) -> dict[str, Any]:
        """Find any currently running timers."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()
        result = await harvest.get_running_timers()
        return {"running_timers": result, "count": len(result)}

    async def harvest_client_report(self, from_date: str | None = None, to_date: str | None = None) -> dict[str, Any]:
        """Get time summary by client."""
        if not self._is_harvest_connected():
            return {"error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env"}

        harvest = self._get_harvest_client()

        if not to_date:
            to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not from_date:
            from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        return await harvest.get_client_report(from_date=from_date, to_date=to_date)

    # ==================== CONNECTION STATUS ====================

    async def check_connection_status(self) -> dict[str, Any]:
        """Check connection status for Microsoft 365 and Harvest."""
        ms_connected = self.auth.is_connected(DEFAULT_USER_ID)
        harvest_connected = self._is_harvest_connected()

        result = {
            "microsoft_365": {
                "connected": ms_connected,
                "message": "Connected" if ms_connected else "Not connected. Run 'python auth_server.py' to authenticate.",
            },
            "harvest": {
                "connected": harvest_connected,
                "message": "Connected" if harvest_connected else "Not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env",
            },
        }

        # Test Harvest connection if configured
        if harvest_connected:
            harvest = self._get_harvest_client()
            test_result = await harvest.test_connection()
            result["harvest"]["details"] = test_result

        return result
