from fastapi import APIRouter, HTTPException, status

from app.models.schemas import ChatSession, SessionCreate, SessionUpdate
from app.services import session_store

session_router = APIRouter(
    prefix="/session",
    tags=["session"],
)


@session_router.post("/", response_model=ChatSession, status_code=status.HTTP_201_CREATED)
async def create_session(session: SessionCreate):
    return await session_store.create_session(session.name)


@session_router.get("/", response_model=list[ChatSession])
async def get_sessions():
    return await session_store.list_sessions()


@session_router.get("/{session_id}", response_model=ChatSession)
async def get_session(session_id: str):
    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@session_router.put("/{session_id}", response_model=ChatSession)
async def update_session(session_id: str, session: SessionUpdate):
    updated_session = await session_store.update_session_name(session_id, session.name)
    if not updated_session:
        raise HTTPException(status_code=404, detail="Session not found")

    return updated_session


@session_router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str):
    was_deleted = await session_store.delete_session(session_id)
    if not was_deleted:
        raise HTTPException(status_code=404, detail="Session not found")
