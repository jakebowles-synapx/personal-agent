"""Anomaly agent - detects patterns and flags issues."""

import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from src.agents.base import BaseAgent
from src.config import settings

if TYPE_CHECKING:
    from src.agents.message_bus import MessageBus
    from src.knowledge.manager import KnowledgeManager
    from src.memory.mem0_client import MemoryClient
    from src.llm import AzureOpenAIClient
    from src.microsoft.auth import MicrosoftAuth
    from src.agent.tools import ToolExecutor

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default"


class AnomalyAgent(BaseAgent):
    """
    Agent that detects anomalies and patterns.

    Runs every 4 hours to:
    - Check project budgets for overruns (Harvest)
    - Detect missed meetings
    - Flag unusual patterns
    - Alert on important deadlines
    """

    name = "anomaly"
    description = "Detects anomalies in budgets, schedules, and patterns"

    def __init__(
        self,
        message_bus: "MessageBus",
        knowledge_manager: "KnowledgeManager | None" = None,
        memory_client: "MemoryClient | None" = None,
        llm_client: "AzureOpenAIClient | None" = None,
        auth: "MicrosoftAuth | None" = None,
        tool_executor: "ToolExecutor | None" = None,
    ) -> None:
        super().__init__(
            message_bus=message_bus,
            knowledge_manager=knowledge_manager,
            memory_client=memory_client,
            llm_client=llm_client,
        )
        self.auth = auth
        self.tool_executor = tool_executor

    async def execute(self) -> dict:
        """Check for anomalies and patterns."""
        logger.info("Checking for anomalies...")

        anomalies_found = 0
        checks_performed = 0

        # Check budget status (if Harvest connected)
        if self._is_harvest_connected():
            try:
                budget_anomalies = await self._check_budgets()
                anomalies_found += budget_anomalies
                checks_performed += 1
            except Exception as e:
                logger.error(f"Failed to check budgets: {e}")

            # Check team utilization
            try:
                util_anomalies = await self._check_utilization()
                anomalies_found += util_anomalies
                checks_performed += 1
            except Exception as e:
                logger.error(f"Failed to check utilization: {e}")

        # Check calendar for issues (if Microsoft connected)
        if self.auth and self.auth.is_connected(DEFAULT_USER_ID):
            try:
                calendar_anomalies = await self._check_calendar()
                anomalies_found += calendar_anomalies
                checks_performed += 1
            except Exception as e:
                logger.error(f"Failed to check calendar: {e}")

        return {
            "summary": f"Found {anomalies_found} anomalies from {checks_performed} checks",
            "items_processed": checks_performed,
        }

    def _is_harvest_connected(self) -> bool:
        """Check if Harvest is configured."""
        return bool(settings.harvest_account_id and settings.harvest_access_token)

    async def _check_budgets(self) -> int:
        """Check project budgets for overruns."""
        if not self.tool_executor:
            return 0

        # Get all active projects
        result = await self.tool_executor.execute(
            user_id=DEFAULT_USER_ID,
            tool_name="harvest_get_projects",
            arguments={"is_active": True},
        )

        projects = result.get("projects", [])
        if not projects:
            return 0

        anomalies = 0

        for project in projects:
            project_id = project.get("id")
            project_name = project.get("name", "Unknown")

            if not project_id:
                continue

            # Get project budget details
            try:
                details = await self.tool_executor.execute(
                    user_id=DEFAULT_USER_ID,
                    tool_name="harvest_get_project_details",
                    arguments={"project_id": project_id},
                )

                budget_status = details.get("budget_status", {})

                # Check for budget concerns
                budget_spent_pct = budget_status.get("budget_spent_percentage", 0)
                is_over_budget = budget_status.get("is_over_budget", False)
                budget_remaining = budget_status.get("budget_remaining")

                if is_over_budget:
                    self.create_recommendation(
                        title=f"Budget Exceeded: {project_name}",
                        content=f"Project '{project_name}' has exceeded its budget.\n\n"
                               f"Budget spent: {budget_spent_pct:.1f}%\n"
                               f"Over by: {abs(budget_remaining) if budget_remaining else 'Unknown'} hours",
                        priority="urgent",
                        metadata={
                            "type": "budget_alert",
                            "project_id": project_id,
                            "project_name": project_name,
                            "budget_spent_pct": budget_spent_pct,
                        },
                    )
                    anomalies += 1

                elif budget_spent_pct > 80:
                    self.create_recommendation(
                        title=f"Budget Warning: {project_name}",
                        content=f"Project '{project_name}' is approaching budget limit.\n\n"
                               f"Budget spent: {budget_spent_pct:.1f}%\n"
                               f"Remaining: {budget_remaining if budget_remaining else 'Unknown'} hours",
                        priority="high",
                        metadata={
                            "type": "budget_warning",
                            "project_id": project_id,
                            "project_name": project_name,
                            "budget_spent_pct": budget_spent_pct,
                        },
                    )
                    anomalies += 1

            except Exception as e:
                logger.warning(f"Failed to check budget for {project_name}: {e}")

        return anomalies

    async def _check_utilization(self) -> int:
        """Check team utilization for anomalies."""
        if not self.tool_executor:
            return 0

        # Get team report for last 7 days
        result = await self.tool_executor.execute(
            user_id=DEFAULT_USER_ID,
            tool_name="harvest_team_report",
            arguments={},
        )

        team_data = result.get("team_members", [])
        if not team_data:
            return 0

        anomalies = 0

        for member in team_data:
            name = member.get("name", "Unknown")
            hours = member.get("total_hours", 0)
            capacity = member.get("weekly_capacity", 40)

            # Check for very low utilization (< 50% over a week)
            utilization = (hours / capacity * 100) if capacity > 0 else 0

            if utilization < 30 and capacity > 0:
                self.create_recommendation(
                    title=f"Low Utilization: {name}",
                    content=f"{name} has low time tracking this week.\n\n"
                           f"Hours logged: {hours:.1f}\n"
                           f"Capacity: {capacity} hours\n"
                           f"Utilization: {utilization:.1f}%\n\n"
                           f"This could indicate missing time entries or availability for new work.",
                    priority="normal",
                    metadata={
                        "type": "utilization_low",
                        "member_name": name,
                        "hours": hours,
                        "utilization": utilization,
                    },
                )
                anomalies += 1

            # Check for overtime (> 120% utilization)
            elif utilization > 120:
                self.create_recommendation(
                    title=f"Overtime Alert: {name}",
                    content=f"{name} is significantly over capacity this week.\n\n"
                           f"Hours logged: {hours:.1f}\n"
                           f"Capacity: {capacity} hours\n"
                           f"Utilization: {utilization:.1f}%\n\n"
                           f"Consider workload balancing.",
                    priority="high",
                    metadata={
                        "type": "utilization_high",
                        "member_name": name,
                        "hours": hours,
                        "utilization": utilization,
                    },
                )
                anomalies += 1

        return anomalies

    async def _check_calendar(self) -> int:
        """Check calendar for issues."""
        if not self.tool_executor:
            return 0

        # Get today's and tomorrow's events
        result = await self.tool_executor.execute(
            user_id=DEFAULT_USER_ID,
            tool_name="get_calendar_events",
            arguments={"days": 2, "past_days": 1},
        )

        events = result.get("events", [])
        if not events:
            return 0

        anomalies = 0
        now = datetime.now(timezone.utc)

        # Check for conflicting meetings
        conflicts = self._find_conflicts(events)
        for conflict in conflicts:
            self.create_recommendation(
                title="Meeting Conflict Detected",
                content=f"Overlapping meetings found:\n\n"
                       f"1. {conflict['event1']['subject']} ({conflict['event1']['start']})\n"
                       f"2. {conflict['event2']['subject']} ({conflict['event2']['start']})",
                priority="high",
                metadata={
                    "type": "calendar_conflict",
                    "events": [conflict['event1']['id'], conflict['event2']['id']],
                },
            )
            anomalies += 1

        # Check for meetings without responses
        # Note: GraphClient returns simplified format with start/end as strings
        pending_responses = [
            e for e in events
            if any(a.get("status") == "notResponded" for a in e.get("attendees", []))
            and self._parse_datetime(e.get("start")) > now
        ]

        if len(pending_responses) > 3:
            self.create_recommendation(
                title="Pending Meeting Responses",
                content=f"You have {len(pending_responses)} meeting invitations without responses.\n\n"
                       "Meetings:\n" +
                       "\n".join(f"- {e.get('subject', 'Unknown')}" for e in pending_responses[:5]),
                priority="normal",
                metadata={
                    "type": "pending_responses",
                    "count": len(pending_responses),
                },
            )
            anomalies += 1

        return anomalies

    def _find_conflicts(self, events: list[dict]) -> list[dict]:
        """Find overlapping events."""
        conflicts = []
        # GraphClient returns simplified format with start/end as strings
        sorted_events = sorted(
            events,
            key=lambda e: e.get("start", "")
        )

        for i, event1 in enumerate(sorted_events):
            start1 = self._parse_datetime(event1.get("start"))
            end1 = self._parse_datetime(event1.get("end"))

            if not start1 or not end1:
                continue

            for event2 in sorted_events[i + 1:]:
                start2 = self._parse_datetime(event2.get("start"))
                end2 = self._parse_datetime(event2.get("end"))

                if not start2 or not end2:
                    continue

                # Check overlap
                if start1 < end2 and end1 > start2:
                    # Skip all-day events
                    if event1.get("isAllDay") or event2.get("isAllDay"):
                        continue

                    conflicts.append({
                        "event1": {
                            "id": event1.get("id"),
                            "subject": event1.get("subject"),
                            "start": start1.isoformat(),
                        },
                        "event2": {
                            "id": event2.get("id"),
                            "subject": event2.get("subject"),
                            "start": start2.isoformat(),
                        },
                    })

        return conflicts

    def _parse_datetime(self, dt_string: str | None) -> datetime | None:
        """Parse datetime string."""
        if not dt_string:
            return None

        try:
            # Handle various formats
            dt_string = dt_string.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_string)
        except ValueError:
            return None
