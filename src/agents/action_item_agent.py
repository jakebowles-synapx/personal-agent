"""Action item agent - extracts and tracks action items."""

import logging
from datetime import datetime, timezone, timedelta
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

ACTION_ITEM_PROMPT = """You are analyzing content to extract action items.

For each piece of content, identify:
1. Clear action items assigned to the user or their team
2. Deadlines if mentioned
3. Priority level (high, normal, low) based on urgency
4. Context about what the action item relates to

Format your response as a JSON array of action items:
[
  {
    "title": "Brief description of the action",
    "details": "Full context and details",
    "deadline": "Date if mentioned (YYYY-MM-DD) or null",
    "priority": "high|normal|low",
    "source": "Where this came from (email, meeting, etc.)"
  }
]

Only extract genuine action items - things that need to be done. Skip:
- FYI information
- Completed items
- Vague suggestions without clear actions

If no action items are found, return an empty array: []
"""


class ActionItemAgent(BaseAgent):
    """
    Agent that extracts action items from meetings and emails.

    Runs every 2 hours to:
    - Process recent meeting transcripts
    - Scan recent emails for action items
    - Create recommendations for new action items
    """

    name = "action_item"
    description = "Extracts action items from meetings and emails"

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
        self._processed_ids: set[str] = set()  # Track processed content

    async def execute(self) -> dict:
        """Extract action items from recent content."""
        logger.info("Extracting action items...")

        # Check if Microsoft is connected
        if not self.auth or not self.auth.is_connected(DEFAULT_USER_ID):
            logger.warning("Microsoft not connected, skipping action item extraction")
            return {
                "summary": "Microsoft not connected",
                "items_processed": 0,
            }

        items_found = 0
        content_processed = 0

        # Process recent emails
        try:
            email_items = await self._process_emails()
            items_found += email_items
            content_processed += 1
        except Exception as e:
            logger.error(f"Failed to process emails: {e}")

        # Process recent meetings with transcripts
        try:
            meeting_items = await self._process_meetings()
            items_found += meeting_items
            content_processed += 1
        except Exception as e:
            logger.error(f"Failed to process meetings: {e}")

        return {
            "summary": f"Extracted {items_found} action items from {content_processed} sources",
            "items_processed": items_found,
        }

    async def _process_emails(self) -> int:
        """Process recent emails for action items."""
        if not self.tool_executor:
            return 0

        # Get recent emails (last 4 hours worth, since we run every 2 hours)
        result = await self.tool_executor.execute(
            user_id=DEFAULT_USER_ID,
            tool_name="get_emails",
            arguments={"limit": 20},
        )

        emails = result.get("emails", [])
        if not emails:
            return 0

        # Filter to unprocessed emails
        new_emails = []
        for email in emails:
            email_id = email.get("id", "")
            if email_id and email_id not in self._processed_ids:
                new_emails.append(email)
                self._processed_ids.add(email_id)

        if not new_emails:
            logger.info("No new emails to process")
            return 0

        # Prepare content for analysis
        email_content = self._format_emails_for_analysis(new_emails)

        # Extract action items
        action_items = await self._extract_action_items(email_content, "emails")

        # Create recommendations for action items
        for item in action_items:
            self._create_action_item_recommendation(item)

        return len(action_items)

    async def _process_meetings(self) -> int:
        """Process recent meetings with transcripts for action items."""
        if not self.tool_executor:
            return 0

        # Get recent meetings
        result = await self.tool_executor.execute(
            user_id=DEFAULT_USER_ID,
            tool_name="get_recent_meetings",
            arguments={"days_back": 1, "limit": 5},
        )

        meetings = result.get("meetings", [])
        if not meetings:
            return 0

        total_items = 0

        for meeting in meetings:
            meeting_id = meeting.get("id", "")
            subject = meeting.get("subject", "Unknown meeting")

            # Skip if already processed
            if meeting_id in self._processed_ids:
                continue

            self._processed_ids.add(meeting_id)

            # Try to get meeting summary/transcript
            try:
                summary_result = await self.tool_executor.execute(
                    user_id=DEFAULT_USER_ID,
                    tool_name="get_meeting_summary",
                    arguments={"subject": subject},
                )

                if summary_result.get("error"):
                    continue

                # Format meeting content
                content = self._format_meeting_for_analysis(meeting, summary_result)

                # Extract action items
                action_items = await self._extract_action_items(
                    content, f"meeting: {subject}"
                )

                # Create recommendations
                for item in action_items:
                    self._create_action_item_recommendation(item)

                total_items += len(action_items)

            except Exception as e:
                logger.warning(f"Failed to process meeting {subject}: {e}")
                continue

        return total_items

    def _format_emails_for_analysis(self, emails: list[dict]) -> str:
        """Format emails for action item extraction."""
        parts = []
        for email in emails:
            sender = email.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
            subject = email.get("subject", "No subject")
            body = email.get("bodyPreview", "")
            received = email.get("receivedDateTime", "")

            parts.append(f"""
Email from: {sender}
Subject: {subject}
Received: {received}
Content: {body}
---""")

        return "\n".join(parts)

    def _format_meeting_for_analysis(self, meeting: dict, summary: dict) -> str:
        """Format meeting content for action item extraction."""
        subject = meeting.get("subject", "Unknown meeting")
        organizer = meeting.get("organizer", {}).get("emailAddress", {}).get("name", "Unknown")
        start = meeting.get("start", {}).get("dateTime", "Unknown time")

        # Get transcript/notes if available
        notes = summary.get("notes", "")
        transcript = summary.get("transcript", "")
        copilot_insights = summary.get("copilot_insights", {})

        content = f"""
Meeting: {subject}
Organizer: {organizer}
Date: {start}
"""

        if copilot_insights:
            action_items = copilot_insights.get("action_items", [])
            if action_items:
                content += "\nCopilot Action Items:\n" + "\n".join(f"- {item}" for item in action_items)

            follow_ups = copilot_insights.get("follow_ups", [])
            if follow_ups:
                content += "\nFollow-ups:\n" + "\n".join(f"- {item}" for item in follow_ups)

        if notes:
            content += f"\nMeeting Notes:\n{notes[:2000]}"

        if transcript:
            content += f"\nTranscript Excerpt:\n{transcript[:3000]}"

        return content

    async def _extract_action_items(self, content: str, source: str) -> list[dict]:
        """Use LLM to extract action items from content."""
        if not self.llm_client:
            return []

        messages = [
            {"role": "system", "content": ACTION_ITEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract action items from the following {source}:\n\n{content}",
            },
        ]

        try:
            response = await self.llm_client.chat(messages=messages)

            # Parse JSON response
            import json
            # Find JSON array in response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                items = json.loads(json_str)
                return items if isinstance(items, list) else []

            return []

        except Exception as e:
            logger.error(f"Failed to extract action items: {e}")
            return []

    def _create_action_item_recommendation(self, item: dict) -> None:
        """Create a recommendation for an action item."""
        title = item.get("title", "Action required")
        details = item.get("details", "")
        deadline = item.get("deadline")
        priority = item.get("priority", "normal")
        source = item.get("source", "")

        # Determine priority
        if priority not in ["low", "normal", "high", "urgent"]:
            priority = "normal"

        # Upgrade priority if deadline is soon
        if deadline:
            try:
                deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
                days_until = (deadline_date - datetime.now(timezone.utc).date()).days
                if days_until <= 1:
                    priority = "urgent"
                elif days_until <= 3:
                    priority = "high"
            except ValueError:
                pass

        content = f"{details}\n\n"
        if deadline:
            content += f"**Deadline:** {deadline}\n"
        if source:
            content += f"**Source:** {source}"

        self.create_recommendation(
            title=f"Action: {title}",
            content=content,
            priority=priority,
            metadata={
                "type": "action_item",
                "deadline": deadline,
                "source": source,
            },
        )
