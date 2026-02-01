"""Bot command handlers."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.agent import AgentOrchestrator
from src.config import settings

logger = logging.getLogger(__name__)


def is_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    allowed = settings.allowed_user_ids
    # If no users are configured, allow all (development mode)
    if not allowed:
        return True
    return user_id in allowed


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    if not update.effective_user or not update.message:
        return

    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    await update.message.reply_text(
        "Hello! I'm your personal business assistant.\n\n"
        "I can help you with:\n"
        "- Answering questions and providing advice\n"
        "- Remembering important details from our conversations\n"
        "- Accessing your Microsoft 365 data (after connecting)\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/status - Check bot and connection status\n"
        "/connect - Connect your Microsoft 365 account\n"
        "/disconnect - Disconnect Microsoft 365\n"
        "/memories - View your stored memories\n"
        "/clear - Clear all your memories\n\n"
        "Just send me a message to get started!"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /status command."""
    if not update.effective_user or not update.message:
        return

    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    user_id = str(update.effective_user.id)
    orchestrator: AgentOrchestrator = context.bot_data.get("orchestrator")

    memory_count = 0
    ms_connected = False

    if orchestrator:
        try:
            memories = orchestrator.get_user_memories(user_id)
            memory_count = len(memories)
        except Exception:
            pass

        try:
            ms_connected = orchestrator.is_microsoft_connected(user_id)
        except Exception:
            pass

    ms_status = "Connected" if ms_connected else "Not connected (use /connect)"

    status_text = (
        "Bot Status: Online\n\n"
        f"Your Telegram ID: {user_id}\n"
        f"Stored memories: {memory_count}\n\n"
        "Services:\n"
        "- LLM (Azure OpenAI): Connected\n"
        "- Memory (Mem0 + Qdrant): Connected\n"
        f"- Microsoft 365: {ms_status}"
    )
    await update.message.reply_text(status_text)


async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /memories command."""
    if not update.effective_user or not update.message:
        return

    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    user_id = str(update.effective_user.id)
    orchestrator: AgentOrchestrator = context.bot_data.get("orchestrator")

    if not orchestrator:
        await update.message.reply_text("Bot is still initializing. Please try again.")
        return

    try:
        memories = orchestrator.get_user_memories(user_id)
        if not memories:
            await update.message.reply_text("No memories stored yet. Start chatting to build memory!")
            return

        memory_text = "Your stored memories:\n\n"
        for i, mem in enumerate(memories[:10], 1):  # Show max 10
            text = mem.get("memory", mem.get("text", str(mem)))
            memory_text += f"{i}. {text}\n\n"

        if len(memories) > 10:
            memory_text += f"... and {len(memories) - 10} more"

        await update.message.reply_text(memory_text)
    except Exception as e:
        logger.error(f"Failed to get memories: {e}")
        await update.message.reply_text("Failed to retrieve memories. Please try again.")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /clear command."""
    if not update.effective_user or not update.message:
        return

    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    user_id = str(update.effective_user.id)
    orchestrator: AgentOrchestrator = context.bot_data.get("orchestrator")

    if not orchestrator:
        await update.message.reply_text("Bot is still initializing. Please try again.")
        return

    try:
        orchestrator.clear_all(user_id)
        await update.message.reply_text(
            "All your data has been cleared:\n"
            "- Long-term memories\n"
            "- Conversation history"
        )
    except Exception as e:
        logger.error(f"Failed to clear data: {e}")
        await update.message.reply_text("Failed to clear data. Please try again.")


async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /connect command - initiate Microsoft OAuth flow."""
    if not update.effective_user or not update.message:
        return

    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    user_id = str(update.effective_user.id)
    orchestrator: AgentOrchestrator = context.bot_data.get("orchestrator")

    if not orchestrator:
        await update.message.reply_text("Bot is still initializing. Please try again.")
        return

    # Check if already connected
    if orchestrator.is_microsoft_connected(user_id):
        await update.message.reply_text(
            "Your Microsoft 365 account is already connected!\n\n"
            "You can ask me about your:\n"
            "- Calendar and meetings\n"
            "- Emails\n"
            "- Teams chats\n"
            "- Files in OneDrive/SharePoint\n\n"
            "Use /disconnect if you want to unlink your account."
        )
        return

    # Check if Azure AD is configured
    if not settings.azure_client_id or not settings.azure_client_secret:
        await update.message.reply_text(
            "Microsoft 365 integration is not configured.\n"
            "Please contact the administrator to set up Azure AD credentials."
        )
        return

    try:
        # Generate OAuth URL
        auth_url = orchestrator.get_microsoft_auth_url(user_id)

        await update.message.reply_text(
            "To connect your Microsoft 365 account, please click the link below and sign in:\n\n"
            f"{auth_url}\n\n"
            "After signing in and granting permissions, you'll be redirected back and your account will be connected.\n\n"
            "This will allow me to access your:\n"
            "- Calendar and meetings\n"
            "- Emails (read-only)\n"
            "- Teams chats (read-only)\n"
            "- Files in OneDrive/SharePoint (read-only)"
        )
    except Exception as e:
        logger.error(f"Failed to generate auth URL: {e}")
        await update.message.reply_text(
            "Failed to generate authentication link. Please try again later."
        )


async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /disconnect command - disconnect Microsoft account."""
    if not update.effective_user or not update.message:
        return

    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    user_id = str(update.effective_user.id)
    orchestrator: AgentOrchestrator = context.bot_data.get("orchestrator")

    if not orchestrator:
        await update.message.reply_text("Bot is still initializing. Please try again.")
        return

    if not orchestrator.is_microsoft_connected(user_id):
        await update.message.reply_text(
            "Your Microsoft 365 account is not connected.\n"
            "Use /connect to link your account."
        )
        return

    try:
        orchestrator.disconnect_microsoft(user_id)
        await update.message.reply_text(
            "Your Microsoft 365 account has been disconnected.\n\n"
            "I can no longer access your calendar, emails, Teams, or files.\n"
            "Use /connect to reconnect anytime."
        )
    except Exception as e:
        logger.error(f"Failed to disconnect: {e}")
        await update.message.reply_text("Failed to disconnect. Please try again.")
