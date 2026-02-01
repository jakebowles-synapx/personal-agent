"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.agent import AgentOrchestrator
from src.api import (
    threads_router,
    memories_router,
    microsoft_router,
    harvest_router,
    agents_router,
    knowledge_router,
    recommendations_router,
)
from src.api.threads import set_orchestrator as set_threads_orchestrator, set_chat_agent
from src.api.memories import set_orchestrator as set_memories_orchestrator
from src.api.microsoft import set_orchestrator as set_microsoft_orchestrator
from src.api.harvest import set_orchestrator as set_harvest_orchestrator
from src.api.agents import set_registry, set_scheduler
from src.api.knowledge import set_knowledge_manager
from src.api.recommendations import set_knowledge_manager_for_recommendations
from src.config import settings
from src.db import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
orchestrator: AgentOrchestrator | None = None
scheduler = None
registry = None

# Path to React build
WEB_DIR = Path(__file__).parent.parent / "web" / "dist"


def _init_agents():
    """Initialize the agent system (registry, agents, scheduler)."""
    from src.agents import get_registry, get_message_bus
    from src.agents.chat_agent import ChatAgent
    from src.agents.briefing_agent import BriefingAgent
    from src.agents.action_item_agent import ActionItemAgent
    from src.agents.memory_agent import MemoryAgent
    from src.agents.anomaly_agent import AnomalyAgent
    from src.scheduler import AgentScheduler
    from src.knowledge import KnowledgeManager
    from src.agent.tools import ToolExecutor

    global orchestrator, scheduler, registry

    # Get shared instances
    message_bus = get_message_bus()
    registry = get_registry()

    # Create knowledge manager
    knowledge_manager = KnowledgeManager(llm_client=orchestrator.llm)

    # Create tool executor with auth
    tool_executor = ToolExecutor(orchestrator.auth)

    # Register ChatAgent
    chat_agent = ChatAgent(
        message_bus=message_bus,
        knowledge_manager=knowledge_manager,
        memory_client=orchestrator.memory,
        llm_client=orchestrator.llm,
        conversation_history=orchestrator.history,
        auth=orchestrator.auth,
    )
    registry.register(chat_agent)
    set_chat_agent(chat_agent)  # Set for threads API

    # Register BriefingAgent
    briefing_agent = BriefingAgent(
        message_bus=message_bus,
        knowledge_manager=knowledge_manager,
        memory_client=orchestrator.memory,
        llm_client=orchestrator.llm,
        auth=orchestrator.auth,
        tool_executor=tool_executor,
    )
    registry.register(briefing_agent)

    # Register ActionItemAgent
    action_item_agent = ActionItemAgent(
        message_bus=message_bus,
        knowledge_manager=knowledge_manager,
        memory_client=orchestrator.memory,
        llm_client=orchestrator.llm,
        auth=orchestrator.auth,
        tool_executor=tool_executor,
    )
    registry.register(action_item_agent)

    # Register MemoryAgent
    memory_agent = MemoryAgent(
        message_bus=message_bus,
        knowledge_manager=knowledge_manager,
        memory_client=orchestrator.memory,
        llm_client=orchestrator.llm,
        auth=orchestrator.auth,
        tool_executor=tool_executor,
    )
    registry.register(memory_agent)

    # Register AnomalyAgent
    anomaly_agent = AnomalyAgent(
        message_bus=message_bus,
        knowledge_manager=knowledge_manager,
        memory_client=orchestrator.memory,
        llm_client=orchestrator.llm,
        auth=orchestrator.auth,
        tool_executor=tool_executor,
    )
    registry.register(anomaly_agent)

    # Create and start scheduler
    scheduler = AgentScheduler(registry)
    scheduler.start()

    # Set up API dependencies
    set_registry(registry)
    set_scheduler(scheduler)
    set_knowledge_manager(knowledge_manager)
    set_knowledge_manager_for_recommendations(knowledge_manager)

    logger.info(f"Registered {len(registry.list_agents())} agents")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global orchestrator, scheduler

    logger.info("Starting Personal Agent...")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Initialize orchestrator (legacy, for existing API compatibility)
    orchestrator = AgentOrchestrator()

    # Set orchestrator for API routers (legacy)
    set_threads_orchestrator(orchestrator)
    set_memories_orchestrator(orchestrator)
    set_microsoft_orchestrator(orchestrator)
    set_harvest_orchestrator(orchestrator)

    # Initialize agent system
    _init_agents()

    logger.info("Agent system started successfully!")

    yield

    # Shutdown
    logger.info("Shutting down...")

    if scheduler:
        scheduler.stop()
        logger.info("Scheduler stopped")

    logger.info("Shutdown complete.")


app = FastAPI(
    title="Personal Agent",
    description="A personal AI assistant with web interface",
    version="0.2.0",
    lifespan=lifespan,
)

# Mount API routers
app.include_router(threads_router)
app.include_router(memories_router)
app.include_router(microsoft_router)
app.include_router(harvest_router)
app.include_router(agents_router)
app.include_router(knowledge_router)
app.include_router(recommendations_router)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    from src.recommendations.store import RecommendationStore

    pending_recs = RecommendationStore.count_pending()

    return {
        "status": "healthy",
        "services": {
            "orchestrator": orchestrator is not None,
            "memory": True,
            "llm": True,
            "microsoft": orchestrator.is_microsoft_connected() if orchestrator else False,
            "harvest": orchestrator.is_harvest_connected() if orchestrator else False,
            "scheduler": scheduler.is_running() if scheduler else False,
            "agents": len(registry.list_agents()) if registry else 0,
        },
        "recommendations": {
            "pending": pending_recs,
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
