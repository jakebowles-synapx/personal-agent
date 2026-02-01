"""Memory agent - maintains and updates knowledge from conversations and content."""

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

KNOWLEDGE_EXTRACTION_PROMPT = """You are analyzing content to extract important knowledge that should be remembered long-term.

Focus on extracting:
1. People information (names, roles, relationships, preferences)
2. Project information (names, statuses, key dates, stakeholders)
3. Process information (how things work, workflows)
4. Business context (clients, strategies, goals)

For each piece of knowledge, determine:
- Category: team, clients, projects, processes, or strategy
- Title: A short descriptive title
- Content: The key information to remember

Format your response as a JSON array:
[
  {
    "category": "team|clients|projects|processes|strategy",
    "title": "Brief title",
    "content": "The important information to remember"
  }
]

Only extract genuinely useful long-term knowledge. Skip:
- Temporary or time-sensitive information
- Trivial details
- Information that's already obvious

If no significant knowledge is found, return an empty array: []
"""


class MemoryAgent(BaseAgent):
    """
    Agent that maintains and updates knowledge.

    Runs hourly to:
    - Process new conversations for facts
    - Update fixed knowledge from meetings/documents
    - Maintain knowledge freshness
    """

    name = "memory"
    description = "Maintains and updates knowledge from conversations"

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
        self._last_processed_time: datetime | None = None

    async def execute(self) -> dict:
        """Process content to extract and store knowledge."""
        logger.info("Running memory update...")

        items_processed = 0
        knowledge_added = 0

        # Process recent meetings for knowledge
        if self.auth and self.auth.is_connected(DEFAULT_USER_ID):
            try:
                meeting_knowledge = await self._process_recent_meetings()
                knowledge_added += meeting_knowledge
                items_processed += 1
            except Exception as e:
                logger.error(f"Failed to process meetings for knowledge: {e}")

        # Analyze memory patterns (clean up/consolidate)
        try:
            consolidations = await self._consolidate_memories()
            items_processed += consolidations
        except Exception as e:
            logger.error(f"Failed to consolidate memories: {e}")

        # Update last processed time
        self._last_processed_time = datetime.now(timezone.utc)

        # Create summary recommendation if significant knowledge was added
        if knowledge_added > 0:
            self.create_recommendation(
                title="Knowledge Updated",
                content=f"Added {knowledge_added} new knowledge items from recent content.",
                priority="low",
                metadata={
                    "type": "knowledge_update",
                    "items_added": knowledge_added,
                },
            )

        return {
            "summary": f"Processed {items_processed} sources, added {knowledge_added} knowledge items",
            "items_processed": items_processed,
        }

    async def _process_recent_meetings(self) -> int:
        """Extract knowledge from recent meetings."""
        if not self.tool_executor or not self.knowledge_manager:
            return 0

        # Get meetings from last 2 hours (since we run hourly)
        result = await self.tool_executor.execute(
            user_id=DEFAULT_USER_ID,
            tool_name="get_recent_meetings",
            arguments={"days_back": 1, "limit": 5},
        )

        meetings = result.get("meetings", [])
        if not meetings:
            return 0

        knowledge_added = 0

        for meeting in meetings:
            subject = meeting.get("subject", "")

            # Get meeting summary/transcript
            try:
                summary = await self.tool_executor.execute(
                    user_id=DEFAULT_USER_ID,
                    tool_name="get_meeting_summary",
                    arguments={"subject": subject},
                )

                if summary.get("error"):
                    continue

                # Extract knowledge from meeting content
                content = self._format_meeting_content(meeting, summary)
                knowledge_items = await self._extract_knowledge(content)

                # Store extracted knowledge
                for item in knowledge_items:
                    try:
                        await self.knowledge_manager.add(
                            category=item["category"],
                            title=item["title"],
                            content=item["content"],
                            source=f"meeting: {subject}",
                        )
                        knowledge_added += 1
                    except Exception as e:
                        logger.warning(f"Failed to store knowledge: {e}")

            except Exception as e:
                logger.warning(f"Failed to process meeting {subject}: {e}")

        return knowledge_added

    def _format_meeting_content(self, meeting: dict, summary: dict) -> str:
        """Format meeting content for knowledge extraction."""
        subject = meeting.get("subject", "")
        attendees = meeting.get("attendees", [])

        content = f"Meeting: {subject}\n"
        content += f"Attendees: {', '.join(a.get('emailAddress', {}).get('name', '') for a in attendees[:10])}\n"

        # Include meeting notes/transcript
        notes = summary.get("notes", "")
        transcript = summary.get("transcript", "")
        copilot_insights = summary.get("copilot_insights", {})

        if copilot_insights:
            key_points = copilot_insights.get("key_points", [])
            if key_points:
                content += "\nKey Points:\n" + "\n".join(f"- {p}" for p in key_points)

        if notes:
            content += f"\nNotes: {notes[:2000]}"

        if transcript:
            content += f"\nDiscussion: {transcript[:3000]}"

        return content

    async def _extract_knowledge(self, content: str) -> list[dict]:
        """Use LLM to extract knowledge from content."""
        if not self.llm_client:
            return []

        messages = [
            {"role": "system", "content": KNOWLEDGE_EXTRACTION_PROMPT},
            {
                "role": "user",
                "content": f"Extract important knowledge from:\n\n{content}",
            },
        ]

        try:
            response = await self.llm_client.chat(messages=messages)

            # Parse JSON response
            import json
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                items = json.loads(json_str)
                # Validate items
                valid_items = []
                for item in items:
                    if all(k in item for k in ["category", "title", "content"]):
                        if item["category"] in ["team", "clients", "projects", "processes", "strategy"]:
                            valid_items.append(item)
                return valid_items

            return []

        except Exception as e:
            logger.error(f"Failed to extract knowledge: {e}")
            return []

    async def _consolidate_memories(self) -> int:
        """Consolidate and clean up memories."""
        if not self.memory_client:
            return 0

        # Get all memories
        memories = self.memory_client.get_all(user_id=DEFAULT_USER_ID)
        if not memories:
            return 0

        # For now, just count - future: implement deduplication/consolidation
        logger.info(f"Memory consolidation: {len(memories)} total memories")

        return 0

    async def learn_from_conversation(
        self,
        conversation: list[dict],
        context: str | None = None,
    ) -> int:
        """
        Learn from a conversation (called by chat agent).

        Args:
            conversation: List of message dicts
            context: Optional context about the conversation

        Returns:
            Number of knowledge items extracted
        """
        if not self.knowledge_manager or not self.llm_client:
            return 0

        # Format conversation
        content = ""
        if context:
            content += f"Context: {context}\n\n"

        for msg in conversation:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            content += f"{role.title()}: {text}\n"

        # Extract knowledge
        knowledge_items = await self._extract_knowledge(content)

        # Store extracted knowledge
        added = 0
        for item in knowledge_items:
            try:
                await self.knowledge_manager.add(
                    category=item["category"],
                    title=item["title"],
                    content=item["content"],
                    source="conversation",
                )
                added += 1
            except Exception as e:
                logger.warning(f"Failed to store knowledge: {e}")

        return added

    async def on_message(self, message) -> dict:
        """Handle inter-agent messages."""
        from src.agents.message_bus import MessageType

        if message.type == MessageType.EVENT:
            event_name = message.metadata.get("event_name")

            if event_name == "conversation_complete":
                # Learn from conversation
                conversation = message.content.get("conversation", [])
                context = message.content.get("context")
                added = await self.learn_from_conversation(conversation, context)
                return {"knowledge_added": added}

        return {"received": True}
