"""Microsoft Copilot and Meeting Transcripts APIs wrapper.

Based on:
- https://learn.microsoft.com/en-us/graph/api/onlinemeeting-list-transcripts
- https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/meeting-insights
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_BETA_URL = "https://graph.microsoft.com/beta"


class MeetingInsightsClient:
    """Client for Microsoft Meeting Transcripts and Copilot AI Insights APIs."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict[str, Any]:
        """Make a request to the Graph API."""
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
                raise PermissionError("Insufficient permissions - check API permissions")
            elif response.status_code == 404:
                return {"error": "Not found", "status": 404}
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", response.text)
                logger.error(f"Graph API error: {response.status_code} - {error_msg}")
                raise Exception(f"Graph API error ({response.status_code}): {error_msg}")

            return response.json() if response.content else {}

    # ==================== ONLINE MEETINGS ====================

    async def get_recent_meetings(
        self,
        days_back: int = 30,
        days_forward: int = 0,
        limit: int = 10,
    ) -> list[dict]:
        """Get online meetings from calendar events."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days_back)
        end = now + timedelta(days=days_forward)

        params = {
            "startDateTime": start.isoformat(),
            "endDateTime": end.isoformat(),
            "$orderby": "start/dateTime desc",
            "$select": "id,subject,start,end,onlineMeeting,isOnlineMeeting,organizer,isOrganizer",
            "$top": 100,
        }

        result = await self._request("GET", f"{GRAPH_BASE_URL}/me/calendarView", params=params)

        meetings = []
        for event in result.get("value", []):
            if not event.get("isOnlineMeeting"):
                continue

            online_meeting = event.get("onlineMeeting", {}) or {}
            join_url = online_meeting.get("joinUrl", "")
            organizer_info = event.get("organizer", {}).get("emailAddress", {})

            meetings.append({
                "event_id": event["id"],
                "subject": event.get("subject", "(No title)"),
                "start": event.get("start", {}).get("dateTime", ""),
                "end": event.get("end", {}).get("dateTime", ""),
                "organizer_name": organizer_info.get("name", ""),
                "organizer_email": organizer_info.get("address", ""),
                "is_organizer": event.get("isOrganizer", False),
                "join_url": join_url,
            })

            if len(meetings) >= limit:
                break

        return meetings

    async def get_meetings_for_date(self, date_str: str, limit: int = 20) -> list[dict]:
        """Get Teams online meetings for a specific date."""
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD format.")

        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        params = {
            "startDateTime": start_of_day.isoformat(),
            "endDateTime": end_of_day.isoformat(),
            "$orderby": "start/dateTime",
            "$select": "id,subject,start,end,onlineMeeting,isOnlineMeeting,organizer,isOrganizer",
            "$top": 50,
        }

        result = await self._request("GET", f"{GRAPH_BASE_URL}/me/calendarView", params=params)

        meetings = []
        for event in result.get("value", []):
            if not event.get("isOnlineMeeting"):
                continue

            online_meeting = event.get("onlineMeeting", {}) or {}
            join_url = online_meeting.get("joinUrl", "")
            organizer_info = event.get("organizer", {}).get("emailAddress", {})

            meetings.append({
                "event_id": event["id"],
                "subject": event.get("subject", "(No title)"),
                "start": event.get("start", {}).get("dateTime", ""),
                "end": event.get("end", {}).get("dateTime", ""),
                "organizer_name": organizer_info.get("name", ""),
                "organizer_email": organizer_info.get("address", ""),
                "is_organizer": event.get("isOrganizer", False),
                "join_url": join_url,
            })

            if len(meetings) >= limit:
                break

        return meetings

    # ==================== MEETING ID RESOLUTION ====================

    def _extract_meeting_info_from_join_url(self, join_url: str) -> dict:
        """Extract meeting info from a Teams join URL."""
        import urllib.parse
        import base64
        import json

        result = {
            "thread_id": None,
            "tenant_id": None,
            "organizer_id": None,
        }

        try:
            # Decode the URL
            decoded = urllib.parse.unquote(join_url)

            # Extract thread ID: 19:meeting_XXXX@thread.v2
            if "meetup-join/" in decoded:
                parts = decoded.split("meetup-join/")[1]
                result["thread_id"] = parts.split("/")[0]
                logger.info(f"Extracted thread ID: {result['thread_id']}")

            # Extract context (contains Tid and Oid)
            if "context=" in decoded:
                context_str = decoded.split("context=")[1].split("&")[0]
                context = json.loads(urllib.parse.unquote(context_str))
                result["tenant_id"] = context.get("Tid")
                result["organizer_id"] = context.get("Oid")
                logger.info(f"Extracted tenant: {result['tenant_id']}, organizer: {result['organizer_id']}")

        except Exception as e:
            logger.warning(f"Could not extract meeting info: {e}")

        return result

    async def get_online_meeting_by_join_url(
        self,
        join_url: str,
        organizer_id: str | None = None,
        subject: str | None = None,
    ) -> dict | None:
        """
        Look up an online meeting by its join URL.
        """
        if not join_url and not subject:
            logger.warning("No join_url or subject provided")
            return None

        logger.info(f"Looking up meeting...")
        if join_url:
            logger.info(f"  join_url: {join_url[:80]}...")
        if subject:
            logger.info(f"  subject: {subject}")

        # Extract info from join URL
        meeting_info = self._extract_meeting_info_from_join_url(join_url) if join_url else {}
        thread_id = meeting_info.get("thread_id")

        # Need to get the actual online meeting ID via the JoinWebUrl filter
        # The join URL must NOT be double-encoded
        if join_url:
            import urllib.parse

            # First decode the URL if it's encoded
            decoded_url = urllib.parse.unquote(join_url)
            logger.info(f"Decoded join URL: {decoded_url[:80]}...")

            # Try the JoinWebUrl filter with properly encoded URL
            try:
                # The filter value needs single quotes, and the URL inside should not be re-encoded
                filter_value = f"JoinWebUrl eq '{decoded_url}'"
                logger.info(f"Trying filter: {filter_value[:100]}...")

                result = await self._request(
                    "GET",
                    f"{GRAPH_BASE_URL}/me/onlineMeetings",
                    params={"$filter": filter_value}
                )

                meetings = result.get("value", [])
                if meetings:
                    meeting = meetings[0]
                    logger.info(f"Found online meeting via filter: {meeting.get('id')}")
                    return meeting
                else:
                    logger.info("No meeting found via JoinWebUrl filter")

            except Exception as e:
                logger.warning(f"JoinWebUrl filter failed: {e}")

            # If filter didn't work, try with organizer context
            if organizer_id:
                try:
                    filter_value = f"JoinWebUrl eq '{decoded_url}'"
                    result = await self._request(
                        "GET",
                        f"{GRAPH_BASE_URL}/users/{organizer_id}/onlineMeetings",
                        params={"$filter": filter_value}
                    )

                    meetings = result.get("value", [])
                    if meetings:
                        meeting = meetings[0]
                        logger.info(f"Found online meeting via organizer filter: {meeting.get('id')}")
                        return meeting

                except Exception as e:
                    logger.warning(f"Organizer JoinWebUrl filter failed: {e}")

        return None

    async def get_organizer_id_from_email(self, email: str) -> str | None:
        """Look up a user's ID by their email address."""
        try:
            result = await self._request("GET", f"{GRAPH_BASE_URL}/users/{email}")
            user_id = result.get("id")
            logger.info(f"Resolved user ID for {email}: {user_id}")
            return user_id
        except Exception as e:
            logger.warning(f"Could not resolve user ID for {email}: {e}")
            return None

    async def get_user_online_meetings(self, limit: int = 50) -> list[dict]:
        """Get all online meetings for the user (meetings they organized)."""
        try:
            # Note: /me/onlineMeetings doesn't support $top, so we fetch all and slice
            result = await self._request("GET", f"{GRAPH_BASE_URL}/me/onlineMeetings")
            meetings = result.get("value", [])[:limit]
            logger.info(f"Retrieved {len(meetings)} online meetings")
            return meetings
        except Exception as e:
            logger.error(f"Failed to get user online meetings: {e}")
            return []

    async def list_online_meetings_with_transcripts(self) -> list[dict]:
        """
        List online meetings and check which ones have transcripts.
        Useful for debugging transcript access issues.
        """
        results = []
        meetings = await self.get_user_online_meetings(limit=20)

        for meeting in meetings:
            meeting_id = meeting.get("id")
            subject = meeting.get("subject", "No subject")

            # Check for transcripts
            transcripts = await self.get_meeting_transcripts(meeting_id)

            results.append({
                "meeting_id": meeting_id,
                "subject": subject,
                "join_url": meeting.get("joinWebUrl", ""),
                "start_time": meeting.get("startDateTime", ""),
                "has_transcripts": len(transcripts) > 0,
                "transcript_count": len(transcripts),
            })

        return results

    # ==================== TRANSCRIPTS ====================

    async def get_user_id(self) -> str | None:
        """Get the current user's ID."""
        try:
            result = await self._request("GET", f"{GRAPH_BASE_URL}/me")
            return result.get("id")
        except Exception as e:
            logger.error(f"Failed to get user ID: {e}")
            return None

    async def get_all_transcripts(self, days_back: int = 30, limit: int = 50) -> list[dict]:
        """
        Get all transcripts by iterating through online meetings.

        Note: getAllTranscripts endpoint requires application permissions,
        so for delegated access we iterate through meetings instead.
        """
        logger.info(f"Getting transcripts for meetings from last {days_back} days...")

        # Get online meetings the user organized
        meetings = await self.get_user_online_meetings(limit=limit)
        logger.info(f"Found {len(meetings)} online meetings to check for transcripts")

        all_transcripts = []
        for meeting in meetings:
            meeting_id = meeting.get("id")
            subject = meeting.get("subject", "No subject")

            transcripts = await self.get_meeting_transcripts(meeting_id)
            if transcripts:
                logger.info(f"Found {len(transcripts)} transcript(s) for '{subject}'")
                for t in transcripts:
                    all_transcripts.append({
                        "id": t.get("id", ""),
                        "meeting_id": meeting_id,
                        "meeting_subject": subject,
                        "created": t.get("created", ""),
                        "start_time": meeting.get("startDateTime", ""),
                    })

        logger.info(f"Found {len(all_transcripts)} total transcripts across all meetings")
        return all_transcripts

    async def get_meeting_transcripts(self, meeting_id: str) -> list[dict]:
        """Get available transcripts for a specific meeting."""
        url = f"{GRAPH_BASE_URL}/me/onlineMeetings/{meeting_id}/transcripts"

        try:
            result = await self._request("GET", url)

            if "error" in result:
                logger.warning(f"No transcripts found for meeting {meeting_id}")
                return []

            transcripts = []
            for t in result.get("value", []):
                transcripts.append({
                    "id": t.get("id", ""),
                    "meeting_id": meeting_id,
                    "created": t.get("createdDateTime", ""),
                })

            logger.info(f"Found {len(transcripts)} transcripts for meeting {meeting_id}")
            return transcripts

        except Exception as e:
            logger.error(f"Failed to get transcripts for meeting {meeting_id}: {e}")
            return []

    async def get_transcript_content(self, meeting_id: str, transcript_id: str) -> str:
        """Get the content of a specific transcript in WebVTT format."""
        url = f"{GRAPH_BASE_URL}/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "text/vtt",
                },
                params={"$format": "text/vtt"},
                timeout=60.0,
            )

            if response.status_code == 200:
                logger.info(f"Retrieved transcript content for {transcript_id}")
                return response.text
            elif response.status_code == 404:
                logger.warning(f"Transcript content not found: {transcript_id}")
                return ""
            else:
                logger.error(f"Failed to get transcript content: {response.status_code}")
                raise Exception(f"Failed to get transcript: {response.status_code}")

    # ==================== COPILOT AI INSIGHTS ====================
    # Docs: https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/meeting-insights/onlinemeeting-list-aiinsights

    async def get_meeting_ai_insights(self, meeting_id: str) -> list[dict]:
        """
        Get AI-generated insights for a meeting (requires Copilot license).

        Endpoint: GET /copilot/users/{userId}/onlineMeetings/{onlineMeetingId}/aiInsights

        Returns callAiInsight objects containing:
        - actionItems: Collection of action items
        - meetingNotes: Collection of meeting notes with title, text, subpoints
        - createdDateTime, endDateTime
        """
        # Get user ID - the API requires user ID, not 'me'
        user_id = await self.get_user_id()
        if not user_id:
            logger.error("Could not get user ID for AI insights")
            return []

        # AI Insights API is now GA in v1.0 (December 2025)
        url = f"{GRAPH_BASE_URL}/copilot/users/{user_id}/onlineMeetings/{meeting_id}/aiInsights"
        logger.info(f"Fetching AI insights from: {url}")

        try:
            result = await self._request("GET", url)

            if "error" in result:
                logger.warning(f"AI insights error: {result.get('error')}")
                return []

            insights = []
            for insight in result.get("value", []):
                # Parse the callAiInsight structure
                parsed = {
                    "id": insight.get("id", ""),
                    "created": insight.get("createdDateTime", ""),
                    "end": insight.get("endDateTime", ""),
                    "call_id": insight.get("callId", ""),
                }

                # Extract action items
                action_items = insight.get("actionItems", [])
                if action_items:
                    parsed["action_items"] = [
                        {"text": item.get("text", "")} for item in action_items
                    ]

                # Extract meeting notes (structured with title, text, subpoints)
                meeting_notes = insight.get("meetingNotes", [])
                if meeting_notes:
                    parsed["meeting_notes"] = []
                    for note in meeting_notes:
                        note_data = {
                            "title": note.get("title", ""),
                            "text": note.get("text", ""),
                        }
                        subpoints = note.get("subpoints", [])
                        if subpoints:
                            note_data["subpoints"] = [
                                {"title": sp.get("title", ""), "text": sp.get("text", "")}
                                for sp in subpoints
                            ]
                        parsed["meeting_notes"].append(note_data)

                insights.append(parsed)

            logger.info(f"Found {len(insights)} AI insights for meeting {meeting_id}")
            return insights

        except PermissionError as e:
            logger.warning(f"Copilot AI Insights permission error: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get AI insights: {e}")
            return []

    # ==================== MEETING SUMMARY ====================

    async def get_meeting_summary(
        self,
        meeting_id: str | None = None,
        join_url: str | None = None,
        organizer_email: str | None = None,
        subject: str | None = None,
    ) -> dict:
        """
        Get a comprehensive meeting summary.

        Tries multiple methods to get meeting data:
        1. Resolve meeting ID from join URL if needed
        2. Try to get Copilot AI Insights (action items, meeting notes)
        3. Try to get transcript content as fallback
        """
        result = {
            "meeting_id": meeting_id,
            "join_url": join_url,
            "has_copilot_insights": False,
            "has_transcript": False,
            "action_items": [],
            "meeting_notes": [],
            "transcript_preview": "",
            "error": None,
        }

        # Step 1: If we only have subject, search calendar for the meeting first
        if not join_url and subject:
            logger.info(f"No join_url provided, searching calendar for: {subject}")
            # Search recent meetings for the subject
            recent = await self.get_recent_meetings(days_back=30, limit=50)
            for meeting in recent:
                if subject.lower() in meeting.get("subject", "").lower():
                    join_url = meeting.get("join_url")
                    result["subject"] = meeting.get("subject")
                    result["found_in_calendar"] = True
                    logger.info(f"Found meeting in calendar: {meeting.get('subject')}")
                    logger.info(f"Join URL: {join_url[:80] if join_url else 'None'}...")
                    break

        # Step 2: Resolve meeting ID from join URL
        if not meeting_id and join_url:
            logger.info(f"Resolving meeting ID from join URL...")

            # Try to get organizer ID if email provided
            organizer_id = None
            if organizer_email:
                organizer_id = await self.get_organizer_id_from_email(organizer_email)
                result["organizer_email"] = organizer_email
                result["organizer_id"] = organizer_id

            online_meeting = await self.get_online_meeting_by_join_url(
                join_url,
                organizer_id,
                subject
            )
            if online_meeting:
                meeting_id = online_meeting.get("id")
                result["meeting_id"] = meeting_id
                if not result.get("subject"):
                    result["subject"] = online_meeting.get("subject", "")
                logger.info(f"Resolved meeting ID: {meeting_id}")

        # Step 2: If still no meeting ID, report error
        if not meeting_id:
            result["error"] = (
                "Could not resolve meeting ID. This can happen if:\n"
                "1. You are not the meeting organizer\n"
                "2. The meeting was not created via calendar\n"
                "3. The meeting has expired\n\n"
                "Use 'list_meetings_with_transcripts' to see available meetings."
            )
            return result

        # Step 3: Try to get Copilot AI insights
        insights = await self.get_meeting_ai_insights(meeting_id)
        if insights:
            result["has_copilot_insights"] = True

            # Extract action items and meeting notes from all insights
            for insight in insights:
                if "action_items" in insight:
                    result["action_items"].extend(insight["action_items"])
                if "meeting_notes" in insight:
                    result["meeting_notes"].extend(insight["meeting_notes"])

            # Create a formatted summary
            summary_parts = []
            if result["action_items"]:
                summary_parts.append("**Action Items:**")
                for item in result["action_items"]:
                    summary_parts.append(f"- {item.get('text', '')}")

            if result["meeting_notes"]:
                summary_parts.append("\n**Meeting Notes:**")
                for note in result["meeting_notes"]:
                    if note.get("title"):
                        summary_parts.append(f"\n### {note['title']}")
                    if note.get("text"):
                        summary_parts.append(note["text"])
                    for subpoint in note.get("subpoints", []):
                        if subpoint.get("title"):
                            summary_parts.append(f"  - **{subpoint['title']}**: {subpoint.get('text', '')}")
                        elif subpoint.get("text"):
                            summary_parts.append(f"  - {subpoint['text']}")

            result["formatted_summary"] = "\n".join(summary_parts)

        # Step 4: Try to get transcript as fallback or supplement
        transcripts = await self.get_meeting_transcripts(meeting_id)
        if transcripts:
            result["has_transcript"] = True
            result["transcript_count"] = len(transcripts)

            # Get the first transcript's content
            try:
                transcript_content = await self.get_transcript_content(
                    meeting_id, transcripts[0]["id"]
                )
                # Return first 3000 chars as preview
                result["transcript_preview"] = transcript_content[:3000] if transcript_content else ""
            except Exception as e:
                logger.error(f"Failed to get transcript content: {e}")
                result["transcript_error"] = str(e)

        if not result["has_transcript"] and not result["has_copilot_insights"]:
            result["error"] = (
                "No transcript or AI insights available for this meeting. "
                "Possible reasons:\n"
                "1. Transcription/recording was not enabled during the meeting\n"
                "2. You don't have permission (must be meeting organizer)\n"
                "3. AI insights take up to 4 hours to be available after meeting ends\n"
                "4. You need a Microsoft 365 Copilot license for AI insights"
            )

        return result

    async def get_all_available_transcripts(self) -> dict:
        """
        Get all available transcripts for the user.
        Useful for discovering what transcript data is accessible.
        """
        result = {
            "transcripts": [],
            "organized_meetings": 0,
            "count": 0,
            "error": None,
            "note": None,
        }

        try:
            # First, show how many meetings we're checking
            meetings = await self.get_user_online_meetings(limit=50)
            result["organized_meetings"] = len(meetings)

            if not meetings:
                result["note"] = (
                    "No online meetings found that you organized. "
                    "The Graph API only allows access to transcripts for meetings you organized, "
                    "not meetings you attended."
                )
                return result

            transcripts = await self.get_all_transcripts(limit=100)
            result["transcripts"] = transcripts
            result["count"] = len(transcripts)

            if not transcripts:
                result["note"] = (
                    f"Checked {len(meetings)} meetings you organized but found no transcripts. "
                    "Possible reasons:\n"
                    "1. Transcription was not enabled during these meetings\n"
                    "2. The transcripts haven't been processed yet\n"
                    "3. Transcripts may have expired (meetings older than retention period)"
                )

        except Exception as e:
            result["error"] = f"Failed to fetch transcripts: {str(e)}"

        return result

    # ==================== MEETING-SPECIFIC HELPERS ====================

    async def get_meeting_action_items(self, meeting_id: str) -> dict:
        """Get just the action items from a meeting (simpler than full summary)."""
        insights = await self.get_meeting_ai_insights(meeting_id)

        action_items = []
        for insight in insights:
            if "action_items" in insight:
                action_items.extend(insight["action_items"])

        return {
            "meeting_id": meeting_id,
            "action_items": action_items,
            "count": len(action_items),
            "has_insights": len(insights) > 0,
        }

    async def get_meeting_notes_only(self, meeting_id: str) -> dict:
        """Get just the meeting notes without transcript."""
        insights = await self.get_meeting_ai_insights(meeting_id)

        meeting_notes = []
        for insight in insights:
            if "meeting_notes" in insight:
                meeting_notes.extend(insight["meeting_notes"])

        return {
            "meeting_id": meeting_id,
            "meeting_notes": meeting_notes,
            "count": len(meeting_notes),
            "has_insights": len(insights) > 0,
        }

    async def get_meeting_attendance(self, meeting_id: str) -> dict:
        """Get attendance report for a meeting (must be meeting organizer)."""
        user_id = await self.get_user_id()
        if not user_id:
            return {"error": "Could not get user ID"}

        url = f"{GRAPH_BASE_URL}/users/{user_id}/onlineMeetings/{meeting_id}/attendanceReports"

        try:
            result = await self._request("GET", url)
            reports = result.get("value", [])

            if not reports:
                return {
                    "meeting_id": meeting_id,
                    "has_attendance": False,
                    "note": "No attendance report available. You must be the meeting organizer.",
                }

            # Get the most recent attendance report
            report = reports[0]
            report_id = report.get("id", "")

            # Get attendance records
            records_url = f"{url}/{report_id}/attendanceRecords"
            records_result = await self._request("GET", records_url)

            attendees = []
            for record in records_result.get("value", []):
                attendees.append({
                    "email": record.get("emailAddress", ""),
                    "display_name": record.get("identity", {}).get("displayName", ""),
                    "total_duration_seconds": record.get("totalAttendanceInSeconds", 0),
                    "role": record.get("role", ""),
                })

            return {
                "meeting_id": meeting_id,
                "has_attendance": True,
                "total_attendees": len(attendees),
                "meeting_start": report.get("meetingStartDateTime", ""),
                "meeting_end": report.get("meetingEndDateTime", ""),
                "attendees": attendees,
            }

        except Exception as e:
            logger.error(f"Failed to get meeting attendance: {e}")
            return {"error": str(e), "meeting_id": meeting_id}

    async def get_meeting_recording(self, meeting_id: str) -> dict:
        """Check if meeting has recording available."""
        user_id = await self.get_user_id()
        if not user_id:
            return {"error": "Could not get user ID"}

        url = f"{GRAPH_BASE_URL}/users/{user_id}/onlineMeetings/{meeting_id}/recordings"

        try:
            result = await self._request("GET", url)
            recordings = result.get("value", [])

            if not recordings:
                return {
                    "meeting_id": meeting_id,
                    "has_recording": False,
                    "note": "No recording available for this meeting.",
                }

            recording = recordings[0]
            return {
                "meeting_id": meeting_id,
                "has_recording": True,
                "recording_id": recording.get("id", ""),
                "created": recording.get("createdDateTime", ""),
                "content_url": recording.get("recordingContentUrl", ""),
            }

        except Exception as e:
            logger.error(f"Failed to get meeting recording: {e}")
            return {"error": str(e), "meeting_id": meeting_id}

    # ==================== COPILOT RETRIEVAL API ====================
    # Docs: https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/retrieval/copilotroot-retrieval

    async def copilot_search(self, query: str, max_results: int = 10) -> dict:
        """
        Semantic search across M365 using Copilot's index.

        Requires: Files.Read.All and Sites.Read.All permissions.
        Note: This API is in public preview (beta endpoint).
        """
        url = f"{GRAPH_BETA_URL}/copilot/retrieval"

        body = {
            "queryString": query,
            "top": min(max_results, 10),  # API max is 10
        }

        try:
            result = await self._request("POST", url, json_data=body)

            documents = []
            for doc in result.get("value", []):
                documents.append({
                    "id": doc.get("id", ""),
                    "title": doc.get("title", ""),
                    "web_url": doc.get("webUrl", ""),
                    "snippet": doc.get("snippet", ""),
                    "source_type": doc.get("sourceType", ""),
                    "relevance_score": doc.get("relevanceScore", 0),
                    "last_modified": doc.get("lastModifiedDateTime", ""),
                })

            return {
                "query": query,
                "documents": documents,
                "count": len(documents),
            }

        except PermissionError as e:
            return {
                "error": "Insufficient permissions. Copilot Retrieval API requires Files.Read.All and Sites.Read.All.",
                "details": str(e),
            }
        except Exception as e:
            logger.error(f"Copilot search failed: {e}")
            return {"error": str(e), "query": query}

    async def copilot_search_sharepoint(self, query: str, site_url: str | None = None, max_results: int = 10) -> dict:
        """
        Semantic search specifically in SharePoint sites using Copilot's index.

        Args:
            query: The search query
            site_url: Optional SharePoint site URL to limit search to
            max_results: Maximum number of results (max 10)
        """
        url = f"{GRAPH_BETA_URL}/copilot/retrieval"

        body = {
            "queryString": query,
            "top": min(max_results, 10),
            "sources": {
                "sharePoint": {
                    "includePersonalSites": False,
                }
            }
        }

        if site_url:
            body["sources"]["sharePoint"]["siteUrls"] = [site_url]

        try:
            result = await self._request("POST", url, json_data=body)

            documents = []
            for doc in result.get("value", []):
                documents.append({
                    "id": doc.get("id", ""),
                    "title": doc.get("title", ""),
                    "web_url": doc.get("webUrl", ""),
                    "snippet": doc.get("snippet", ""),
                    "site_url": doc.get("siteUrl", ""),
                    "relevance_score": doc.get("relevanceScore", 0),
                    "last_modified": doc.get("lastModifiedDateTime", ""),
                })

            return {
                "query": query,
                "site_filter": site_url,
                "documents": documents,
                "count": len(documents),
            }

        except PermissionError as e:
            return {
                "error": "Insufficient permissions. Requires Files.Read.All and Sites.Read.All.",
                "details": str(e),
            }
        except Exception as e:
            logger.error(f"Copilot SharePoint search failed: {e}")
            return {"error": str(e), "query": query}

    async def find_transcript_for_calendar_meeting(self, event_id: str, join_url: str) -> dict:
        """
        Try to find transcript for a calendar meeting.
        This handles the case where we have a calendar event but need the online meeting ID.
        """
        result = {
            "event_id": event_id,
            "join_url": join_url,
            "meeting_id": None,
            "has_transcript": False,
            "transcript_preview": "",
            "error": None,
        }

        # Try to find the online meeting by join URL
        online_meeting = await self.get_online_meeting_by_join_url(join_url)

        if not online_meeting:
            result["error"] = (
                "Could not find online meeting details. "
                "This usually means you're not the meeting organizer. "
                "Graph API only allows transcript access to meeting organizers."
            )
            return result

        meeting_id = online_meeting.get("id")
        result["meeting_id"] = meeting_id
        result["subject"] = online_meeting.get("subject", "")

        # Now try to get transcripts
        transcripts = await self.get_meeting_transcripts(meeting_id)
        if transcripts:
            result["has_transcript"] = True
            result["transcript_count"] = len(transcripts)

            # Get content
            try:
                content = await self.get_transcript_content(meeting_id, transcripts[0]["id"])
                result["transcript_preview"] = content[:3000] if content else ""
            except Exception as e:
                result["transcript_error"] = str(e)
        else:
            result["error"] = (
                "No transcripts found for this meeting. "
                "Was transcription enabled during the meeting?"
            )

        return result
