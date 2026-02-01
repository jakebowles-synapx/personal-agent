"""Slash command handling for the web interface."""

import logging
from dataclasses import dataclass

from src.agent import AgentOrchestrator
from src.config import settings

logger = logging.getLogger(__name__)

# Default user ID for single-user mode
DEFAULT_USER_ID = "default"


@dataclass
class CommandResult:
    """Result of executing a command."""
    response: str
    is_command: bool = True


def is_command(message: str) -> bool:
    """Check if a message is a slash command."""
    return message.strip().startswith("/")


async def execute_command(message: str, orchestrator: AgentOrchestrator) -> CommandResult | None:
    """Execute a slash command and return the result."""
    message = message.strip()
    if not is_command(message):
        return None

    parts = message.split(maxsplit=1)
    command = parts[0].lower()
    # args = parts[1] if len(parts) > 1 else ""

    if command in ("/start", "/help"):
        return await cmd_help()
    elif command == "/status":
        return await cmd_status(orchestrator)
    elif command == "/connect":
        return await cmd_connect(orchestrator)
    elif command == "/disconnect":
        return await cmd_disconnect(orchestrator)
    elif command == "/memories":
        return await cmd_memories(orchestrator)
    elif command == "/clear":
        return await cmd_clear(orchestrator)
    else:
        return CommandResult(
            response=f"Unknown command: {command}\n\nType /help to see available commands."
        )


async def cmd_help() -> CommandResult:
    """Show available commands."""
    return CommandResult(
        response=(
            "**Available Commands**\n\n"
            "- `/help` - Show this message\n"
            "- `/status` - Check connection status\n"
            "- `/connect` - Connect your Microsoft 365 account\n"
            "- `/disconnect` - Disconnect Microsoft 365\n"
            "- `/memories` - View your stored memories\n"
            "- `/clear` - Clear all your data\n\n"
            "Or just send a message to chat!"
        )
    )


async def cmd_status(orchestrator: AgentOrchestrator) -> CommandResult:
    """Check status of services."""
    memory_count = 0
    ms_connected = False

    try:
        memories = orchestrator.get_user_memories(DEFAULT_USER_ID)
        memory_count = len(memories)
    except Exception:
        pass

    try:
        ms_connected = orchestrator.is_microsoft_connected(DEFAULT_USER_ID)
    except Exception:
        pass

    harvest_connected = orchestrator.is_harvest_connected()

    ms_status = "Connected" if ms_connected else "Not connected (use `/connect`)"
    harvest_status = "Connected" if harvest_connected else "Not configured"

    return CommandResult(
        response=(
            "**Status**\n\n"
            f"Stored memories: {memory_count}\n\n"
            "**Services:**\n"
            "- LLM (Azure OpenAI): Connected\n"
            "- Memory (Mem0 + Qdrant): Connected\n"
            f"- Microsoft 365: {ms_status}\n"
            f"- Harvest: {harvest_status}"
        )
    )


async def cmd_connect(orchestrator: AgentOrchestrator) -> CommandResult:
    """Initiate Microsoft OAuth flow."""
    # Check if already connected
    if orchestrator.is_microsoft_connected(DEFAULT_USER_ID):
        return CommandResult(
            response=(
                "Your Microsoft 365 account is already connected!\n\n"
                "You can ask me about your:\n"
                "- Calendar and meetings\n"
                "- Emails\n"
                "- Teams chats\n"
                "- Files in OneDrive/SharePoint\n\n"
                "Use `/disconnect` if you want to unlink your account."
            )
        )

    # Check if Azure AD is configured
    if not settings.azure_client_id or not settings.azure_client_secret:
        return CommandResult(
            response=(
                "Microsoft 365 integration is not configured.\n"
                "Please set up Azure AD credentials in the environment."
            )
        )

    try:
        auth_url = orchestrator.get_microsoft_auth_url(DEFAULT_USER_ID)
        return CommandResult(
            response=(
                "To connect your Microsoft 365 account, click the link below:\n\n"
                f"[Sign in with Microsoft]({auth_url})\n\n"
                "After signing in and granting permissions, your account will be connected.\n\n"
                "This will allow access to:\n"
                "- Calendar and meetings\n"
                "- Emails (read-only)\n"
                "- Teams chats (read-only)\n"
                "- Files in OneDrive/SharePoint (read-only)"
            )
        )
    except Exception as e:
        logger.error(f"Failed to generate auth URL: {e}")
        return CommandResult(
            response="Failed to generate authentication link. Please try again later."
        )


async def cmd_disconnect(orchestrator: AgentOrchestrator) -> CommandResult:
    """Disconnect Microsoft account."""
    if not orchestrator.is_microsoft_connected(DEFAULT_USER_ID):
        return CommandResult(
            response=(
                "Your Microsoft 365 account is not connected.\n"
                "Use `/connect` to link your account."
            )
        )

    try:
        orchestrator.disconnect_microsoft(DEFAULT_USER_ID)
        return CommandResult(
            response=(
                "Your Microsoft 365 account has been disconnected.\n\n"
                "I can no longer access your calendar, emails, Teams, or files.\n"
                "Use `/connect` to reconnect anytime."
            )
        )
    except Exception as e:
        logger.error(f"Failed to disconnect: {e}")
        return CommandResult(response="Failed to disconnect. Please try again.")


async def cmd_memories(orchestrator: AgentOrchestrator) -> CommandResult:
    """Show stored memories."""
    try:
        memories = orchestrator.get_user_memories(DEFAULT_USER_ID)
        if not memories:
            return CommandResult(
                response="No memories stored yet. Start chatting to build memory!"
            )

        memory_text = "**Your Stored Memories**\n\n"
        for i, mem in enumerate(memories[:15], 1):  # Show max 15
            text = mem.get("memory", mem.get("text", str(mem)))
            memory_text += f"{i}. {text}\n\n"

        if len(memories) > 15:
            memory_text += f"*...and {len(memories) - 15} more*"

        return CommandResult(response=memory_text)
    except Exception as e:
        logger.error(f"Failed to get memories: {e}")
        return CommandResult(response="Failed to retrieve memories. Please try again.")


async def cmd_clear(orchestrator: AgentOrchestrator) -> CommandResult:
    """Clear all user data."""
    try:
        orchestrator.clear_user_memories(DEFAULT_USER_ID)
        return CommandResult(
            response=(
                "All your data has been cleared:\n"
                "- Long-term memories\n\n"
                "Note: Conversation threads are preserved. Delete them individually from the sidebar."
            )
        )
    except Exception as e:
        logger.error(f"Failed to clear data: {e}")
        return CommandResult(response="Failed to clear data. Please try again.")
