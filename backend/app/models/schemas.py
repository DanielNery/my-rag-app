from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    text: str
    created_at: str


class SessionCreate(BaseModel):
    name: str = Field(default="Nova sessao", min_length=1, max_length=80)


class SessionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ChatSession(BaseModel):
    id: str
    name: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ChatSocketMessage(BaseModel):
    session_id: str
    text: str = Field(min_length=1)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str
    top_k: int = Field(default=5, ge=1, le=20)


class SourceChunk(BaseModel):
    chunk: str
    source: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]


class UploadedDocument(BaseModel):
    id: str
    filename: str
    content_type: str | None = None
    reader_method: str
    chunks_count: int
    created_at: str


class DocumentChunk(BaseModel):
    id: str
    document_id: str
    source: str
    content: str
    embedding: list[float]
    reader_method: str
    created_at: str
