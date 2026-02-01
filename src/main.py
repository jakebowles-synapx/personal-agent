"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

from src.bot import TelegramHandler
from src.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global telegram handler
telegram_handler: TelegramHandler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global telegram_handler

    logger.info("Starting Personal Business Agent...")

    # Initialize Telegram handler
    telegram_handler = TelegramHandler()
    await telegram_handler.initialize()
    await telegram_handler.start()

    # Set webhook
    try:
        await telegram_handler.set_webhook()
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

    logger.info("Bot started successfully!")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if telegram_handler:
        await telegram_handler.stop()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Personal Business Agent",
    description="A personal AI assistant accessible via Telegram",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "personal-business-agent"}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "services": {
            "telegram": telegram_handler is not None,
            "memory": True,
            "llm": True,
        },
    }


@app.post("/webhook")
async def webhook(request: Request):
    """Handle incoming Telegram webhook updates."""
    if not telegram_handler:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    try:
        update_data = await request.json()
        await telegram_handler.process_update(update_data)
        return JSONResponse(content={"ok": True})
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Return 200 to prevent Telegram from retrying
        return JSONResponse(content={"ok": False, "error": str(e)})


@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle Microsoft OAuth callback."""
    if not telegram_handler:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # Get OAuth parameters
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description")

    # Handle OAuth errors
    if error:
        logger.error(f"OAuth error: {error} - {error_description}")
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #d32f2f;">Authentication Failed</h1>
                <p>Error: {error}</p>
                <p>{error_description or 'An unknown error occurred.'}</p>
                <p>Please close this window and try again using /connect in Telegram.</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    # Validate required parameters
    if not code or not state:
        return HTMLResponse(
            content="""
            <html>
            <head><title>Invalid Request</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #d32f2f;">Invalid Request</h1>
                <p>Missing required parameters.</p>
                <p>Please close this window and try again using /connect in Telegram.</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    try:
        # Handle the OAuth callback through the orchestrator's auth
        auth = telegram_handler.orchestrator.auth
        result = await auth.handle_callback(code=code, state=state)

        user_id = result["user_id"]

        # Notify user via Telegram
        await telegram_handler.send_message(
            user_id=user_id,
            text=(
                "Your Microsoft 365 account has been connected successfully!\n\n"
                "You can now ask me about your:\n"
                "- Calendar and upcoming meetings\n"
                "- Emails in your inbox\n"
                "- Teams chat messages\n"
                "- Files in OneDrive and SharePoint\n\n"
                "Try asking: \"What meetings do I have today?\" or \"Any important emails?\""
            ),
        )

        return HTMLResponse(
            content="""
            <html>
            <head><title>Connected Successfully</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center;">
                <h1 style="color: #4caf50;">Connected Successfully!</h1>
                <p>Your Microsoft 365 account has been linked to your Telegram bot.</p>
                <p style="margin-top: 30px;">You can close this window and return to Telegram.</p>
                <script>setTimeout(function() { window.close(); }, 3000);</script>
            </body>
            </html>
            """,
            status_code=200,
        )

    except ValueError as e:
        logger.error(f"OAuth callback error: {e}")
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #d32f2f;">Authentication Failed</h1>
                <p>{str(e)}</p>
                <p>Please close this window and try again using /connect in Telegram.</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    except Exception as e:
        logger.error(f"Unexpected OAuth error: {e}", exc_info=True)
        return HTMLResponse(
            content="""
            <html>
            <head><title>Error</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #d32f2f;">Something Went Wrong</h1>
                <p>An unexpected error occurred during authentication.</p>
                <p>Please close this window and try again using /connect in Telegram.</p>
            </body>
            </html>
            """,
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
