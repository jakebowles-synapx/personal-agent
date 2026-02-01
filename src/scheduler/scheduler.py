"""APScheduler-based scheduler for running agents on schedules."""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings

if TYPE_CHECKING:
    from src.agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


class AgentScheduler:
    """Manages scheduled execution of agents using APScheduler."""

    def __init__(self, registry: "AgentRegistry") -> None:
        self.registry = registry
        self._scheduler: AsyncIOScheduler | None = None
        self._running = False

    def _create_scheduler(self) -> AsyncIOScheduler:
        """Create and configure the scheduler."""
        # Use in-memory job store (jobs re-register on startup)
        scheduler = AsyncIOScheduler(
            job_defaults={
                "coalesce": True,  # Combine missed runs into one
                "max_instances": 1,  # Only one instance per job
                "misfire_grace_time": 300,  # 5 minute grace period for missed jobs
            },
            timezone="UTC"
        )

        return scheduler

    def start(self) -> None:
        """Start the scheduler and register all agent jobs."""
        if not settings.scheduler_enabled:
            logger.info("Scheduler is disabled in settings")
            return

        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._scheduler = self._create_scheduler()

        # Register scheduled agents
        self._register_agent_jobs()

        self._scheduler.start()
        self._running = True
        logger.info("Agent scheduler started")

        # Log all scheduled jobs
        jobs = self._scheduler.get_jobs()
        for job in jobs:
            logger.info(f"Scheduled job: {job.id} - next run: {job.next_run_time}")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Agent scheduler stopped")

    def _register_agent_jobs(self) -> None:
        """Register all agent jobs with their schedules."""
        if not self._scheduler:
            return

        # Define agent schedules from config
        agent_schedules = {
            "briefing": settings.briefing_schedule,
            "action_item": settings.action_item_schedule,
            "memory": settings.memory_schedule,
            "anomaly": settings.anomaly_schedule,
        }

        for agent_name, cron_schedule in agent_schedules.items():
            if not self.registry.has_agent(agent_name):
                logger.warning(f"Agent '{agent_name}' not registered, skipping schedule")
                continue

            try:
                trigger = CronTrigger.from_crontab(cron_schedule)
                job_id = f"agent_{agent_name}"

                # Remove existing job if it exists
                existing_job = self._scheduler.get_job(job_id)
                if existing_job:
                    self._scheduler.remove_job(job_id)

                # Add the job
                self._scheduler.add_job(
                    self._run_agent,
                    trigger=trigger,
                    id=job_id,
                    name=f"Run {agent_name} agent",
                    args=[agent_name],
                    replace_existing=True,
                )
                logger.info(f"Registered job '{job_id}' with schedule '{cron_schedule}'")

            except Exception as e:
                logger.error(f"Failed to register job for agent '{agent_name}': {e}")

    async def _run_agent(self, agent_name: str) -> None:
        """Execute an agent's run method."""
        logger.info(f"Scheduled execution of agent '{agent_name}'")
        try:
            agent = self.registry.get_agent(agent_name)
            if agent:
                await agent.run()
            else:
                logger.error(f"Agent '{agent_name}' not found in registry")
        except Exception as e:
            logger.error(f"Error running agent '{agent_name}': {e}", exc_info=True)

    async def trigger_agent(self, agent_name: str) -> dict:
        """Manually trigger an agent to run immediately."""
        logger.info(f"Manual trigger of agent '{agent_name}'")

        if not self.registry.has_agent(agent_name):
            return {"success": False, "error": f"Agent '{agent_name}' not found"}

        try:
            agent = self.registry.get_agent(agent_name)
            if agent:
                await agent.run()
                return {"success": True, "agent": agent_name}
            else:
                return {"success": False, "error": f"Agent '{agent_name}' not found"}
        except Exception as e:
            logger.error(f"Error triggering agent '{agent_name}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def get_job_status(self) -> list[dict]:
        """Get status of all scheduled jobs."""
        if not self._scheduler:
            return []

        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs

    def get_next_run_time(self, agent_name: str) -> datetime | None:
        """Get the next scheduled run time for an agent."""
        if not self._scheduler:
            return None

        job_id = f"agent_{agent_name}"
        job = self._scheduler.get_job(job_id)
        return job.next_run_time if job else None

    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running

    def pause_job(self, agent_name: str) -> bool:
        """Pause a scheduled job."""
        if not self._scheduler:
            return False

        job_id = f"agent_{agent_name}"
        try:
            self._scheduler.pause_job(job_id)
            logger.info(f"Paused job '{job_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed to pause job '{job_id}': {e}")
            return False

    def resume_job(self, agent_name: str) -> bool:
        """Resume a paused job."""
        if not self._scheduler:
            return False

        job_id = f"agent_{agent_name}"
        try:
            self._scheduler.resume_job(job_id)
            logger.info(f"Resumed job '{job_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed to resume job '{job_id}': {e}")
            return False
