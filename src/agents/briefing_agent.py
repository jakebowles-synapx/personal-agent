"""Briefing agent - generates morning summaries."""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.agents.base import BaseAgent
from src.config import settings

if TYPE_CHECKING:
    from src.agents.message_bus import MessageBus
    from src.knowledge.manager import KnowledgeManager
    from src.memory.mem0_client import MemoryClient
    from src.llm import AzureOpenAIClient
    from src.microsoft.auth import MicrosoftAuth
    from src.agent.tools import ToolExecutor

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default"

BRIEFING_PROMPT = """Generate a morning briefing based ONLY on the actual data provided below. Do not invent or assume information not present in the data.

IMPORTANT RULES:
- Only summarize what is actually in the provided data
- If no events are listed, say "No scheduled events"
- If no emails are shown, say "No recent emails"
- Do not create fake "Priority Items" or "Action Items" unless they are explicitly mentioned in the data
- Be factual and concise

Structure:

## Schedule
List the actual calendar events provided (with times and locations). If none, state that.

## Emails
Summarize the actual emails provided, highlighting any unread or important ones. If none, state that.

## Organization Context
If team/project/strategy information is provided, briefly mention key points relevant to today.

Keep it brief and factual. Only include information that appears in the data below.
"""


class BriefingAgent(BaseAgent):
    """
    Agent that generates morning briefings.

    Runs daily at 7am to create a summary of:
    - Today's calendar
    - Important emails
    - Outstanding action items
    - Key priorities
    """

    name = "briefing"
    description = "Generates daily morning briefings"

    def __init__(
        self,
        message_bus: "MessageBus",
        knowledge_manager: "KnowledgeManager | None" = None,
        memory_client: "MemoryClient | None" = None,
        llm_client: "AzureOpenAIClient | None" = None,
        auth: "MicrosoftAuth | None" = None,
        tool_executor: "ToolExecutor | None" = None,
    ) -> None:
        super().__init__(
            message_bus=message_bus,
            knowledge_manager=knowledge_manager,
            memory_client=memory_client,
            llm_client=llm_client,
        )
        self.auth = auth
        self.tool_executor = tool_executor

    async def execute(self) -> dict:
        """Generate the morning briefing."""
        logger.info("Generating morning briefing...")

        # Check if Microsoft is connected
        if not self.auth or not self.auth.is_connected(DEFAULT_USER_ID):
            logger.warning("Microsoft not connected, creating limited briefing")
            self.create_recommendation(
                title="Connect Microsoft 365",
                content="Connect your Microsoft 365 account to receive personalized morning briefings with your calendar, emails, and Teams messages.",
                priority="normal",
            )
            return {
                "summary": "Limited briefing - Microsoft not connected",
                "items_processed": 0,
            }

        # Gather information
        context_parts = []
        items_processed = 0

        # Get upcoming events (today and tomorrow)
        try:
            events = await self._get_upcoming_events()
            if events:
                context_parts.append(f"## Upcoming Calendar Events\n{self._format_events(events)}")
                items_processed += len(events)
            else:
                context_parts.append("## Upcoming Calendar Events\nNo events scheduled for today or tomorrow.")
        except Exception as e:
            logger.warning(f"Failed to get calendar events: {e}")
            context_parts.append("## Upcoming Calendar Events\nCould not retrieve calendar.")

        # Get recent emails (all recent, not just unread)
        try:
            emails = await self._get_recent_emails()
            if emails:
                context_parts.append(f"## Recent Emails ({len(emails)} messages)\n{self._format_emails(emails)}")
                items_processed += len(emails)
            else:
                context_parts.append("## Recent Emails\nNo recent emails.")
        except Exception as e:
            logger.warning(f"Failed to get emails: {e}")

        # Get fixed knowledge (strategy/priorities)
        try:
            knowledge = await self._get_knowledge_context()
            if knowledge:
                context_parts.append(f"## Organization Context\n{knowledge}")
        except Exception as e:
            logger.warning(f"Failed to get knowledge: {e}")

        if not context_parts:
            logger.warning("No context gathered for briefing")
            return {
                "summary": "No information available for briefing",
                "items_processed": 0,
            }

        # Generate briefing using LLM
        context = "\n\n".join(context_parts)
        briefing = await self._generate_briefing(context)

        # Create recommendation with the briefing
        self.create_recommendation(
            title=f"Morning Briefing - {datetime.now(timezone.utc).strftime('%d %B %Y')}",
            content=briefing,
            priority="high",
            metadata={
                "type": "briefing",
                "events_count": items_processed,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {
            "summary": f"Generated briefing with {items_processed} items",
            "items_processed": items_processed,
        }

    async def _get_upcoming_events(self) -> list[dict]:
        """Get calendar events for today and tomorrow."""
        if not self.tool_executor:
            return []

        # Get events for the next 2 days
        result = await self.tool_executor.execute(
            user_id=DEFAULT_USER_ID,
            tool_name="get_calendar_events",
            arguments={"days": 2, "past_days": 0},
        )

        return result.get("events", [])

    async def _get_recent_emails(self, limit: int = 10) -> list[dict]:
        """Get recent emails (all, not filtered)."""
        if not self.tool_executor:
            return []

        result = await self.tool_executor.execute(
            user_id=DEFAULT_USER_ID,
            tool_name="get_emails",
            arguments={"limit": limit},
        )

        return result.get("emails", [])

    async def _get_knowledge_context(self) -> str:
        """Get relevant knowledge context for briefing."""
        if not self.knowledge_manager:
            return ""

        # Get all knowledge to provide context
        parts = []

        # Get team info
        team_items = self.knowledge_manager.list_by_category("team")
        if team_items:
            parts.append("**Team:**")
            for item in team_items[:5]:
                parts.append(f"- {item['title']}: {item['content'][:100]}")

        # Get strategy info
        strategy_items = self.knowledge_manager.list_by_category("strategy")
        if strategy_items:
            parts.append("\n**Strategy/Priorities:**")
            for item in strategy_items[:5]:
                parts.append(f"- {item['title']}: {item['content'][:100]}")

        # Get projects info
        project_items = self.knowledge_manager.list_by_category("projects")
        if project_items:
            parts.append("\n**Active Projects:**")
            for item in project_items[:5]:
                parts.append(f"- {item['title']}: {item['content'][:100]}")

        return "\n".join(parts) if parts else ""

    def _format_events(self, events: list[dict]) -> str:
        """Format calendar events for the prompt."""
        if not events:
            return "No events scheduled."

        lines = []
        for event in events:
            # GraphClient returns start as a string directly (ISO format)
            start = event.get("start", "")
            if start:
                # Format as "Mon 01 Feb 09:00"
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    formatted = dt.strftime("%a %d %b %H:%M")
                except Exception:
                    formatted = start[:16]
            else:
                formatted = "TBD"

            subject = event.get("subject", "Untitled")
            location = event.get("location", "")
            location_str = f" @ {location}" if location else ""
            lines.append(f"- {formatted}: {subject}{location_str}")

        return "\n".join(lines)

    def _format_emails(self, emails: list[dict]) -> str:
        """Format emails for the prompt."""
        if not emails:
            return "No recent emails."

        lines = []
        for email in emails[:10]:
            sender = email.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
            subject = email.get("subject", "No subject")
            is_read = email.get("isRead", True)
            importance = email.get("importance", "normal")

            # Status indicators
            status = []
            if not is_read:
                status.append("UNREAD")
            if importance == "high":
                status.append("IMPORTANT")
            status_str = f" [{', '.join(status)}]" if status else ""

            preview = email.get("bodyPreview", "")[:80]
            lines.append(f"- {sender}: {subject}{status_str}\n  {preview}...")

        return "\n".join(lines)

    async def _generate_briefing(self, context: str) -> str:
        """Generate the briefing text using LLM."""
        if not self.llm_client:
            return context  # Return raw context if no LLM

        today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")

        messages = [
            {"role": "system", "content": BRIEFING_PROMPT},
            {
                "role": "user",
                "content": f"Today is {today}. Here is the information for the briefing:\n\n{context}",
            },
        ]

        try:
            return await self.llm_client.chat(messages=messages)
        except Exception as e:
            logger.error(f"Failed to generate briefing: {e}")
            return f"# Morning Briefing - {today}\n\n{context}"
