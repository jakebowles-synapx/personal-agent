"""Knowledge manager with Qdrant integration for fixed knowledge."""

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from src.config import settings
from src.db import KnowledgeDB
from src.llm import AzureOpenAIClient

logger = logging.getLogger(__name__)

# Collection name for fixed knowledge in Qdrant
KNOWLEDGE_COLLECTION = "fixed_knowledge"

# Valid knowledge categories
KNOWLEDGE_CATEGORIES = ["strategy", "team", "processes", "clients", "projects"]


class KnowledgeManager:
    """
    Manages two-tier knowledge:
    - Fixed Knowledge: Qdrant vectors with category tags (strategy, team, etc.)
    - Dynamic Memory: Mem0 facts from conversations (handled by MemoryClient)

    This class handles the Fixed Knowledge tier.
    """

    def __init__(self, llm_client: AzureOpenAIClient | None = None) -> None:
        self.qdrant = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        self.llm = llm_client or AzureOpenAIClient()
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Ensure the Qdrant collection exists."""
        try:
            collections = self.qdrant.get_collections().collections
            collection_names = [c.name for c in collections]

            if KNOWLEDGE_COLLECTION not in collection_names:
                self.qdrant.create_collection(
                    collection_name=KNOWLEDGE_COLLECTION,
                    vectors_config=qdrant_models.VectorParams(
                        size=1536,  # text-embedding-ada-002 dimension
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {KNOWLEDGE_COLLECTION}")
            else:
                logger.debug(f"Qdrant collection '{KNOWLEDGE_COLLECTION}' already exists")

        except Exception as e:
            logger.error(f"Failed to ensure Qdrant collection: {e}")
            raise

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text using Azure OpenAI."""
        return await self.llm.get_embedding(text)

    async def add(
        self,
        category: str,
        title: str,
        content: str,
        source: str | None = None,
    ) -> int:
        """
        Add a knowledge item.

        Args:
            category: Category (strategy, team, processes, clients, projects)
            title: Title of the knowledge item
            content: Content text
            source: Source file path or 'manual'

        Returns:
            Knowledge item ID
        """
        if category not in KNOWLEDGE_CATEGORIES:
            raise ValueError(f"Invalid category: {category}. Must be one of {KNOWLEDGE_CATEGORIES}")

        # Generate embedding
        embedding_text = f"{title}\n\n{content}"
        embedding = await self._get_embedding(embedding_text)

        # Generate unique ID for Qdrant point
        point_id = str(uuid.uuid4())

        # Store in Qdrant
        self.qdrant.upsert(
            collection_name=KNOWLEDGE_COLLECTION,
            points=[
                qdrant_models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "category": category,
                        "title": title,
                        "content": content,
                        "source": source,
                    },
                )
            ],
        )

        # Store in SQLite
        knowledge_id = KnowledgeDB.create(
            category=category,
            title=title,
            content=content,
            source=source,
            embedding_id=point_id,
        )

        logger.info(f"Added knowledge item {knowledge_id}: {title} ({category})")
        return knowledge_id

    async def update(
        self,
        knowledge_id: int,
        title: str | None = None,
        content: str | None = None,
        category: str | None = None,
    ) -> bool:
        """
        Update a knowledge item.

        Args:
            knowledge_id: ID of the knowledge item
            title: New title (optional)
            content: New content (optional)
            category: New category (optional)

        Returns:
            True if updated successfully
        """
        # Get existing item
        item = KnowledgeDB.get(knowledge_id)
        if not item:
            return False

        # Determine new values
        new_title = title if title is not None else item["title"]
        new_content = content if content is not None else item["content"]
        new_category = category if category is not None else item["category"]

        if new_category not in KNOWLEDGE_CATEGORIES:
            raise ValueError(f"Invalid category: {new_category}")

        # If content changed, update embedding
        if content is not None or title is not None:
            embedding_text = f"{new_title}\n\n{new_content}"
            embedding = await self._get_embedding(embedding_text)

            # Update in Qdrant
            point_id = item["embedding_id"]
            if point_id:
                self.qdrant.upsert(
                    collection_name=KNOWLEDGE_COLLECTION,
                    points=[
                        qdrant_models.PointStruct(
                            id=point_id,
                            vector=embedding,
                            payload={
                                "category": new_category,
                                "title": new_title,
                                "content": new_content,
                                "source": item["source"],
                            },
                        )
                    ],
                )

        # Update in SQLite
        KnowledgeDB.update(
            knowledge_id=knowledge_id,
            title=title,
            content=content,
            category=category,
        )

        logger.info(f"Updated knowledge item {knowledge_id}")
        return True

    def delete(self, knowledge_id: int) -> bool:
        """
        Delete a knowledge item.

        Args:
            knowledge_id: ID of the knowledge item

        Returns:
            True if deleted successfully
        """
        # Get item to find Qdrant point ID
        item = KnowledgeDB.get(knowledge_id)
        if not item:
            return False

        # Delete from Qdrant
        point_id = item.get("embedding_id")
        if point_id:
            try:
                self.qdrant.delete(
                    collection_name=KNOWLEDGE_COLLECTION,
                    points_selector=qdrant_models.PointIdsList(points=[point_id]),
                )
            except Exception as e:
                logger.warning(f"Failed to delete from Qdrant: {e}")

        # Delete from SQLite
        KnowledgeDB.delete(knowledge_id)
        logger.info(f"Deleted knowledge item {knowledge_id}")
        return True

    def get(self, knowledge_id: int) -> dict | None:
        """Get a knowledge item by ID."""
        return KnowledgeDB.get(knowledge_id)

    def list_all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """List all knowledge items."""
        return KnowledgeDB.list(limit=limit, offset=offset)

    def list_by_category(self, category: str) -> list[dict]:
        """List knowledge items by category."""
        if category not in KNOWLEDGE_CATEGORIES:
            raise ValueError(f"Invalid category: {category}")
        return KnowledgeDB.list(category=category)

    def count_by_category(self) -> dict[str, int]:
        """Get count of knowledge items by category."""
        return KnowledgeDB.count_by_category()

    async def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Search knowledge using semantic similarity.

        Args:
            query: Search query
            category: Optional category filter
            limit: Maximum results

        Returns:
            List of matching knowledge items with scores
        """
        # Get query embedding
        query_embedding = await self._get_embedding(query)

        # Build filter
        search_filter = None
        if category:
            if category not in KNOWLEDGE_CATEGORIES:
                raise ValueError(f"Invalid category: {category}")
            search_filter = qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="category",
                        match=qdrant_models.MatchValue(value=category),
                    )
                ]
            )

        # Search Qdrant using query_points (qdrant-client 1.16+)
        results = self.qdrant.query_points(
            collection_name=KNOWLEDGE_COLLECTION,
            query=query_embedding,
            query_filter=search_filter,
            limit=limit,
        )

        # Format results
        items = []
        for result in results.points:
            items.append({
                "id": result.id,
                "score": result.score,
                "category": result.payload.get("category"),
                "title": result.payload.get("title"),
                "content": result.payload.get("content"),
                "source": result.payload.get("source"),
            })

        return items

    async def search_by_categories(
        self,
        query: str,
        categories: list[str],
        limit: int = 5,
    ) -> list[dict]:
        """
        Search knowledge across multiple categories.

        Args:
            query: Search query
            categories: List of categories to search
            limit: Maximum results per category

        Returns:
            List of matching knowledge items
        """
        all_results = []
        for category in categories:
            results = await self.search(query, category=category, limit=limit)
            all_results.extend(results)

        # Sort by score and deduplicate
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:limit]

    def get_context_for_prompt(
        self,
        categories: list[str] | None = None,
        limit_per_category: int = 3,
    ) -> str:
        """
        Get formatted knowledge context for system prompts.

        Args:
            categories: Categories to include (all if None)
            limit_per_category: Max items per category

        Returns:
            Formatted string for system prompt
        """
        categories = categories or KNOWLEDGE_CATEGORIES
        context_parts = []

        for category in categories:
            items = KnowledgeDB.list(category=category, limit=limit_per_category)
            if items:
                category_title = category.replace("_", " ").title()
                context_parts.append(f"\n## {category_title}")
                for item in items:
                    context_parts.append(f"- **{item['title']}**: {item['content'][:200]}...")

        if not context_parts:
            return ""

        return "# Fixed Knowledge\n" + "\n".join(context_parts)

    async def add_from_text(
        self,
        text: str,
        category: str,
        title: str,
        source: str = "manual",
    ) -> int:
        """
        Add knowledge from raw text.

        Args:
            text: Text content
            category: Category
            title: Title
            source: Source identifier

        Returns:
            Knowledge item ID
        """
        return await self.add(
            category=category,
            title=title,
            content=text,
            source=source,
        )

    async def add_from_document(
        self,
        content: str,
        filename: str,
        category: str,
    ) -> int:
        """
        Add knowledge from a document (content already extracted).

        Args:
            content: Extracted text content
            filename: Original filename
            category: Category

        Returns:
            Knowledge item ID
        """
        # Use filename as title
        title = filename.rsplit(".", 1)[0] if "." in filename else filename

        return await self.add(
            category=category,
            title=title,
            content=content,
            source=filename,
        )
