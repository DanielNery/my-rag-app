from collections.abc import AsyncGenerator

from app.models.schemas import ChatMessage, ChatResponse, SourceChunk
from app.config import settings
from app.services.openai_client import get_openai_client
from app.services.retriever import retrieve

_INSTRUCTIONS = (
    "Voce e um assistente RAG para responder perguntas em portugues. "
    "Use somente o contexto fornecido. Se a resposta nao estiver no contexto, "
    "diga que nao encontrou informacao suficiente nos documentos. "
    "Seja direto e cite os nomes dos arquivos usados quando fizer sentido. "
    "Formate sua resposta usando Markdown: use **negrito** para termos importantes, "
    "listas quando listar itens, e blocos de codigo quando necessario. "
    "Leve em consideracao o historico da conversa ao interpretar a pergunta atual."
)

_MAX_HISTORY_MESSAGES = 10


def _build_input(
    question: str,
    sources: list[SourceChunk],
    history: list[ChatMessage],
) -> list[dict]:
    """
    Constrói o input conversacional para o modelo.

    O histórico é incluído como turns anteriores, e a pergunta atual
    (com o contexto RAG recuperado) é adicionada como último turn do usuário.
    """
    turns: list[dict] = []

    # Inclui apenas mensagens reais (após a primeira mensagem do usuário)
    filtered = _filter_history(history)
    for msg in filtered:
        turns.append({"role": msg.role, "content": msg.text})

    if sources:
        context = "\n\n".join(
            f"Fonte: {source.source}\nScore: {source.score}\nTrecho: {source.chunk}"
            for source in sources
        )
        user_content = (
            f"Pergunta: {question}\n\n"
            f"Contexto recuperado dos documentos:\n{context}\n\n"
            "Responda com base exclusivamente no contexto recuperado acima."
        )
    else:
        user_content = (
            f"Pergunta: {question}\n\n"
            "Nenhum trecho relevante foi encontrado nos documentos para esta pergunta. "
            "Se possivel, responda com base no historico da conversa. "
            "Caso contrario, informe que nao ha informacao suficiente."
        )

    turns.append({"role": "user", "content": user_content})
    return turns


def _filter_history(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Retorna apenas mensagens reais."""
    result: list[ChatMessage] = []
    found_user = False
    for msg in messages:
        if msg.role == "user":
            found_user = True
        if found_user and msg.role in ("user", "assistant"):
            result.append(msg)
    return result[-_MAX_HISTORY_MESSAGES:]


async def answer_question(
    question: str,
    history: list[ChatMessage],
    top_k: int = 5,
) -> ChatResponse:
    """Responde uma pergunta usando o modelo de resposta do OpenAI.

    Args:
        question (str): Pergunta a ser respondida.
        history (list[ChatMessage]): Histórico da conversa.
        top_k (int, optional): Número de chunks a serem recuperados. Defaults to 5.

    Returns:
        ChatResponse: Resposta gerada.
    """
    sources = await retrieve(question, top_k=top_k)
    client = get_openai_client()

    response = await client.responses.create(
        model=settings.openai_model,
        instructions=_INSTRUCTIONS,
        input=_build_input(question, sources, history),
    )

    return ChatResponse(answer=response.output_text, sources=sources)


async def stream_answer(
    question: str,
    history: list[ChatMessage],
    top_k: int = 5,
) -> AsyncGenerator[dict, None]:
    """Responde uma pergunta usando o modelo de resposta do OpenAI em streaming.

    Args:
        question (str): Pergunta a ser respondida.
        history (list[ChatMessage]): Histórico da conversa.
        top_k (int, optional): Número de chunks a serem recuperados. Defaults to 5.

    Returns:
        AsyncGenerator[dict, None]: Gerador de eventos de streaming.
    """
    #TODO: parametrizar numero de chunks em tela de controle no frontend.
    sources = await retrieve(question, top_k=top_k)
    client = get_openai_client()

    stream = await client.responses.create(
        model=settings.openai_model,
        instructions=_INSTRUCTIONS,
        input=_build_input(question, sources, history),
        stream=True,
    )

    async for event in stream:
        if event.type == "response.output_text.delta":
            yield {"type": "token", "text": event.delta}

    yield {"type": "done", "sources": [s.model_dump() for s in sources]}
