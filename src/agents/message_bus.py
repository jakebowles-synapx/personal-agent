"""Inter-agent communication message bus."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of messages that can be sent between agents."""
    TASK = "task"  # Request to perform a task
    QUERY = "query"  # Request for information
    RESPONSE = "response"  # Response to a query/task
    EVENT = "event"  # Notification of an event


@dataclass
class Message:
    """A message sent between agents."""
    id: str
    type: MessageType
    from_agent: str
    to_agent: str
    content: Any
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None  # For linking responses to requests
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }


MessageHandler = Callable[[Message], Awaitable[Any]]


class MessageBus:
    """
    In-memory async message bus for inter-agent communication.

    Supports:
    - Async message delivery via queues
    - Request/response pattern with correlation IDs
    - Event broadcasting
    - Agent addressing (agent_name or agent_name:method)
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[Message]] = {}
        self._handlers: dict[str, MessageHandler] = {}
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._running = False
        self._tasks: list[asyncio.Task] = []

    def register_agent(self, agent_name: str, handler: MessageHandler | None = None) -> None:
        """Register an agent to receive messages."""
        if agent_name not in self._queues:
            self._queues[agent_name] = asyncio.Queue()
            logger.info(f"Registered agent '{agent_name}' on message bus")

        if handler:
            self._handlers[agent_name] = handler

    def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent from the message bus."""
        if agent_name in self._queues:
            del self._queues[agent_name]
        if agent_name in self._handlers:
            del self._handlers[agent_name]
        logger.info(f"Unregistered agent '{agent_name}' from message bus")

    async def send(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        message_type: MessageType = MessageType.TASK,
        correlation_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        Send a message to an agent.

        Args:
            from_agent: Name of the sending agent
            to_agent: Name of the receiving agent (can be "agent_name" or "agent_name:method")
            content: Message content
            message_type: Type of message
            correlation_id: Optional ID to link related messages
            metadata: Optional additional data

        Returns:
            Message ID
        """
        # Parse agent address (agent_name or agent_name:method)
        if ":" in to_agent:
            target_agent, method = to_agent.split(":", 1)
            if metadata is None:
                metadata = {}
            metadata["method"] = method
        else:
            target_agent = to_agent

        if target_agent not in self._queues:
            logger.warning(f"Target agent '{target_agent}' not registered, message will be dropped")
            raise ValueError(f"Agent '{target_agent}' not registered on message bus")

        message = Message(
            id=str(uuid.uuid4()),
            type=message_type,
            from_agent=from_agent,
            to_agent=target_agent,
            content=content,
            correlation_id=correlation_id,
            metadata=metadata or {},
        )

        await self._queues[target_agent].put(message)
        logger.debug(f"Message {message.id} sent from '{from_agent}' to '{target_agent}'")

        return message.id

    async def query(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        timeout: float = 30.0,
        metadata: dict | None = None,
    ) -> Any:
        """
        Send a query and wait for a response.

        Args:
            from_agent: Name of the sending agent
            to_agent: Name of the receiving agent
            content: Query content
            timeout: Timeout in seconds
            metadata: Optional additional data

        Returns:
            Response content

        Raises:
            TimeoutError: If no response received within timeout
            ValueError: If target agent not registered
        """
        correlation_id = str(uuid.uuid4())

        # Create future for response
        response_future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_responses[correlation_id] = response_future

        try:
            # Send query
            await self.send(
                from_agent=from_agent,
                to_agent=to_agent,
                content=content,
                message_type=MessageType.QUERY,
                correlation_id=correlation_id,
                metadata=metadata,
            )

            # Wait for response
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            logger.warning(f"Query from '{from_agent}' to '{to_agent}' timed out")
            raise TimeoutError(f"Query to '{to_agent}' timed out after {timeout}s")

        finally:
            # Clean up pending response
            self._pending_responses.pop(correlation_id, None)

    async def respond(
        self,
        original_message: Message,
        content: Any,
        metadata: dict | None = None,
    ) -> str:
        """
        Send a response to a query.

        Args:
            original_message: The message being responded to
            content: Response content
            metadata: Optional additional data

        Returns:
            Response message ID
        """
        if not original_message.correlation_id:
            raise ValueError("Cannot respond to message without correlation_id")

        # Check if there's a pending future for this correlation
        if original_message.correlation_id in self._pending_responses:
            future = self._pending_responses[original_message.correlation_id]
            if not future.done():
                future.set_result(content)
                logger.debug(f"Response delivered for correlation {original_message.correlation_id}")
                return original_message.correlation_id

        # Otherwise send as regular message
        return await self.send(
            from_agent=original_message.to_agent,
            to_agent=original_message.from_agent,
            content=content,
            message_type=MessageType.RESPONSE,
            correlation_id=original_message.correlation_id,
            metadata=metadata,
        )

    async def broadcast_event(
        self,
        from_agent: str,
        event_name: str,
        content: Any,
        exclude_agents: list[str] | None = None,
    ) -> list[str]:
        """
        Broadcast an event to all registered agents.

        Args:
            from_agent: Name of the sending agent
            event_name: Name of the event
            content: Event content
            exclude_agents: List of agents to exclude from broadcast

        Returns:
            List of message IDs
        """
        exclude = set(exclude_agents or [])
        exclude.add(from_agent)  # Don't send to self

        message_ids = []
        for agent_name in self._queues:
            if agent_name not in exclude:
                try:
                    msg_id = await self.send(
                        from_agent=from_agent,
                        to_agent=agent_name,
                        content=content,
                        message_type=MessageType.EVENT,
                        metadata={"event_name": event_name},
                    )
                    message_ids.append(msg_id)
                except Exception as e:
                    logger.error(f"Failed to broadcast to '{agent_name}': {e}")

        logger.info(f"Event '{event_name}' broadcast to {len(message_ids)} agents")
        return message_ids

    async def receive(self, agent_name: str, timeout: float | None = None) -> Message | None:
        """
        Receive the next message for an agent.

        Args:
            agent_name: Name of the receiving agent
            timeout: Optional timeout in seconds

        Returns:
            Message or None if timeout
        """
        if agent_name not in self._queues:
            raise ValueError(f"Agent '{agent_name}' not registered on message bus")

        try:
            if timeout:
                return await asyncio.wait_for(
                    self._queues[agent_name].get(),
                    timeout=timeout
                )
            else:
                return await self._queues[agent_name].get()
        except asyncio.TimeoutError:
            return None

    def has_messages(self, agent_name: str) -> bool:
        """Check if an agent has pending messages."""
        if agent_name not in self._queues:
            return False
        return not self._queues[agent_name].empty()

    def get_queue_size(self, agent_name: str) -> int:
        """Get the number of pending messages for an agent."""
        if agent_name not in self._queues:
            return 0
        return self._queues[agent_name].qsize()

    def start_processors(self) -> None:
        """Start message processors for all registered agents with handlers."""
        if self._running:
            return

        self._running = True
        for agent_name, handler in self._handlers.items():
            task = asyncio.create_task(self._process_messages(agent_name, handler))
            self._tasks.append(task)
            logger.info(f"Started message processor for '{agent_name}'")

    async def stop_processors(self) -> None:
        """Stop all message processors."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("Message processors stopped")

    async def _process_messages(self, agent_name: str, handler: MessageHandler) -> None:
        """Process messages for an agent."""
        while self._running:
            try:
                message = await self.receive(agent_name, timeout=1.0)
                if message:
                    try:
                        result = await handler(message)
                        # Auto-respond to queries
                        if message.type == MessageType.QUERY and message.correlation_id:
                            await self.respond(message, result)
                    except Exception as e:
                        logger.error(f"Error handling message in '{agent_name}': {e}", exc_info=True)
                        if message.type == MessageType.QUERY and message.correlation_id:
                            await self.respond(message, {"error": str(e)})
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message processor for '{agent_name}': {e}")


# Global message bus instance
_message_bus: MessageBus | None = None


def get_message_bus() -> MessageBus:
    """Get the global message bus instance."""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
    return _message_bus
