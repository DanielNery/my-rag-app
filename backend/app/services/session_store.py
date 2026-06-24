import json
from uuid import uuid4

from app.models.schemas import ChatMessage, ChatSession
from app.services.utils import get_redis_client, now_iso, score_from_iso

SESSIONS_INDEX_KEY = "chat:sessions"
SESSION_KEY_PREFIX = "chat:session:"


def session_key(session_id: str) -> str:
    """Retorna a chave da sessão no Redis."""
    return f"{SESSION_KEY_PREFIX}{session_id}"


async def create_session(name: str) -> ChatSession:
    """Cria uma nova sessão.

    Args:
        name (str): Nome da sessão.

    Returns:
        ChatSession: Sessão criada.
    """
    timestamp = now_iso()
    session = ChatSession(
        id=str(uuid4()),
        name=name.strip() or "Nova sessao",
        messages=[
            ChatMessage(
                id=str(uuid4()),
                role="assistant",
                text="Envie uma pergunta sobre os arquivos enviados.",
                created_at=timestamp,
            )
        ],
        created_at=timestamp,
        updated_at=timestamp,
    )

    await save_session(session)
    return session


async def save_session(session: ChatSession) -> None:
    """Salva uma sessão no Redis.

    Args:
        session (ChatSession): Sessão a ser salva.
    """
    redis_client = get_redis_client()
    try:
        await redis_client.set(
            session_key(session.id),
            session.model_dump_json(),
        )
        await redis_client.zadd(
            SESSIONS_INDEX_KEY,
            {session.id: score_from_iso(session.updated_at)},
        )
    finally:
        await redis_client.aclose()


async def get_session(session_id: str) -> ChatSession | None:
    """Obtém uma sessão do Redis.

    Args:
        session_id (str): ID da sessão.

    Returns:
        ChatSession | None: Sessão encontrada ou None.
    """
    redis_client = get_redis_client()
    try:
        payload = await redis_client.get(session_key(session_id))
        if not payload:
            return None
    finally:
        await redis_client.aclose()

    return ChatSession.model_validate(json.loads(payload))


async def list_sessions() -> list[ChatSession]:
    """Lista todas as sessões do Redis.

    Returns:
        list[ChatSession]: Lista de sessões.
    """
    redis_client = get_redis_client()
    try:
        session_ids = await redis_client.zrevrange(SESSIONS_INDEX_KEY, 0, -1)
    finally:
        await redis_client.aclose()

    sessions: list[ChatSession] = []

    for session_id in session_ids:
        session = await get_session(session_id)
        if session:
            sessions.append(session)
        else:
            redis_client = get_redis_client()
            try:
                await redis_client.zrem(SESSIONS_INDEX_KEY, session_id)
            finally:
                await redis_client.aclose()

    return sessions


async def update_session_name(session_id: str, name: str) -> ChatSession | None:
    """Atualiza o nome de uma sessão.

    Args:
        session_id (str): ID da sessão.
        name (str): Nome da sessão.

    Returns:
        ChatSession | None: Sessão atualizada ou None.
    """
    session = await get_session(session_id)
    if not session:
        return None

    session.name = name.strip() or session.name
    session.updated_at = now_iso()
    await save_session(session)
    return session


async def delete_session(session_id: str) -> bool:
    """Deleta uma sessão do Redis.

    Args:
        session_id (str): ID da sessão.

    Returns:
        bool: True se a sessão foi deletada, False caso contrário.
    """
    redis_client = get_redis_client()
    try:
        deleted = await redis_client.delete(session_key(session_id))
        await redis_client.zrem(SESSIONS_INDEX_KEY, session_id)
        return deleted > 0
    finally:
        await redis_client.aclose()


async def append_message(session_id: str, role: str, text: str) -> ChatMessage | None:
    """Adiciona uma mensagem a uma sessão.

    Args:
        session_id (str): ID da sessão.
        role (str): Papel da mensagem.
        text (str): Texto da mensagem.

    Returns:
        ChatMessage | None: Mensagem adicionada ou None.
    """
    session = await get_session(session_id)
    if not session:
        return None

    timestamp = now_iso()
    message = ChatMessage(
        id=str(uuid4()),
        role=role,
        text=text,
        created_at=timestamp,
    )
    session.messages.append(message)
    session.updated_at = timestamp
    await save_session(session)
    return message
