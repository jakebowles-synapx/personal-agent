"""Knowledge management API endpoints."""

import io
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel

from src.knowledge.manager import KnowledgeManager, KNOWLEDGE_CATEGORIES
from src.db import KnowledgeDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# Dependencies - set by main.py
_knowledge_manager: KnowledgeManager | None = None


def get_knowledge_manager() -> KnowledgeManager:
    """Get the knowledge manager."""
    if _knowledge_manager is None:
        raise HTTPException(status_code=503, detail="Knowledge manager not initialized")
    return _knowledge_manager


def set_knowledge_manager(manager: KnowledgeManager) -> None:
    """Set the knowledge manager."""
    global _knowledge_manager
    _knowledge_manager = manager


# Request/Response models
class KnowledgeCreate(BaseModel):
    category: str
    title: str
    content: str


class KnowledgeUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None


class KnowledgeResponse(BaseModel):
    id: int
    category: str
    title: str
    content: str
    source: str | None
    created_at: str
    updated_at: str


class KnowledgeSearchResult(BaseModel):
    id: str
    score: float
    category: str
    title: str
    content: str
    source: str | None


class CategoryCount(BaseModel):
    category: str
    count: int


# Endpoints
@router.get("/categories")
async def get_categories():
    """Get list of valid knowledge categories."""
    return {"categories": KNOWLEDGE_CATEGORIES}


@router.get("/stats")
async def get_stats():
    """Get knowledge statistics."""
    counts = KnowledgeDB.count_by_category()
    return {
        "total": sum(counts.values()),
        "by_category": counts,
        "categories": KNOWLEDGE_CATEGORIES,
    }


@router.get("", response_model=list[KnowledgeResponse])
async def list_knowledge(
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """List knowledge items with optional category filter."""
    if category and category not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {KNOWLEDGE_CATEGORIES}"
        )

    items = KnowledgeDB.list(category=category, limit=limit, offset=offset)
    return items


@router.get("/{knowledge_id}", response_model=KnowledgeResponse)
async def get_knowledge(knowledge_id: int):
    """Get a specific knowledge item."""
    item = KnowledgeDB.get(knowledge_id)
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return item


@router.post("", response_model=KnowledgeResponse, status_code=201)
async def create_knowledge(
    body: KnowledgeCreate,
    manager: Annotated[KnowledgeManager, Depends(get_knowledge_manager)],
):
    """Create a new knowledge item."""
    if body.category not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {KNOWLEDGE_CATEGORIES}"
        )

    try:
        knowledge_id = await manager.add(
            category=body.category,
            title=body.title,
            content=body.content,
            source="manual",
        )
        return KnowledgeDB.get(knowledge_id)
    except Exception as e:
        logger.error(f"Failed to create knowledge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{knowledge_id}", response_model=KnowledgeResponse)
async def update_knowledge(
    knowledge_id: int,
    body: KnowledgeUpdate,
    manager: Annotated[KnowledgeManager, Depends(get_knowledge_manager)],
):
    """Update a knowledge item."""
    if body.category and body.category not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {KNOWLEDGE_CATEGORIES}"
        )

    try:
        success = await manager.update(
            knowledge_id=knowledge_id,
            title=body.title,
            content=body.content,
            category=body.category,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Knowledge item not found")

        return KnowledgeDB.get(knowledge_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update knowledge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{knowledge_id}", status_code=204)
async def delete_knowledge(
    knowledge_id: int,
    manager: Annotated[KnowledgeManager, Depends(get_knowledge_manager)],
):
    """Delete a knowledge item."""
    success = manager.delete(knowledge_id)
    if not success:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return None


@router.post("/search", response_model=list[KnowledgeSearchResult])
async def search_knowledge(
    query: str,
    manager: Annotated[KnowledgeManager, Depends(get_knowledge_manager)],
    category: str | None = None,
    limit: int = 10,
):
    """Search knowledge using semantic similarity."""
    if category and category not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {KNOWLEDGE_CATEGORIES}"
        )

    try:
        results = await manager.search(query=query, category=category, limit=limit)
        return results
    except Exception as e:
        logger.error(f"Failed to search knowledge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=KnowledgeResponse, status_code=201)
async def upload_document(
    manager: Annotated[KnowledgeManager, Depends(get_knowledge_manager)],
    file: UploadFile = File(...),
    category: str = Form(...),
):
    """Upload a document to the knowledge base."""
    if category not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {KNOWLEDGE_CATEGORIES}"
        )

    # Check file type
    filename = file.filename or "unknown"
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    supported_types = ["txt", "md", "docx", "pdf"]
    if extension not in supported_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: {supported_types}"
        )

    try:
        # Read file content
        content_bytes = await file.read()

        # Extract text based on file type
        if extension in ["txt", "md"]:
            content = content_bytes.decode("utf-8")

        elif extension == "docx":
            from docx import Document
            doc = Document(io.BytesIO(content_bytes))
            content = "\n\n".join(para.text for para in doc.paragraphs if para.text)

        elif extension == "pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content_bytes))
            content = "\n\n".join(page.extract_text() for page in reader.pages)

        else:
            content = content_bytes.decode("utf-8", errors="ignore")

        if not content.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from file")

        # Add to knowledge base
        knowledge_id = await manager.add_from_document(
            content=content,
            filename=filename,
            category=category,
        )

        return KnowledgeDB.get(knowledge_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")
