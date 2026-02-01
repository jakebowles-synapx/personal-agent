"""Harvest time tracking API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.agent import AgentOrchestrator
from src.harvest import HarvestClient
from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/harvest", tags=["harvest"])

# Dependency to get orchestrator instance
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator instance."""
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return _orchestrator


def set_orchestrator(orchestrator: AgentOrchestrator) -> None:
    """Set the global orchestrator instance."""
    global _orchestrator
    _orchestrator = orchestrator


# Response models
class HarvestStatusResponse(BaseModel):
    configured: bool
    connected: bool
    company_name: str | None = None
    error: str | None = None


@router.get("/status", response_model=HarvestStatusResponse)
async def get_status(
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Get Harvest connection status."""
    configured = orchestrator.is_harvest_connected()

    if not configured:
        return {
            "configured": False,
            "connected": False,
            "company_name": None,
            "error": "Harvest not configured. Set HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in .env",
        }

    # Test the connection
    try:
        client = HarvestClient(
            account_id=settings.harvest_account_id,
            access_token=settings.harvest_access_token,
        )
        result = await client.test_connection()

        if result.get("connected"):
            return {
                "configured": True,
                "connected": True,
                "company_name": result.get("company_name"),
                "error": None,
            }
        else:
            return {
                "configured": True,
                "connected": False,
                "company_name": None,
                "error": result.get("error", "Failed to connect to Harvest"),
            }

    except Exception as e:
        logger.error(f"Error testing Harvest connection: {e}")
        return {
            "configured": True,
            "connected": False,
            "company_name": None,
            "error": str(e),
        }
