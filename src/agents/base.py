"""Base agent class for all specialized agents."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.db import AgentRunsDB, RecommendationsDB

if TYPE_CHECKING:
    from src.agents.message_bus import MessageBus, Message
    from src.knowledge.manager import KnowledgeManager
    from src.memory.mem0_client import MemoryClient
    from src.llm import AzureOpenAIClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all agents in the system.

    Provides:
    - Lifecycle management (run with logging)
    - Inter-agent communication
    - Recommendation creation
    - Access to knowledge and memory layers
    """

    # Override in subclasses
    name: str = "base"
    description: str = "Base agent"

    def __init__(
        self,
        message_bus: "MessageBus",
        knowledge_manager: "KnowledgeManager | None" = None,
        memory_client: "MemoryClient | None" = None,
        llm_client: "AzureOpenAIClient | None" = None,
    ) -> None:
        self.message_bus = message_bus
        self.knowledge_manager = knowledge_manager
        self.memory_client = memory_client
        self.llm_client = llm_client
        self._current_run_id: int | None = None

        # Register on message bus
        self.message_bus.register_agent(self.name, self._handle_message)

    async def run(self) -> dict:
        """
        Execute the agent's main task with logging.

        Returns:
            Dict with run results including status, summary, items_processed
        """
        logger.info(f"Starting agent '{self.name}'")

        # Create run record
        self._current_run_id = AgentRunsDB.create(self.name)

        try:
            # Execute agent logic
            result = await self.execute()

            # Mark run as completed
            items_processed = result.get("items_processed", 0)
            summary = result.get("summary", "Completed successfully")

            AgentRunsDB.complete(
                run_id=self._current_run_id,
                status="completed",
                summary=summary,
                items_processed=items_processed,
            )

            logger.info(f"Agent '{self.name}' completed: {summary}")
            return {
                "status": "completed",
                "run_id": self._current_run_id,
                **result,
            }

        except Exception as e:
            logger.error(f"Agent '{self.name}' failed: {e}", exc_info=True)

            AgentRunsDB.complete(
                run_id=self._current_run_id,
                status="failed",
                error_message=str(e),
            )

            return {
                "status": "failed",
                "run_id": self._current_run_id,
                "error": str(e),
            }

        finally:
            self._current_run_id = None

    @abstractmethod
    async def execute(self) -> dict:
        """
        Agent-specific execution logic.

        Override in subclasses to implement agent behavior.

        Returns:
            Dict with at minimum:
            - summary: str - Brief description of what was done
            - items_processed: int - Number of items processed
        """
        pass

    def can_handle(self, message: str) -> bool:
        """
        Check if this agent can handle a chat message.

        Override in subclasses for agents that handle chat messages.

        Args:
            message: The user's message

        Returns:
            True if this agent should handle the message
        """
        return False

    async def handle_chat(self, message: str, context: dict | None = None) -> str:
        """
        Handle a chat message.

        Override in subclasses for agents that handle chat messages.

        Args:
            message: The user's message
            context: Optional context (memories, history, etc.)

        Returns:
            Response string
        """
        return "This agent does not handle chat messages."

    async def _handle_message(self, message: "Message") -> Any:
        """
        Handle an inter-agent message.

        Override to customize message handling.

        Args:
            message: The incoming message

        Returns:
            Response to the message (for queries)
        """
        logger.debug(f"Agent '{self.name}' received message: {message.type} from {message.from_agent}")

        # Check for method routing
        method_name = message.metadata.get("method")
        if method_name:
            method = getattr(self, method_name, None)
            if method and callable(method):
                return await method(message.content)
            else:
                logger.warning(f"Method '{method_name}' not found on agent '{self.name}'")
                return {"error": f"Method '{method_name}' not found"}

        # Default handling
        return await self.on_message(message)

    async def on_message(self, message: "Message") -> Any:
        """
        Handle a message without method routing.

        Override in subclasses for custom message handling.
        """
        return {"received": True}

    # Inter-agent communication methods

    async def send_to_agent(
        self,
        agent_name: str,
        content: Any,
        method: str | None = None,
    ) -> str:
        """
        Send a message to another agent.

        Args:
            agent_name: Target agent name
            content: Message content
            method: Optional method to call on target agent

        Returns:
            Message ID
        """
        from src.agents.message_bus import MessageType

        target = f"{agent_name}:{method}" if method else agent_name
        return await self.message_bus.send(
            from_agent=self.name,
            to_agent=target,
            content=content,
            message_type=MessageType.TASK,
        )

    async def query_agent(
        self,
        agent_name: str,
        content: Any,
        method: str | None = None,
        timeout: float = 30.0,
    ) -> Any:
        """
        Query another agent and wait for response.

        Args:
            agent_name: Target agent name
            content: Query content
            method: Optional method to call on target agent
            timeout: Timeout in seconds

        Returns:
            Response from target agent
        """
        target = f"{agent_name}:{method}" if method else agent_name
        return await self.message_bus.query(
            from_agent=self.name,
            to_agent=target,
            content=content,
            timeout=timeout,
        )

    async def broadcast_event(
        self,
        event_name: str,
        content: Any,
        exclude_agents: list[str] | None = None,
    ) -> list[str]:
        """
        Broadcast an event to all agents.

        Args:
            event_name: Name of the event
            content: Event content
            exclude_agents: Agents to exclude from broadcast

        Returns:
            List of message IDs
        """
        return await self.message_bus.broadcast_event(
            from_agent=self.name,
            event_name=event_name,
            content=content,
            exclude_agents=exclude_agents,
        )

    # Recommendation methods

    def create_recommendation(
        self,
        title: str,
        content: str,
        priority: str = "normal",
        metadata: dict | None = None,
    ) -> int:
        """
        Create a recommendation for the user.

        Args:
            title: Short title for the recommendation
            content: Detailed content/description
            priority: Priority level (low, normal, high, urgent)
            metadata: Optional additional data

        Returns:
            Recommendation ID
        """
        valid_priorities = ["low", "normal", "high", "urgent"]
        if priority not in valid_priorities:
            raise ValueError(f"Invalid priority: {priority}. Must be one of {valid_priorities}")

        rec_id = RecommendationsDB.create(
            agent_name=self.name,
            title=title,
            content=content,
            priority=priority,
            metadata=metadata,
        )

        logger.info(f"Agent '{self.name}' created recommendation {rec_id}: {title}")
        return rec_id

    # Knowledge access methods

    async def search_knowledge(
        self,
        query: str,
        category: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Search the knowledge base.

        Args:
            query: Search query
            category: Optional category filter
            limit: Maximum results

        Returns:
            List of matching knowledge items
        """
        if not self.knowledge_manager:
            logger.warning(f"Agent '{self.name}' has no knowledge manager")
            return []

        return await self.knowledge_manager.search(
            query=query,
            category=category,
            limit=limit,
        )

    async def get_knowledge_by_category(self, category: str) -> list[dict]:
        """
        Get all knowledge items in a category.

        Args:
            category: Category name

        Returns:
            List of knowledge items
        """
        if not self.knowledge_manager:
            return []

        return self.knowledge_manager.list_by_category(category)

    # Memory access methods

    def search_memories(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 5,
    ) -> list[dict]:
        """
        Search dynamic memories (Mem0).

        Args:
            query: Search query
            user_id: User ID
            limit: Maximum results

        Returns:
            List of matching memories
        """
        if not self.memory_client:
            logger.warning(f"Agent '{self.name}' has no memory client")
            return []

        return self.memory_client.search(query=query, user_id=user_id, limit=limit)

    def get_all_memories(self, user_id: str = "default") -> list[dict]:
        """
        Get all memories for a user.

        Args:
            user_id: User ID

        Returns:
            List of all memories
        """
        if not self.memory_client:
            return []

        return self.memory_client.get_all(user_id=user_id)

    # LLM access methods

    async def chat_with_llm(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> str:
        """
        Send messages to the LLM.

        Args:
            messages: List of message dicts with role/content
            system_prompt: Optional system prompt

        Returns:
            LLM response text
        """
        if not self.llm_client:
            raise RuntimeError(f"Agent '{self.name}' has no LLM client")

        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        return await self.llm_client.chat(messages=messages)

    # Status methods

    def get_last_run(self) -> dict | None:
        """Get the last run record for this agent."""
        return AgentRunsDB.get_last_run(self.name)

    def get_recent_runs(self, limit: int = 10, hours: int = 24) -> list[dict]:
        """Get recent runs for this agent."""
        return AgentRunsDB.list_recent(agent_name=self.name, limit=limit, hours=hours)
