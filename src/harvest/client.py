"""Harvest API V2 client for time tracking and team management."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HARVEST_BASE_URL = "https://api.harvestapp.com/v2"


class HarvestClient:
    """Client for Harvest API V2."""

    def __init__(self, account_id: str, access_token: str) -> None:
        self.account_id = account_id
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Harvest-Account-Id": account_id,
            "User-Agent": "PersonalAgent",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Make a request to the Harvest API."""
        url = f"{HARVEST_BASE_URL}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                timeout=30.0,
            )

            if response.status_code == 401:
                raise PermissionError("Harvest access token invalid or expired")
            elif response.status_code == 403:
                raise PermissionError("Insufficient Harvest permissions")
            elif response.status_code == 429:
                raise Exception("Harvest rate limit exceeded. Please wait and try again.")
            elif response.status_code >= 400:
                error_msg = response.text
                raise Exception(f"Harvest API error ({response.status_code}): {error_msg}")

            return response.json() if response.content else {}

    async def _paginated_request(
        self,
        endpoint: str,
        params: dict | None = None,
        max_pages: int = 10,
    ) -> list[dict]:
        """Make paginated requests and return all results."""
        params = params or {}
        params["per_page"] = 100
        all_results = []
        page = 1

        while page <= max_pages:
            params["page"] = page
            result = await self._request("GET", endpoint, params=params)

            # Get the key that contains the array (varies by endpoint)
            data_key = None
            for key in result:
                if isinstance(result[key], list):
                    data_key = key
                    break

            if data_key:
                all_results.extend(result[data_key])

            # Check if there are more pages
            total_pages = result.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

        return all_results

    # ==================== USERS/TEAM ====================

    async def get_users(self, is_active: bool | None = True) -> list[dict]:
        """
        Get all team members.

        Args:
            is_active: Filter by active status (default: True for active only)
        """
        params = {}
        if is_active is not None:
            params["is_active"] = str(is_active).lower()

        users = await self._paginated_request("/users", params)

        return [
            {
                "id": user["id"],
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name", ""),
                "email": user.get("email", ""),
                "is_active": user.get("is_active", False),
                "is_admin": user.get("is_admin", False),
                "is_project_manager": user.get("is_project_manager", False),
                "weekly_capacity": user.get("weekly_capacity", 0) / 3600,  # Convert to hours
                "default_hourly_rate": user.get("default_hourly_rate"),
                "roles": user.get("roles", []),
                "created_at": user.get("created_at", ""),
            }
            for user in users
        ]

    async def get_user(self, user_id: int) -> dict:
        """Get a specific user's details."""
        result = await self._request("GET", f"/users/{user_id}")

        return {
            "id": result["id"],
            "first_name": result.get("first_name", ""),
            "last_name": result.get("last_name", ""),
            "email": result.get("email", ""),
            "phone": result.get("phone", ""),
            "timezone": result.get("timezone", ""),
            "is_active": result.get("is_active", False),
            "is_admin": result.get("is_admin", False),
            "is_project_manager": result.get("is_project_manager", False),
            "weekly_capacity": result.get("weekly_capacity", 0) / 3600,
            "default_hourly_rate": result.get("default_hourly_rate"),
            "cost_rate": result.get("cost_rate"),
            "roles": result.get("roles", []),
            "created_at": result.get("created_at", ""),
            "updated_at": result.get("updated_at", ""),
        }

    async def get_user_project_assignments(self, user_id: int) -> list[dict]:
        """Get projects assigned to a specific user."""
        assignments = await self._paginated_request(f"/users/{user_id}/project_assignments")

        return [
            {
                "id": assignment["id"],
                "is_active": assignment.get("is_active", False),
                "is_project_manager": assignment.get("is_project_manager", False),
                "hourly_rate": assignment.get("hourly_rate"),
                "budget": assignment.get("budget"),
                "project": {
                    "id": assignment.get("project", {}).get("id"),
                    "name": assignment.get("project", {}).get("name", ""),
                    "code": assignment.get("project", {}).get("code", ""),
                },
                "client": {
                    "id": assignment.get("client", {}).get("id"),
                    "name": assignment.get("client", {}).get("name", ""),
                },
                "task_assignments": [
                    {
                        "id": ta.get("id"),
                        "task_name": ta.get("task", {}).get("name", ""),
                        "is_active": ta.get("is_active", False),
                        "billable": ta.get("billable", False),
                        "hourly_rate": ta.get("hourly_rate"),
                    }
                    for ta in assignment.get("task_assignments", [])
                ],
            }
            for assignment in assignments
        ]

    # ==================== TIME ENTRIES ====================

    async def get_time_entries(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        user_id: int | None = None,
        project_id: int | None = None,
    ) -> list[dict]:
        """
        Get time entries with optional filters.

        Args:
            from_date: Start date (YYYY-MM-DD format)
            to_date: End date (YYYY-MM-DD format)
            user_id: Filter by user
            project_id: Filter by project
        """
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if user_id:
            params["user_id"] = user_id
        if project_id:
            params["project_id"] = project_id

        entries = await self._paginated_request("/time_entries", params)

        return [
            {
                "id": entry["id"],
                "spent_date": entry.get("spent_date", ""),
                "hours": entry.get("hours", 0),
                "notes": entry.get("notes", ""),
                "is_running": entry.get("is_running", False),
                "billable": entry.get("billable", False),
                "billable_rate": entry.get("billable_rate"),
                "cost_rate": entry.get("cost_rate"),
                "user": {
                    "id": entry.get("user", {}).get("id"),
                    "name": entry.get("user", {}).get("name", ""),
                },
                "project": {
                    "id": entry.get("project", {}).get("id"),
                    "name": entry.get("project", {}).get("name", ""),
                    "code": entry.get("project", {}).get("code", ""),
                },
                "client": {
                    "id": entry.get("client", {}).get("id"),
                    "name": entry.get("client", {}).get("name", ""),
                },
                "task": {
                    "id": entry.get("task", {}).get("id"),
                    "name": entry.get("task", {}).get("name", ""),
                },
                "started_time": entry.get("started_time", ""),
                "ended_time": entry.get("ended_time", ""),
                "created_at": entry.get("created_at", ""),
            }
            for entry in entries
        ]

    async def get_time_entries_for_user(self, user_id: int, days: int = 7) -> list[dict]:
        """Get recent time entries for a specific user."""
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        return await self.get_time_entries(
            from_date=from_date,
            to_date=to_date,
            user_id=user_id,
        )

    async def get_today_time_entries(self) -> list[dict]:
        """Get time entries for today (what's being tracked right now)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return await self.get_time_entries(from_date=today, to_date=today)

    # ==================== PROJECTS ====================

    async def get_projects(self, is_active: bool | None = True) -> list[dict]:
        """
        Get projects.

        Args:
            is_active: Filter by active status (default: True for active only)
        """
        params = {}
        if is_active is not None:
            params["is_active"] = str(is_active).lower()

        projects = await self._paginated_request("/projects", params)

        return [
            {
                "id": project["id"],
                "name": project.get("name", ""),
                "code": project.get("code", ""),
                "is_active": project.get("is_active", False),
                "is_billable": project.get("is_billable", False),
                "bill_by": project.get("bill_by", ""),
                "budget_by": project.get("budget_by", ""),
                "budget": project.get("budget"),
                "budget_is_monthly": project.get("budget_is_monthly", False),
                "over_budget_notification_percentage": project.get("over_budget_notification_percentage"),
                "hourly_rate": project.get("hourly_rate"),
                "fee": project.get("fee"),
                "client": {
                    "id": project.get("client", {}).get("id"),
                    "name": project.get("client", {}).get("name", ""),
                },
                "starts_on": project.get("starts_on", ""),
                "ends_on": project.get("ends_on", ""),
                "created_at": project.get("created_at", ""),
                "notes": project.get("notes", ""),
            }
            for project in projects
        ]

    async def get_project(self, project_id: int) -> dict:
        """Get a single project's details."""
        result = await self._request("GET", f"/projects/{project_id}")

        return {
            "id": result["id"],
            "name": result.get("name", ""),
            "code": result.get("code", ""),
            "is_active": result.get("is_active", False),
            "is_billable": result.get("is_billable", False),
            "is_fixed_fee": result.get("is_fixed_fee", False),
            "bill_by": result.get("bill_by", ""),
            "budget_by": result.get("budget_by", ""),
            "budget": result.get("budget"),
            "budget_is_monthly": result.get("budget_is_monthly", False),
            "notify_when_over_budget": result.get("notify_when_over_budget", False),
            "over_budget_notification_percentage": result.get("over_budget_notification_percentage"),
            "show_budget_to_all": result.get("show_budget_to_all", False),
            "hourly_rate": result.get("hourly_rate"),
            "fee": result.get("fee"),
            "cost_budget": result.get("cost_budget"),
            "cost_budget_include_expenses": result.get("cost_budget_include_expenses", False),
            "client": {
                "id": result.get("client", {}).get("id"),
                "name": result.get("client", {}).get("name", ""),
            },
            "starts_on": result.get("starts_on", ""),
            "ends_on": result.get("ends_on", ""),
            "notes": result.get("notes", ""),
            "created_at": result.get("created_at", ""),
            "updated_at": result.get("updated_at", ""),
        }

    async def get_project_budget(self, project_id: int) -> dict:
        """
        Get budget status for a project by calculating hours/cost spent.

        Note: Harvest doesn't have a dedicated budget endpoint, so we calculate
        from time entries and project details.
        """
        # Get project details for budget info
        project = await self.get_project(project_id)

        # Get all time entries for this project
        entries = await self.get_time_entries(project_id=project_id)

        total_hours = sum(entry["hours"] for entry in entries)
        total_billable_hours = sum(
            entry["hours"] for entry in entries if entry["billable"]
        )

        budget = project.get("budget")
        budget_by = project.get("budget_by", "")

        result = {
            "project_id": project_id,
            "project_name": project.get("name", ""),
            "client_name": project.get("client", {}).get("name", ""),
            "budget_by": budget_by,
            "budget": budget,
            "budget_is_monthly": project.get("budget_is_monthly", False),
            "total_hours": round(total_hours, 2),
            "total_billable_hours": round(total_billable_hours, 2),
            "is_active": project.get("is_active", False),
        }

        # Calculate remaining if budget is set and it's an hours-based budget
        if budget and budget_by in ("project", "person"):
            result["hours_remaining"] = round(budget - total_hours, 2)
            result["percent_used"] = round((total_hours / budget) * 100, 1) if budget > 0 else 0

        return result

    # ==================== REPORTS ====================

    async def get_team_time_report(self, from_date: str, to_date: str) -> dict:
        """
        Get team hours summary by person.

        Args:
            from_date: Start date (YYYY-MM-DD format)
            to_date: End date (YYYY-MM-DD format)
        """
        params = {
            "from": from_date,
            "to": to_date,
        }

        result = await self._request("GET", "/reports/time/team", params=params)

        return {
            "from_date": from_date,
            "to_date": to_date,
            "results": [
                {
                    "user_id": row.get("user_id"),
                    "user_name": row.get("user_name", ""),
                    "total_hours": row.get("total_hours", 0),
                    "billable_hours": row.get("billable_hours", 0),
                    "billable_amount": row.get("billable_amount", 0),
                }
                for row in result.get("results", [])
            ],
            "total_hours": sum(row.get("total_hours", 0) for row in result.get("results", [])),
            "total_billable_hours": sum(row.get("billable_hours", 0) for row in result.get("results", [])),
        }

    async def get_project_time_report(self, from_date: str, to_date: str) -> dict:
        """
        Get project hours summary.

        Args:
            from_date: Start date (YYYY-MM-DD format)
            to_date: End date (YYYY-MM-DD format)
        """
        params = {
            "from": from_date,
            "to": to_date,
        }

        result = await self._request("GET", "/reports/time/projects", params=params)

        return {
            "from_date": from_date,
            "to_date": to_date,
            "results": [
                {
                    "project_id": row.get("project_id"),
                    "project_name": row.get("project_name", ""),
                    "client_id": row.get("client_id"),
                    "client_name": row.get("client_name", ""),
                    "total_hours": row.get("total_hours", 0),
                    "billable_hours": row.get("billable_hours", 0),
                    "billable_amount": row.get("billable_amount", 0),
                }
                for row in result.get("results", [])
            ],
            "total_hours": sum(row.get("total_hours", 0) for row in result.get("results", [])),
            "total_billable_hours": sum(row.get("billable_hours", 0) for row in result.get("results", [])),
        }

    async def get_running_timers(self) -> list[dict]:
        """Find any currently running timers."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        entries = await self.get_time_entries(from_date=today, to_date=today)

        running = [e for e in entries if e.get("is_running", False)]
        return running

    async def get_client_report(self, from_date: str, to_date: str) -> dict:
        """
        Get time by client.

        Args:
            from_date: Start date (YYYY-MM-DD format)
            to_date: End date (YYYY-MM-DD format)
        """
        params = {
            "from": from_date,
            "to": to_date,
        }

        result = await self._request("GET", "/reports/time/clients", params=params)

        return {
            "from_date": from_date,
            "to_date": to_date,
            "results": [
                {
                    "client_id": row.get("client_id"),
                    "client_name": row.get("client_name", ""),
                    "total_hours": row.get("total_hours", 0),
                    "billable_hours": row.get("billable_hours", 0),
                    "billable_amount": row.get("billable_amount", 0),
                }
                for row in result.get("results", [])
            ],
            "total_hours": sum(row.get("total_hours", 0) for row in result.get("results", [])),
            "total_billable_hours": sum(row.get("billable_hours", 0) for row in result.get("results", [])),
        }

    async def get_my_user_id(self) -> int | None:
        """Get the current authenticated user's ID."""
        result = await self._request("GET", "/users/me")
        return result.get("id")

    async def get_my_time_entries(self, days: int = 7) -> list[dict]:
        """Get the current user's recent time entries."""
        user_id = await self.get_my_user_id()
        if not user_id:
            return []

        return await self.get_time_entries_for_user(user_id, days)

    # ==================== UTILITY ====================

    async def test_connection(self) -> dict:
        """Test the Harvest connection by fetching company info."""
        try:
            result = await self._request("GET", "/company")
            return {
                "connected": True,
                "company_name": result.get("name", ""),
                "is_active": result.get("is_active", False),
                "time_format": result.get("time_format", ""),
                "plan_type": result.get("plan_type", ""),
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
            }
