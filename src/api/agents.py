"""Agent status and control API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.agents.registry import AgentRegistry
from src.scheduler import AgentScheduler
from src.db import AgentRunsDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])

# Dependencies - set by main.py
_registry: AgentRegistry | None = None
_scheduler: AgentScheduler | None = None


def get_registry() -> AgentRegistry:
    """Get the agent registry."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Agent registry not initialized")
    return _registry


def get_scheduler() -> AgentScheduler:
    """Get the scheduler."""
    if _scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    return _scheduler


def set_registry(registry: AgentRegistry) -> None:
    """Set the agent registry."""
    global _registry
    _registry = registry


def set_scheduler(scheduler: AgentScheduler) -> None:
    """Set the scheduler."""
    global _scheduler
    _scheduler = scheduler


# Response models
class AgentStatus(BaseModel):
    name: str
    description: str
    last_run: dict | None
    next_run: str | None
    is_scheduled: bool


class AgentRunResponse(BaseModel):
    id: int
    agent_name: str
    started_at: str
    completed_at: str | None
    status: str
    summary: str | None
    items_processed: int
    error_message: str | None


class TriggerResponse(BaseModel):
    success: bool
    agent: str
    error: str | None = None


# Endpoints
@router.get("", response_model=list[AgentStatus])
async def list_agents(
    registry: Annotated[AgentRegistry, Depends(get_registry)],
    scheduler: Annotated[AgentScheduler, Depends(get_scheduler)],
):
    """List all registered agents with their status."""
    agents = registry.list_agents()
    result = []

    for agent_info in agents:
        name = agent_info["name"]
        next_run = scheduler.get_next_run_time(name)

        result.append(AgentStatus(
            name=name,
            description=agent_info["description"],
            last_run=agent_info.get("last_run"),
            next_run=next_run.isoformat() if next_run else None,
            is_scheduled=name in registry.get_scheduled_agents(),
        ))

    return result


@router.get("/{agent_name}", response_model=AgentStatus)
async def get_agent(
    agent_name: str,
    registry: Annotated[AgentRegistry, Depends(get_registry)],
    scheduler: Annotated[AgentScheduler, Depends(get_scheduler)],
):
    """Get status for a specific agent."""
    agent = registry.get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    next_run = scheduler.get_next_run_time(agent_name)

    return AgentStatus(
        name=agent.name,
        description=agent.description,
        last_run=agent.get_last_run(),
        next_run=next_run.isoformat() if next_run else None,
        is_scheduled=agent_name in registry.get_scheduled_agents(),
    )


@router.post("/{agent_name}/trigger", response_model=TriggerResponse)
async def trigger_agent(
    agent_name: str,
    scheduler: Annotated[AgentScheduler, Depends(get_scheduler)],
):
    """Manually trigger an agent to run."""
    result = await scheduler.trigger_agent(agent_name)
    return TriggerResponse(
        success=result["success"],
        agent=agent_name,
        error=result.get("error"),
    )


@router.get("/{agent_name}/runs", response_model=list[AgentRunResponse])
async def get_agent_runs(
    agent_name: str,
    registry: Annotated[AgentRegistry, Depends(get_registry)],
    limit: int = 20,
    hours: int = 168,  # 7 days default
):
    """Get recent runs for an agent."""
    if not registry.has_agent(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    runs = AgentRunsDB.list_recent(agent_name=agent_name, limit=limit, hours=hours)
    return runs


@router.get("/runs/recent", response_model=list[AgentRunResponse])
async def get_recent_runs(
    limit: int = 50,
    hours: int = 24,
):
    """Get recent runs across all agents."""
    runs = AgentRunsDB.list_recent(limit=limit, hours=hours)
    return runs


@router.post("/{agent_name}/pause")
async def pause_agent(
    agent_name: str,
    scheduler: Annotated[AgentScheduler, Depends(get_scheduler)],
):
    """Pause a scheduled agent."""
    success = scheduler.pause_job(agent_name)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to pause agent")
    return {"status": "paused", "agent": agent_name}


@router.post("/{agent_name}/resume")
async def resume_agent(
    agent_name: str,
    scheduler: Annotated[AgentScheduler, Depends(get_scheduler)],
):
    """Resume a paused agent."""
    success = scheduler.resume_job(agent_name)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resume agent")
    return {"status": "resumed", "agent": agent_name}


@router.get("/scheduler/status")
async def get_scheduler_status(
    scheduler: Annotated[AgentScheduler, Depends(get_scheduler)],
):
    """Get scheduler status."""
    return {
        "running": scheduler.is_running(),
        "jobs": scheduler.get_job_status(),
    }
