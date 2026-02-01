"""Microsoft Graph API wrapper."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class GraphClient:
    """Client for Microsoft Graph API."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict[str, Any]:
        """Make a request to the Graph API."""
        url = f"{GRAPH_BASE_URL}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=30.0,
            )

            if response.status_code == 401:
                raise PermissionError("Access token expired or invalid")
            elif response.status_code == 403:
                raise PermissionError("Insufficient permissions for this operation")
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", response.text)
                raise Exception(f"Graph API error ({response.status_code}): {error_msg}")

            return response.json() if response.content else {}

    # ==================== EMAIL ====================

    async def get_emails(
        self,
        limit: int = 10,
        search: str | None = None,
        folder: str = "inbox",
    ) -> list[dict]:
        """Get recent emails, optionally filtered by search query."""
        params = {
            "$top": limit,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead,importance",
        }

        if search:
            params["$search"] = f'"{search}"'

        endpoint = f"/me/mailFolders/{folder}/messages"
        result = await self._request("GET", endpoint, params=params)

        emails = []
        for msg in result.get("value", []):
            emails.append({
                "id": msg["id"],
                "subject": msg.get("subject", "(No subject)"),
                "from": msg.get("from", {}).get("emailAddress", {}).get("address", "Unknown"),
                "from_name": msg.get("from", {}).get("emailAddress", {}).get("name", ""),
                "received": msg.get("receivedDateTime", ""),
                "preview": msg.get("bodyPreview", "")[:200],
                "is_read": msg.get("isRead", False),
                "importance": msg.get("importance", "normal"),
            })

        return emails

    async def get_email(self, email_id: str) -> dict:
        """Get a specific email by ID."""
        params = {
            "$select": "id,subject,from,toRecipients,receivedDateTime,body,isRead,importance,hasAttachments",
        }

        result = await self._request("GET", f"/me/messages/{email_id}", params=params)

        return {
            "id": result["id"],
            "subject": result.get("subject", "(No subject)"),
            "from": result.get("from", {}).get("emailAddress", {}).get("address", "Unknown"),
            "from_name": result.get("from", {}).get("emailAddress", {}).get("name", ""),
            "to": [r.get("emailAddress", {}).get("address", "") for r in result.get("toRecipients", [])],
            "received": result.get("receivedDateTime", ""),
            "body": result.get("body", {}).get("content", ""),
            "body_type": result.get("body", {}).get("contentType", "text"),
            "is_read": result.get("isRead", False),
            "importance": result.get("importance", "normal"),
            "has_attachments": result.get("hasAttachments", False),
        }

    # ==================== CALENDAR ====================

    async def get_calendar_events(self, days: int = 7) -> list[dict]:
        """Get upcoming calendar events."""
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)

        params = {
            "startDateTime": now.isoformat(),
            "endDateTime": end.isoformat(),
            "$orderby": "start/dateTime",
            "$select": "id,subject,start,end,location,organizer,attendees,isOnlineMeeting,onlineMeetingUrl,bodyPreview",
            "$top": 50,
        }

        result = await self._request("GET", "/me/calendarView", params=params)

        events = []
        for event in result.get("value", []):
            start = event.get("start", {})
            end = event.get("end", {})

            events.append({
                "id": event["id"],
                "subject": event.get("subject", "(No title)"),
                "start": start.get("dateTime", ""),
                "start_timezone": start.get("timeZone", "UTC"),
                "end": end.get("dateTime", ""),
                "end_timezone": end.get("timeZone", "UTC"),
                "location": event.get("location", {}).get("displayName", ""),
                "organizer": event.get("organizer", {}).get("emailAddress", {}).get("name", ""),
                "organizer_email": event.get("organizer", {}).get("emailAddress", {}).get("address", ""),
                "attendees": [
                    {
                        "name": a.get("emailAddress", {}).get("name", ""),
                        "email": a.get("emailAddress", {}).get("address", ""),
                        "status": a.get("status", {}).get("response", ""),
                    }
                    for a in event.get("attendees", [])
                ],
                "is_online": event.get("isOnlineMeeting", False),
                "online_url": event.get("onlineMeetingUrl", ""),
                "description": event.get("bodyPreview", "")[:200],
            })

        return events

    async def get_today_events(self) -> list[dict]:
        """Get today's calendar events."""
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        params = {
            "startDateTime": start_of_day.isoformat(),
            "endDateTime": end_of_day.isoformat(),
            "$orderby": "start/dateTime",
            "$select": "id,subject,start,end,location,isOnlineMeeting,onlineMeetingUrl",
        }

        result = await self._request("GET", "/me/calendarView", params=params)

        events = []
        for event in result.get("value", []):
            start = event.get("start", {})
            end = event.get("end", {})

            events.append({
                "id": event["id"],
                "subject": event.get("subject", "(No title)"),
                "start": start.get("dateTime", ""),
                "end": end.get("dateTime", ""),
                "location": event.get("location", {}).get("displayName", ""),
                "is_online": event.get("isOnlineMeeting", False),
                "online_url": event.get("onlineMeetingUrl", ""),
            })

        return events

    # ==================== TEAMS ====================

    async def get_teams_chats(self, limit: int = 10) -> list[dict]:
        """Get recent Teams chats."""
        params = {
            "$top": limit,
            "$orderby": "lastMessagePreview/createdDateTime desc",
            "$expand": "lastMessagePreview",
        }

        result = await self._request("GET", "/me/chats", params=params)

        chats = []
        for chat in result.get("value", []):
            last_msg = chat.get("lastMessagePreview", {})

            chats.append({
                "id": chat["id"],
                "topic": chat.get("topic", ""),
                "chat_type": chat.get("chatType", ""),
                "last_message": last_msg.get("body", {}).get("content", "")[:100] if last_msg else "",
                "last_message_from": last_msg.get("from", {}).get("user", {}).get("displayName", "") if last_msg else "",
                "last_message_time": last_msg.get("createdDateTime", "") if last_msg else "",
            })

        return chats

    async def get_chat_messages(self, chat_id: str, limit: int = 20) -> list[dict]:
        """Get messages from a Teams chat."""
        params = {
            "$top": limit,
            "$orderby": "createdDateTime desc",
        }

        result = await self._request("GET", f"/me/chats/{chat_id}/messages", params=params)

        messages = []
        for msg in result.get("value", []):
            from_user = msg.get("from", {})
            user_info = from_user.get("user", {}) if from_user else {}

            messages.append({
                "id": msg["id"],
                "content": msg.get("body", {}).get("content", ""),
                "content_type": msg.get("body", {}).get("contentType", "text"),
                "from": user_info.get("displayName", "Unknown"),
                "from_email": user_info.get("email", ""),
                "created": msg.get("createdDateTime", ""),
                "message_type": msg.get("messageType", ""),
            })

        return messages

    # ==================== FILES ====================

    async def search_files(self, query: str, limit: int = 10) -> list[dict]:
        """Search files in OneDrive and SharePoint."""
        # Use the search API
        search_body = {
            "requests": [
                {
                    "entityTypes": ["driveItem"],
                    "query": {"queryString": query},
                    "from": 0,
                    "size": limit,
                }
            ]
        }

        result = await self._request("POST", "/search/query", json_data=search_body)

        files = []
        for response in result.get("value", []):
            for hit in response.get("hitsContainers", [{}])[0].get("hits", []):
                resource = hit.get("resource", {})
                files.append({
                    "id": resource.get("id", ""),
                    "name": resource.get("name", ""),
                    "web_url": resource.get("webUrl", ""),
                    "size": resource.get("size", 0),
                    "created": resource.get("createdDateTime", ""),
                    "modified": resource.get("lastModifiedDateTime", ""),
                    "created_by": resource.get("createdBy", {}).get("user", {}).get("displayName", ""),
                })

        return files

    async def get_recent_files(self, limit: int = 10) -> list[dict]:
        """Get recently accessed files."""
        params = {
            "$top": limit,
            "$orderby": "lastAccessedDateTime desc",
        }

        result = await self._request("GET", "/me/drive/recent", params=params)

        files = []
        for item in result.get("value", []):
            files.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "web_url": item.get("webUrl", ""),
                "size": item.get("size", 0),
                "modified": item.get("lastModifiedDateTime", ""),
            })

        return files

    # ==================== USER INFO ====================

    async def get_me(self) -> dict:
        """Get the current user's profile."""
        result = await self._request("GET", "/me")

        return {
            "id": result.get("id", ""),
            "name": result.get("displayName", ""),
            "email": result.get("mail", result.get("userPrincipalName", "")),
            "job_title": result.get("jobTitle", ""),
            "department": result.get("department", ""),
            "office": result.get("officeLocation", ""),
        }
