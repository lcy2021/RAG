import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.deps import chat_service_dep
from models.schemas import (
    ChatMessageIn,
    ChatMessageOut,
    ChatTurnOut,
    ConversationCreate,
    ConversationOut,
    RagRunSourcesOut,
)
from services.chat import ChatService

router = APIRouter(prefix="/conversations", tags=["chat"])

ChatSvc = Annotated[ChatService, Depends(chat_service_dep)]


@router.get("", response_model=list[ConversationOut])
async def list_conversations(svc: ChatSvc) -> list[ConversationOut]:
    return await svc.list_conversations()


@router.post("", response_model=ConversationOut)
async def create_conversation(payload: ConversationCreate, svc: ChatSvc) -> ConversationOut:
    return await svc.create_conversation(payload)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: UUID, svc: ChatSvc) -> None:
    await svc.delete_conversation(conversation_id)


@router.get("/{conversation_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(conversation_id: UUID, svc: ChatSvc) -> list[ChatMessageOut]:
    return await svc.list_messages(conversation_id)


@router.get(
    "/{conversation_id}/rag-runs/{rag_run_id}/sources",
    response_model=RagRunSourcesOut,
)
async def get_run_sources(
    conversation_id: UUID, rag_run_id: UUID, svc: ChatSvc
) -> RagRunSourcesOut:
    return await svc.get_run_sources(conversation_id, rag_run_id)


@router.post("/{conversation_id}/messages", response_model=ChatTurnOut)
async def send_message(
    conversation_id: UUID,
    payload: ChatMessageIn,
    svc: ChatSvc,
) -> ChatTurnOut:
    return await svc.send_message(conversation_id, payload)


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID,
    payload: ChatMessageIn,
    svc: ChatSvc,
) -> StreamingResponse:
    # Validate + persist user turn before SSE headers so 4xx stay JSON responses.
    prepared = await svc.prepare_stream(conversation_id, payload)

    async def event_source() -> AsyncIterator[bytes]:
        async for event, data in svc.iter_stream_events(prepared):
            yield _sse_bytes(event, data)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_bytes(event: str, data: dict) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode()
