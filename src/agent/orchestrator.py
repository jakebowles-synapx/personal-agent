"""Agent orchestrator - main agent logic."""

import json
import logging

from src.llm import AzureOpenAIClient
from src.memory import MemoryClient, ConversationHistory
from src.microsoft.auth import MicrosoftAuth

from .prompts import build_system_message
from .tools import TOOLS, ToolExecutor

logger = logging.getLogger(__name__)

# Maximum number of tool execution rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 5


class AgentOrchestrator:
    """Orchestrates the agent's response generation with tool support."""

    def __init__(self) -> None:
        self.llm = AzureOpenAIClient()
        self.memory = MemoryClient()
        self.history = ConversationHistory()
        self.auth = MicrosoftAuth()
        self.tool_executor = ToolExecutor(self.auth)

    async def process_message(self, user_id: str, message: str) -> str:
        """Process a user message and return the agent's response."""
        # Search for relevant memories (long-term facts)
        memories = []
        try:
            memories = self.memory.search(query=message, user_id=user_id, limit=5)
            logger.info(f"Memory search results: {memories}")
        except Exception as e:
            logger.warning(f"Failed to search memories: {e}")

        # Get recent conversation history (short-term context)
        recent_messages = []
        try:
            recent_messages = self.history.get_recent_messages(user_id=user_id, limit=20)
            logger.info(f"Retrieved {len(recent_messages)} recent messages from history")
        except Exception as e:
            logger.warning(f"Failed to get conversation history: {e}")

        # Check if user has Microsoft connected
        ms_connected = self.auth.is_connected(user_id)

        # Build messages for the LLM
        system_message = build_system_message(memories, ms_connected=ms_connected)
        logger.debug(f"System message: {system_message}")

        # Construct messages: system, then history, then current message
        messages = [{"role": "system", "content": system_message}]
        messages.extend(recent_messages)
        messages.append({"role": "user", "content": message})

        logger.info(f"Sending {len(messages)} messages to LLM (1 system + {len(recent_messages)} history + 1 current)")

        # Get response from LLM (with tools if Microsoft is connected)
        if ms_connected:
            response = await self._process_with_tools(user_id, messages)
        else:
            response = await self.llm.chat(messages=messages)

        # Store the exchange in conversation history (short-term)
        try:
            self.history.add_exchange(user_id=user_id, user_message=message, assistant_message=response)
        except Exception as e:
            logger.warning(f"Failed to store conversation history: {e}")

        # Store the conversation in Mem0 memory (long-term facts extraction)
        try:
            conversation = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response},
            ]
            self.memory.add(messages=conversation, user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to store memory: {e}")

        return response

    async def _process_with_tools(self, user_id: str, messages: list[dict]) -> str:
        """Process a message with tool support using the agentic loop."""
        # Initial call with tools
        result = await self.llm.chat_with_tools(messages=messages, tools=TOOLS)

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
                    user_id=user_id,
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

    def get_user_memories(self, user_id: str) -> list[dict]:
        """Get all memories for a user."""
        try:
            return self.memory.get_all(user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to get memories: {e}")
            return []

    def clear_user_memories(self, user_id: str) -> None:
        """Clear all memories for a user."""
        try:
            self.memory.delete_all(user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to clear memories: {e}")
            raise

    def clear_conversation_history(self, user_id: str) -> None:
        """Clear conversation history for a user."""
        try:
            self.history.clear_history(user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to clear conversation history: {e}")
            raise

    def clear_all(self, user_id: str) -> None:
        """Clear both memories and conversation history for a user."""
        self.clear_user_memories(user_id)
        self.clear_conversation_history(user_id)

    def is_microsoft_connected(self, user_id: str) -> bool:
        """Check if user has Microsoft 365 connected."""
        return self.auth.is_connected(user_id)

    def get_microsoft_auth_url(self, user_id: str) -> str:
        """Get the Microsoft OAuth URL for a user."""
        return self.auth.get_auth_url(user_id)

    def disconnect_microsoft(self, user_id: str) -> None:
        """Disconnect user's Microsoft account."""
        self.auth.disconnect(user_id)
