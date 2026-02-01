"""Microsoft Copilot APIs wrapper (Phase 2 stub)."""

# This will be implemented in Phase 2
# Key functionality (requires E5 Copilot license):
# - Meeting Insights: AI summaries of Teams meetings
# - Retrieval API: Search across M365 content


class CopilotClient:
    """Client for Microsoft Copilot APIs."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    async def get_meeting_insights(self, meeting_id: str) -> dict:
        """Get AI-generated insights for a Teams meeting."""
        raise NotImplementedError("Phase 2")

    async def get_meeting_transcript(self, meeting_id: str) -> str:
        """Get the transcript of a Teams meeting."""
        raise NotImplementedError("Phase 2")

    async def get_meeting_summary(self, meeting_id: str) -> str:
        """Get the AI summary of a Teams meeting."""
        raise NotImplementedError("Phase 2")

    async def search_content(self, query: str, limit: int = 10) -> list[dict]:
        """Search across M365 content using Copilot Retrieval API."""
        raise NotImplementedError("Phase 2")
