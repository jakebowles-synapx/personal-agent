"""Chat agent - handles user conversations."""

import json
import logging
from typing import TYPE_CHECKING

from src.agents.base import BaseAgent
from src.agent.prompts import build_system_message
from src.agent.tools import TOOLS, HARVEST_TOOLS, KNOWLEDGE_TOOLS, ToolExecutor
from src.config import settings

if TYPE_CHECKING:
    from src.agents.message_bus import MessageBus, Message
    from src.knowledge.manager import KnowledgeManager
    from src.memory.mem0_client import MemoryClient
    from src.memory.conversation_history import ConversationHistory
    from src.microsoft.auth import MicrosoftAuth
    from src.llm import AzureOpenAIClient

logger = logging.getLogger(__name__)

# Maximum number of tool execution rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 5

# Default user ID for single-user mode (no auth)
DEFAULT_USER_ID = "default"


class ChatAgent(BaseAgent):
    """
    Agent that handles user conversations.

    This is the main chat interface, refactored from AgentOrchestrator.
    It handles:
    - User messages with full conversation context
    - Tool calling for Microsoft 365 and Harvest
    - Memory storage and retrieval
    - Knowledge integration
    """

    name = "chat"
    description = "Handles user conversations with memory and tool support"

    def __init__(
        self,
        message_bus: "MessageBus",
        knowledge_manager: "KnowledgeManager | None" = None,
        memory_client: "MemoryClient | None" = None,
        llm_client: "AzureOpenAIClient | None" = None,
        conversation_history: "ConversationHistory | None" = None,
        auth: "MicrosoftAuth | None" = None,
    ) -> None:
        super().__init__(
            message_bus=message_bus,
            knowledge_manager=knowledge_manager,
            memory_client=memory_client,
            llm_client=llm_client,
        )
        self.history = conversation_history
        self.auth = auth
        self.tool_executor = ToolExecutor(auth) if auth else None

    def can_handle(self, message: str) -> bool:
        """Chat agent handles all messages as fallback."""
        return True

    async def execute(self) -> dict:
        """
        ChatAgent doesn't have scheduled execution.
        It's only triggered by user messages.
        """
        return {
            "summary": "Chat agent is on-demand only",
            "items_processed": 0,
        }

    async def handle_chat(
        self,
        message: str,
        thread_id: str,
        context: dict | None = None,
    ) -> str:
        """
        Handle a user chat message.

        Args:
            message: The user's message
            thread_id: Conversation thread ID
            context: Optional additional context

        Returns:
            Response string
        """
        # Search for relevant memories (long-term facts)
        memories = []
        if self.memory_client:
            try:
                memories = self.memory_client.search(
                    query=message, user_id=DEFAULT_USER_ID, limit=5
                )
                logger.info(f"Memory search results: {len(memories)} items")
            except Exception as e:
                logger.warning(f"Failed to search memories: {e}")

        # Get recent conversation history (short-term context)
        recent_messages = []
        if self.history:
            try:
                recent_messages = self.history.get_recent_messages(
                    thread_id=thread_id, limit=20
                )
                logger.info(f"Retrieved {len(recent_messages)} recent messages from history")
            except Exception as e:
                logger.warning(f"Failed to get conversation history: {e}")

        # Check integrations
        ms_connected = self.auth.is_connected(DEFAULT_USER_ID) if self.auth else False
        harvest_connected = self._is_harvest_connected()

        # Get fixed knowledge context
        knowledge_context = ""
        if self.knowledge_manager:
            try:
                # Search for relevant knowledge
                knowledge_results = await self.knowledge_manager.search(
                    query=message, limit=3
                )
                if knowledge_results:
                    knowledge_parts = []
                    for item in knowledge_results:
                        knowledge_parts.append(
                            f"- **{item['title']}** ({item['category']}): {item['content'][:300]}..."
                        )
                    knowledge_context = "\n\nRelevant knowledge:\n" + "\n".join(knowledge_parts)
            except Exception as e:
                logger.warning(f"Failed to search knowledge: {e}")

        # Build messages for the LLM
        system_message = build_system_message(
            memories,
            ms_connected=ms_connected,
            harvest_connected=harvest_connected,
        )

        # Add knowledge context if available
        if knowledge_context:
            system_message += knowledge_context

        # Construct messages: system, then history, then current message
        messages = [{"role": "system", "content": system_message}]
        messages.extend(recent_messages)
        messages.append({"role": "user", "content": message})

        logger.info(
            f"Sending {len(messages)} messages to LLM "
            f"(1 system + {len(recent_messages)} history + 1 current)"
        )

        # Get response from LLM with tools (knowledge tools always available)
        if self.tool_executor:
            response = await self._process_with_tools(
                messages, ms_connected, harvest_connected
            )
        else:
            response = await self.llm_client.chat(messages=messages)

        # Store the exchange in conversation history (short-term)
        if self.history:
            try:
                self.history.add_exchange(
                    thread_id=thread_id,
                    user_message=message,
                    assistant_message=response,
                )
            except Exception as e:
                logger.warning(f"Failed to store conversation history: {e}")

        # Store the conversation in Mem0 memory (long-term facts extraction)
        if self.memory_client:
            try:
                conversation = [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response},
                ]
                self.memory_client.add(messages=conversation, user_id=DEFAULT_USER_ID)
            except Exception as e:
                logger.warning(f"Failed to store memory: {e}")

        # Auto-generate thread title from first message
        if self.history:
            try:
                thread = self.history.get_thread(thread_id)
                if thread and not thread.get("title"):
                    title = message[:50] + ("..." if len(message) > 50 else "")
                    self.history.set_thread_title_if_empty(thread_id, title)
            except Exception as e:
                logger.warning(f"Failed to set thread title: {e}")

        return response

    async def _process_with_tools(
        self,
        messages: list[dict],
        ms_connected: bool = False,
        harvest_connected: bool = False,
    ) -> str:
        """Process a message with tool support using the agentic loop."""
        if not self.tool_executor:
            raise RuntimeError("Tool executor not configured")

        # Build tool list based on what's connected
        # Knowledge tools are always available
        tools = list(KNOWLEDGE_TOOLS)
        if ms_connected:
            tools.extend(TOOLS)
        if harvest_connected:
            tools.extend(HARVEST_TOOLS)

        # Initial call with tools
        result = await self.llm_client.chat_with_tools(messages=messages, tools=tools)

        rounds = 0
        while result.get("tool_calls") and rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            logger.info(f"Tool execution round {rounds}")

            # Execute all tool calls
            tool_results = []
            for tool_call in result["tool_calls"]:
                tool_name = tool_call["name"]
                try:
                    arguments = (
                        json.loads(tool_call["arguments"])
                        if isinstance(tool_call["arguments"], str)
                        else tool_call["arguments"]
                    )
                except json.JSONDecodeError:
                    arguments = {}

                # Execute the tool
                tool_output = await self.tool_executor.execute(
                    user_id=DEFAULT_USER_ID,
                    tool_name=tool_name,
                    arguments=arguments,
                )

                tool_results.append({
                    "call_id": tool_call["call_id"],
                    "output": tool_output,
                })

            # Submit tool results back to the LLM
            result = await self.llm_client.submit_tool_results(
                response_id=result["response_id"],
                tool_results=tool_results,
            )

        # Return the final text response
        return result.get("content", "I apologize, but I couldn't generate a response.")

    def _is_harvest_connected(self) -> bool:
        """Check if Harvest is configured."""
        return bool(settings.harvest_account_id and settings.harvest_access_token)

    # Inter-agent query methods

    async def get_context_for_topic(self, topic: str) -> dict:
        """
        Get conversation context for a topic.

        Used by other agents to query chat context.

        Args:
            topic: Topic to search for

        Returns:
            Dict with relevant memories and history
        """
        memories = []
        if self.memory_client:
            memories = self.memory_client.search(
                query=topic, user_id=DEFAULT_USER_ID, limit=5
            )

        return {
            "topic": topic,
            "memories": memories,
        }

    async def on_message(self, message: "Message") -> dict:
        """Handle inter-agent messages."""
        from src.agents.message_bus import MessageType

        if message.type == MessageType.QUERY:
            # Handle queries from other agents
            if isinstance(message.content, dict):
                action = message.content.get("action")
                if action == "get_context":
                    topic = message.content.get("topic", "")
                    return await self.get_context_for_topic(topic)

        return {"received": True}
