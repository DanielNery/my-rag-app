import json
import logging

from fastapi import APIRouter, WebSocket
from openai import OpenAIError
from fastapi.websockets import WebSocketDisconnect
from pydantic import ValidationError

from app.models.schemas import ChatMessage, ChatRequest, ChatResponse, ChatSocketMessage
from app.services.rag_chain import answer_question, stream_answer
from app.services import session_store

logger = logging.getLogger(__name__)

chat_router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


async def _get_history(session_id: str) -> list[ChatMessage]:
    """Retorna o histórico da sessão antes da mensagem atual."""
    session = await session_store.get_session(session_id)
    return session.messages if session else []


@chat_router.post("/", response_model=ChatResponse)
async def ask_question(payload: ChatRequest):
    history = await _get_history(payload.session_id)
    await session_store.append_message(payload.session_id, "user", payload.question)

    try:
        response = await answer_question(
            payload.question,
            history=history,
            top_k=payload.top_k,
        )
    except OpenAIError as error:
        response = ChatResponse(
            answer=f"Erro ao consultar a OpenAI: {error}",
            sources=[],
        )

    await session_store.append_message(payload.session_id, "assistant", response.answer)
    return response


@chat_router.websocket("/")
async def chat(websocket: WebSocket):
    await websocket.accept()

    while True:
        try:
            data = await websocket.receive_text()
            logger.info("Mensagem recebida: %s", data)

            try:
                payload = ChatSocketMessage.model_validate(json.loads(data))
            except (json.JSONDecodeError, ValidationError):
                await websocket.send_text(f"Mensagem recebida: {data}")
                continue

            # Busca histórico ANTES de salvar a mensagem atual
            history = await _get_history(payload.session_id)
            await session_store.append_message(payload.session_id, "user", payload.text)

            full_answer = ""
            try:
                async for event in stream_answer(payload.text, history=history):
                    if event["type"] == "token":
                        full_answer += event["text"]
                        await websocket.send_json(
                            {
                                "type": "token",
                                "session_id": payload.session_id,
                                "text": event["text"],
                            }
                        )
                    elif event["type"] == "done":
                        await session_store.append_message(
                            payload.session_id, "assistant", full_answer
                        )
                        await websocket.send_json(
                            {
                                "type": "done",
                                "session_id": payload.session_id,
                                "sources": event["sources"],
                            }
                        )
            except OpenAIError as error:
                logger.exception("Erro OpenAI ao responder: %s", error)
                await websocket.send_json(
                    {
                        "type": "error",
                        "session_id": payload.session_id,
                        "text": f"Erro ao consultar a OpenAI: {error}",
                    }
                )

        except WebSocketDisconnect:
            break
