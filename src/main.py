"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.agent import AgentOrchestrator
from src.api import threads_router, memories_router, microsoft_router, harvest_router
from src.api.threads import set_orchestrator as set_threads_orchestrator
from src.api.memories import set_orchestrator as set_memories_orchestrator
from src.api.microsoft import set_orchestrator as set_microsoft_orchestrator
from src.api.harvest import set_orchestrator as set_harvest_orchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global orchestrator
orchestrator: AgentOrchestrator | None = None

# Path to React build
WEB_DIR = Path(__file__).parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global orchestrator

    logger.info("Starting Personal Agent...")

    # Initialize orchestrator
    orchestrator = AgentOrchestrator()

    # Set orchestrator for API routers
    set_threads_orchestrator(orchestrator)
    set_memories_orchestrator(orchestrator)
    set_microsoft_orchestrator(orchestrator)
    set_harvest_orchestrator(orchestrator)

    logger.info("Agent started successfully!")

    yield

    # Shutdown
    logger.info("Shutting down...")
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Personal Agent",
    description="A personal AI assistant with web interface",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount API routers
app.include_router(threads_router)
app.include_router(memories_router)
app.include_router(microsoft_router)
app.include_router(harvest_router)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "orchestrator": orchestrator is not None,
            "memory": True,
            "llm": True,
            "microsoft": orchestrator.is_microsoft_connected() if orchestrator else False,
            "harvest": orchestrator.is_harvest_connected() if orchestrator else False,
        },
    }


@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle Microsoft OAuth callback."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")

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
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Failed</title>
                <style>
                    body {{ font-family: system-ui, sans-serif; background: #1a1a1a; color: #e5e5e5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
                    .container {{ text-align: center; padding: 2rem; }}
                    h1 {{ color: #ef4444; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Authentication Failed</h1>
                    <p>Error: {error}</p>
                    <p>{error_description or 'An unknown error occurred.'}</p>
                    <p>Please close this window and try again.</p>
                </div>
            </body>
            </html>
            """,
            status_code=400,
        )

    # Validate required parameters
    if not code or not state:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Invalid Request</title>
                <style>
                    body { font-family: system-ui, sans-serif; background: #1a1a1a; color: #e5e5e5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
                    .container { text-align: center; padding: 2rem; }
                    h1 { color: #ef4444; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Invalid Request</h1>
                    <p>Missing required parameters.</p>
                    <p>Please close this window and try again.</p>
                </div>
            </body>
            </html>
            """,
            status_code=400,
        )

    try:
        # Handle the OAuth callback through the orchestrator's auth
        auth = orchestrator.auth
        await auth.handle_callback(code=code, state=state)

        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Connected Successfully</title>
                <style>
                    body { font-family: system-ui, sans-serif; background: #1a1a1a; color: #e5e5e5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
                    .container { text-align: center; padding: 2rem; }
                    h1 { color: #22c55e; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Connected Successfully!</h1>
                    <p>Your Microsoft 365 account has been linked.</p>
                    <p>You can close this window and return to the app.</p>
                    <script>setTimeout(function() { window.close(); }, 2000);</script>
                </div>
            </body>
            </html>
            """,
            status_code=200,
        )

    except ValueError as e:
        logger.error(f"OAuth callback error: {e}")
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Failed</title>
                <style>
                    body {{ font-family: system-ui, sans-serif; background: #1a1a1a; color: #e5e5e5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
                    .container {{ text-align: center; padding: 2rem; }}
                    h1 {{ color: #ef4444; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Authentication Failed</h1>
                    <p>{str(e)}</p>
                    <p>Please close this window and try again.</p>
                </div>
            </body>
            </html>
            """,
            status_code=400,
        )

    except Exception as e:
        logger.error(f"Unexpected OAuth error: {e}", exc_info=True)
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Error</title>
                <style>
                    body { font-family: system-ui, sans-serif; background: #1a1a1a; color: #e5e5e5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
                    .container { text-align: center; padding: 2rem; }
                    h1 { color: #ef4444; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Something Went Wrong</h1>
                    <p>An unexpected error occurred during authentication.</p>
                    <p>Please close this window and try again.</p>
                </div>
            </body>
            </html>
            """,
            status_code=500,
        )


# Serve React frontend - must be after API routes
if WEB_DIR.exists():
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA for all non-API routes."""
        # Try to serve the requested file first
        file_path = WEB_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # Fall back to index.html for SPA routing
        return FileResponse(WEB_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        """Development placeholder when frontend not built."""
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Personal Agent</title>
                <style>
                    body { font-family: system-ui, sans-serif; background: #1a1a1a; color: #e5e5e5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
                    .container { text-align: center; padding: 2rem; }
                    code { background: #2d2d2d; padding: 0.25rem 0.5rem; border-radius: 4px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Personal Agent API</h1>
                    <p>Frontend not built. Run:</p>
                    <p><code>cd web && npm install && npm run build</code></p>
                    <p>API available at <code>/api/</code></p>
                </div>
            </body>
            </html>
            """
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
