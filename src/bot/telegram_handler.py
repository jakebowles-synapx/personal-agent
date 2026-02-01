"""Telegram webhook handler and message processing."""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from src.agent import AgentOrchestrator
from src.config import settings

from .commands import (
    start_command,
    status_command,
    memories_command,
    clear_command,
    connect_command,
    disconnect_command,
    is_authorized,
)

logger = logging.getLogger(__name__)


class TelegramHandler:
    """Handles Telegram bot interactions."""

    def __init__(self) -> None:
        self.application = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .build()
        )
        self.orchestrator = AgentOrchestrator()

        # Store orchestrator in bot_data for command handlers
        self.application.bot_data["orchestrator"] = self.orchestrator

        # Register handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register command and message handlers."""
        # Command handlers
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("status", status_command))
        self.application.add_handler(CommandHandler("memories", memories_command))
        self.application.add_handler(CommandHandler("clear", clear_command))
        self.application.add_handler(CommandHandler("connect", connect_command))
        self.application.add_handler(CommandHandler("disconnect", disconnect_command))

        # Message handler for regular text messages
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

    async def _handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming text messages."""
        if not update.effective_user or not update.message or not update.message.text:
            return

        user_id = update.effective_user.id

        if not is_authorized(user_id):
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return

        message_text = update.message.text
        logger.info(f"Received message from {user_id}: {message_text[:50]}...")

        # Show typing indicator
        await update.message.chat.send_action("typing")

        try:
            # Process message through the agent
            response = await self.orchestrator.process_message(
                user_id=str(user_id),
                message=message_text,
            )
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await update.message.reply_text(
                "Sorry, I encountered an error processing your message. Please try again."
            )

    async def initialize(self) -> None:
        """Initialize the bot application."""
        await self.application.initialize()

    async def start(self) -> None:
        """Start the bot (for webhook mode)."""
        await self.application.start()

    async def stop(self) -> None:
        """Stop the bot."""
        await self.application.stop()
        await self.application.shutdown()

    async def process_update(self, update_data: dict) -> None:
        """Process an incoming webhook update."""
        update = Update.de_json(update_data, self.application.bot)
        await self.application.process_update(update)

    async def set_webhook(self) -> None:
        """Set the webhook URL for the bot."""
        webhook_url = settings.telegram_webhook_url
        await self.application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")

    async def delete_webhook(self) -> None:
        """Delete the webhook (for switching to polling mode)."""
        await self.application.bot.delete_webhook()
        logger.info("Webhook deleted")

    async def send_message(self, user_id: str, text: str) -> None:
        """Send a message to a user."""
        try:
            await self.application.bot.send_message(chat_id=int(user_id), text=text)
        except Exception as e:
            logger.error(f"Failed to send message to user {user_id}: {e}")
