"""Agent orchestrator - main agent logic."""

import json
import logging
import os

from src.llm import AzureOpenAIClient
from src.memory import MemoryClient, ConversationHistory
from src.microsoft.auth import MicrosoftAuth
from src.config import settings

from .prompts import build_system_message
from .tools import TOOLS, HARVEST_TOOLS, ToolExecutor

logger = logging.getLogger(__name__)

# Maximum number of tool execution rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 5

# Default user ID for single-user mode (no auth)
DEFAULT_USER_ID = "default"


class AgentOrchestrator:
    """Orchestrates the agent's response generation with tool support."""

    def __init__(self) -> None:
        self.llm = AzureOpenAIClient()
        self.memory = MemoryClient()
        # Use data_dir for SQLite databases
        history_db = os.path.join(settings.data_dir, "conversation_history.db")
        tokens_db = os.path.join(settings.data_dir, "tokens.db")
        self.history = ConversationHistory(db_path=history_db)
        self.auth = MicrosoftAuth(db_path=tokens_db)
        self.tool_executor = ToolExecutor(self.auth)

    async def process_message(self, thread_id: str, message: str) -> str:
        """Process a user message and return the agent's response."""
        # Search for relevant memories (long-term facts)
        memories = []
        try:
            memories = self.memory.search(query=message, user_id=DEFAULT_USER_ID, limit=5)
            logger.info(f"Memory search results: {memories}")
        except Exception as e:
            logger.warning(f"Failed to search memories: {e}")

        # Get recent conversation history (short-term context)
        recent_messages = []
        try:
            recent_messages = self.history.get_recent_messages(thread_id=thread_id, limit=20)
            logger.info(f"Retrieved {len(recent_messages)} recent messages from history")
        except Exception as e:
            logger.warning(f"Failed to get conversation history: {e}")

        # Check if user has Microsoft connected
        ms_connected = self.auth.is_connected(DEFAULT_USER_ID)

        # Check if Harvest is configured
        harvest_connected = self.is_harvest_connected()

        # Build messages for the LLM
        system_message = build_system_message(
            memories, ms_connected=ms_connected, harvest_connected=harvest_connected
        )
        logger.debug(f"System message: {system_message}")

        # Construct messages: system, then history, then current message
        messages = [{"role": "system", "content": system_message}]
        messages.extend(recent_messages)
        messages.append({"role": "user", "content": message})

        logger.info(f"Sending {len(messages)} messages to LLM (1 system + {len(recent_messages)} history + 1 current)")

        # Get response from LLM (with tools if any integrations are connected)
        if ms_connected or harvest_connected:
            response = await self._process_with_tools(messages, ms_connected, harvest_connected)
        else:
            response = await self.llm.chat(messages=messages)

        # Store the exchange in conversation history (short-term)
        try:
            self.history.add_exchange(thread_id=thread_id, user_message=message, assistant_message=response)
        except Exception as e:
            logger.warning(f"Failed to store conversation history: {e}")

        # Store the conversation in Mem0 memory (long-term facts extraction)
        try:
            conversation = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response},
            ]
            self.memory.add(messages=conversation, user_id=DEFAULT_USER_ID)
        except Exception as e:
            logger.warning(f"Failed to store memory: {e}")

        # Auto-generate thread title from first message
        try:
            thread = self.history.get_thread(thread_id)
            if thread and not thread.get("title"):
                # Use first ~50 chars of user message as title
                title = message[:50] + ("..." if len(message) > 50 else "")
                self.history.set_thread_title_if_empty(thread_id, title)
        except Exception as e:
            logger.warning(f"Failed to set thread title: {e}")

        return response

    async def _process_with_tools(
        self, messages: list[dict], ms_connected: bool = False, harvest_connected: bool = False
    ) -> str:
        """Process a message with tool support using the agentic loop."""
        # Build tool list based on what's connected
        tools = []
        if ms_connected:
            tools.extend(TOOLS)
        if harvest_connected:
            tools.extend(HARVEST_TOOLS)

        # Initial call with tools
        result = await self.llm.chat_with_tools(messages=messages, tools=tools)

        rounds = 0
        while result.get("tool_calls") and rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            logger.info(f"Tool execution round {rounds}")

            # Execute all tool calls
            tool_results = []
            for tool_call in result["tool_calls"]:
                tool_name = tool_call["name"]
                try:
                    arguments = json.loads(tool_call["arguments"]) if isinstance(tool_call["arguments"], str) else tool_call["arguments"]
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
            result = await self.llm.submit_tool_results(
                response_id=result["response_id"],
                tool_results=tool_results,
            )

        # Return the final text response
        return result.get("content", "I apologize, but I couldn't generate a response.")

    def get_user_memories(self, user_id: str = DEFAULT_USER_ID) -> list[dict]:
        """Get all memories for a user."""
        try:
            return self.memory.get_all(user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to get memories: {e}")
            return []

    def clear_user_memories(self, user_id: str = DEFAULT_USER_ID) -> None:
        """Clear all memories for a user."""
        try:
            self.memory.delete_all(user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to clear memories: {e}")
            raise

    def is_microsoft_connected(self, user_id: str = DEFAULT_USER_ID) -> bool:
        """Check if user has Microsoft 365 connected."""
        return self.auth.is_connected(user_id)

    def get_microsoft_auth_url(self, user_id: str = DEFAULT_USER_ID) -> str:
        """Get the Microsoft OAuth URL for a user."""
        return self.auth.get_auth_url(user_id)

    def disconnect_microsoft(self, user_id: str = DEFAULT_USER_ID) -> None:
        """Disconnect user's Microsoft account."""
        self.auth.disconnect(user_id)

    def is_harvest_connected(self) -> bool:
        """Check if Harvest is configured."""
        return bool(settings.harvest_account_id and settings.harvest_access_token)
