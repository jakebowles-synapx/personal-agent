"""Mem0 client for conversation memory."""

import logging
from datetime import datetime, timezone

from mem0 import Memory

from src.config import settings

logger = logging.getLogger(__name__)

# Custom prompt for Mem0 fact extraction - ensures absolute dates and specificity
MEMORY_EXTRACTION_PROMPT = """You are a memory extraction assistant. Extract important facts from conversations.

CRITICAL RULES:
1. ALWAYS use British English spelling (e.g., "organised" not "organized", "colour" not "color", "centre" not "center").

2. ALWAYS convert relative dates/times to ABSOLUTE dates:
   - "tomorrow" → the specific date (e.g., "2nd February 2025")
   - "Friday" → the specific date (e.g., "31st January 2025")
   - "next week" → the specific date range
   - "in 2 hours" → include the actual time if relevant, or omit if not important

3. Include SPECIFIC details:
   - Names, dates, locations, amounts, deadlines
   - "Meeting with John" → "Meeting with John Smith from Acme Corp"

4. SKIP extracting:
   - Vague or temporary information
   - Information only relevant in the moment
   - Chit-chat or pleasantries

5. For time-sensitive facts, include when it was mentioned:
   - "Has a meeting on 30th January 2025 (mentioned on 29th January)"

Today's date for reference: {current_date}

Extract facts that will still be useful and accurate days or weeks from now."""


class MemoryClient:
    """Client for storing and retrieving conversation memories using Mem0."""

    def __init__(self) -> None:
        current_date = datetime.now(timezone.utc).strftime("%d %B %Y")

        config = {
            "custom_prompt": MEMORY_EXTRACTION_PROMPT.format(current_date=current_date),
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": settings.qdrant_host,
                    "port": settings.qdrant_port,
                    "collection_name": "personal_agent_memories",
                },
            },
            "llm": {
                "provider": "azure_openai",
                "config": {
                    # Model name must contain "gpt-5" for Mem0 to detect it as a reasoning model
                    # and filter out unsupported parameters like max_tokens
                    "model": "gpt-5",
                    "azure_kwargs": {
                        "azure_deployment": settings.azure_openai_deployment,
                        "azure_endpoint": settings.azure_openai_endpoint,
                        "api_key": settings.azure_openai_api_key,
                        "api_version": "2024-02-15-preview",
                    },
                },
            },
            "embedder": {
                "provider": "azure_openai",
                "config": {
                    "azure_kwargs": {
                        "azure_deployment": settings.azure_openai_embedding_deployment,
                        "azure_endpoint": settings.azure_openai_endpoint,
                        "api_key": settings.azure_openai_api_key,
                        "api_version": "2024-02-15-preview",
                    },
                },
            },
        }
        self.memory = Memory.from_config(config)

    def add(self, messages: list[dict], user_id: str, metadata: dict | None = None) -> dict:
        """Add messages to memory for a user."""
        result = self.memory.add(
            messages=messages,
            user_id=user_id,
            metadata=metadata or {},
        )
        logger.info(f"Added memory for user {user_id}: {result}")
        return result

    def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
        """Search memories for a user."""
        response = self.memory.search(
            query=query,
            user_id=user_id,
            limit=limit,
        )
        # Mem0 returns {'results': [...]} - extract the list
        if isinstance(response, dict) and "results" in response:
            results = response["results"]
        else:
            results = response if isinstance(response, list) else []
        logger.info(f"Found {len(results)} memories for user {user_id}: {results}")
        return results

    def get_all(self, user_id: str) -> list[dict]:
        """Get all memories for a user."""
        response = self.memory.get_all(user_id=user_id)
        # Mem0 returns {'results': [...]} - extract the list
        if isinstance(response, dict) and "results" in response:
            return response["results"]
        return response if isinstance(response, list) else []

    def delete(self, memory_id: str) -> None:
        """Delete a specific memory."""
        self.memory.delete(memory_id=memory_id)
        logger.info(f"Deleted memory {memory_id}")

    def delete_all(self, user_id: str) -> None:
        """Delete all memories for a user."""
        self.memory.delete_all(user_id=user_id)
        logger.info(f"Deleted all memories for user {user_id}")
