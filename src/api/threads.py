"""Thread and message API endpoints."""

import logging
from typing import Annotated, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.agent import AgentOrchestrator
from src.api.commands import is_command, execute_command

if TYPE_CHECKING:
    from src.agents.chat_agent import ChatAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads", tags=["threads"])

# Dependency to get orchestrator instance (legacy, for history management)
_orchestrator: AgentOrchestrator | None = None
_chat_agent: "ChatAgent | None" = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator instance."""
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return _orchestrator


def set_orchestrator(orchestrator: AgentOrchestrator) -> None:
    """Set the global orchestrator instance."""
    global _orchestrator
    _orchestrator = orchestrator


def get_chat_agent() -> "ChatAgent":
    """Get the chat agent instance."""
    if _chat_agent is None:
        raise HTTPException(status_code=503, detail="Chat agent not initialized")
    return _chat_agent


def set_chat_agent(agent: "ChatAgent") -> None:
    """Set the chat agent instance."""
    global _chat_agent
    _chat_agent = agent


# Request/Response models
class ThreadCreate(BaseModel):
    title: str | None = None


class ThreadUpdate(BaseModel):
    title: str


class MessageCreate(BaseModel):
    content: str


class ThreadResponse(BaseModel):
    id: str
    title: str | None
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class ThreadWithMessages(ThreadResponse):
    messages: list[MessageResponse]


class SendMessageResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse


# Thread endpoints
@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
    limit: int = 50,
    offset: int = 0,
):
    """List all conversation threads."""
    threads = orchestrator.history.list_threads(limit=limit, offset=offset)
    return threads


@router.post("", response_model=ThreadResponse, status_code=201)
async def create_thread(
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
    body: ThreadCreate | None = None,
):
    """Create a new conversation thread."""
    title = body.title if body else None
    thread = orchestrator.history.create_thread(title=title)
    return thread


@router.get("/{thread_id}", response_model=ThreadWithMessages)
async def get_thread(
    thread_id: str,
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Get a thread with its messages."""
    thread = orchestrator.history.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = orchestrator.history.get_thread_messages(thread_id)
    return {**thread, "messages": messages}


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    body: ThreadUpdate,
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Update a thread's title."""
    thread = orchestrator.history.update_thread(thread_id, title=body.title)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: str,
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Delete a thread and all its messages."""
    deleted = orchestrator.history.delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return None


# Message endpoints
@router.get("/{thread_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    thread_id: str,
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
    limit: int = 50,
):
    """Get messages for a thread."""
    thread = orchestrator.history.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = orchestrator.history.get_thread_messages(thread_id, limit=limit)
    return messages


@router.post("/{thread_id}/messages", response_model=SendMessageResponse)
async def send_message(
    thread_id: str,
    body: MessageCreate,
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Send a message and get AI response."""
    # Get chat agent (uses knowledge integration)
    chat_agent = get_chat_agent()

    thread = orchestrator.history.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    try:
        # Check if this is a slash command
        if is_command(body.content):
            result = await execute_command(body.content, orchestrator)
            if result:
                # Store command and response in thread history
                user_msg, assistant_msg = orchestrator.history.add_exchange(
                    thread_id=thread_id,
                    user_message=body.content,
                    assistant_message=result.response,
                )
                return {
                    "user_message": user_msg,
                    "assistant_message": assistant_msg,
                }

        # Process regular message through ChatAgent (with knowledge integration)
        response = await chat_agent.handle_chat(
            message=body.content,
            thread_id=thread_id,
        )

        # Get the last two messages (user + assistant) - ChatAgent stores them
        messages = orchestrator.history.get_thread_messages(thread_id, limit=2)
        if len(messages) < 2:
            raise HTTPException(status_code=500, detail="Failed to store messages")

        # Messages are oldest first, so [-2] is user, [-1] is assistant
        user_msg = messages[-2] if messages[-2]["role"] == "user" else messages[-1]
        assistant_msg = messages[-1] if messages[-1]["role"] == "assistant" else messages[-2]

        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
        }

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
