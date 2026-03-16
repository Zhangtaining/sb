"""Conversation endpoints — Phase 2 chat interface."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from api.schemas import (
    ChatResponse,
    ConversationCreateRequest,
    ConversationResponse,
    MessageRequest,
    MessageResponse,
)
from gym_shared.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_conversation_manager():
    """Lazy import to avoid circular deps and heavy startup cost."""
    from guidance.config import build_config
    from guidance.conversation_manager import ConversationManager
    from guidance.llm_client import GymLLMClient
    from gym_shared.settings import settings

    config = build_config(settings)
    llm = GymLLMClient(config)
    return ConversationManager(config, llm)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new conversation for a person (or return existing one for this session)."""
    from gym_shared.db.models import Conversation

    existing = None
    if body.session_id:
        from sqlalchemy import select
        result = await db.execute(
            select(Conversation)
            .where(Conversation.person_id == body.person_id)
            .where(Conversation.session_id == body.session_id)
            .order_by(Conversation.started_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()

    if existing:
        return ConversationResponse(
            id=existing.id,
            person_id=existing.person_id,
            session_id=existing.session_id,
            started_at=existing.started_at,
        )

    conv = Conversation(person_id=body.person_id, session_id=body.session_id)
    db.add(conv)
    await db.flush()
    return ConversationResponse(
        id=conv.id,
        person_id=conv.person_id,
        session_id=conv.session_id,
        started_at=conv.started_at,
    )


@router.post("/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Send a user message and receive an AI response."""
    from gym_shared.db.models import Conversation

    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Message text cannot be empty")

    manager = _get_conversation_manager()
    response_text = await manager.send_message(
        conversation_id=conversation_id,
        person_id=conv.person_id,
        user_text=body.text,
    )

    return ChatResponse(
        conversation_id=conversation_id,
        user_message=body.text,
        assistant_response=response_text,
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
):
    """Fetch message history for a conversation."""
    from gym_shared.db.models import Conversation, Message
    from sqlalchemy import select

    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return [
        MessageResponse(role=m.role, content=m.content, created_at=m.created_at)
        for m in messages
    ]
