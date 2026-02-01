"""Agent registry for discovering and managing agents."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for managing agent instances.

    Provides:
    - Agent registration and discovery
    - Message routing based on capability
    - Agent lifecycle management
    """

    def __init__(self) -> None:
        self._agents: dict[str, "BaseAgent"] = {}
        self._chat_agents: list[str] = []  # Agents that can handle chat messages

    def register(self, agent: "BaseAgent") -> None:
        """
        Register an agent.

        Args:
            agent: Agent instance to register
        """
        if agent.name in self._agents:
            logger.warning(f"Agent '{agent.name}' already registered, replacing")

        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} - {agent.description}")

        # Track if this agent handles chat
        if hasattr(agent, "can_handle") and agent.name not in self._chat_agents:
            # Will be used for routing
            self._chat_agents.append(agent.name)

    def unregister(self, agent_name: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_name: Name of agent to unregister

        Returns:
            True if agent was unregistered
        """
        if agent_name in self._agents:
            del self._agents[agent_name]
            if agent_name in self._chat_agents:
                self._chat_agents.remove(agent_name)
            logger.info(f"Unregistered agent: {agent_name}")
            return True
        return False

    def get_agent(self, agent_name: str) -> "BaseAgent | None":
        """
        Get an agent by name.

        Args:
            agent_name: Name of the agent

        Returns:
            Agent instance or None
        """
        return self._agents.get(agent_name)

    def has_agent(self, agent_name: str) -> bool:
        """
        Check if an agent is registered.

        Args:
            agent_name: Name of the agent

        Returns:
            True if agent is registered
        """
        return agent_name in self._agents

    def list_agents(self) -> list[dict]:
        """
        List all registered agents.

        Returns:
            List of agent info dicts
        """
        return [
            {
                "name": agent.name,
                "description": agent.description,
                "last_run": agent.get_last_run(),
            }
            for agent in self._agents.values()
        ]

    def get_all_agents(self) -> list["BaseAgent"]:
        """
        Get all registered agent instances.

        Returns:
            List of agent instances
        """
        return list(self._agents.values())

    def find_handler(self, message: str) -> "BaseAgent | None":
        """
        Find an agent that can handle a chat message.

        Uses the can_handle method of each agent to determine routing.
        The ChatAgent is typically the fallback.

        Args:
            message: The user's message

        Returns:
            Agent that can handle the message, or None
        """
        # Check specialized agents first (exclude chat agent)
        for agent_name in self._chat_agents:
            if agent_name == "chat":
                continue
            agent = self._agents.get(agent_name)
            if agent and agent.can_handle(message):
                logger.info(f"Message routed to specialized agent: {agent_name}")
                return agent

        # Fall back to chat agent
        chat_agent = self._agents.get("chat")
        if chat_agent:
            return chat_agent

        return None

    def get_scheduled_agents(self) -> list[str]:
        """
        Get names of agents that run on schedules.

        Returns:
            List of agent names
        """
        # These are the agents that have scheduled runs
        scheduled = ["briefing", "action_item", "memory", "anomaly"]
        return [name for name in scheduled if name in self._agents]


# Global registry instance
_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
