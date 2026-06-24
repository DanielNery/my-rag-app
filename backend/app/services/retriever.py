from app.models.schemas import SourceChunk
from app.services import document_store
from app.services.embeddings import cosine_similarity, embed_text


async def retrieve(question: str, top_k: int = 5) -> list[SourceChunk]:
    """Recupera os chunks mais relevantes para uma pergunta.

    Args:
        question (str): Pergunta a ser recuperada.
        top_k (int, optional): Número de chunks a serem recuperados. Defaults to 5.

    Returns:
        list[SourceChunk]: Lista de chunks recuperados.
    """
    question_embedding = await embed_text(question)
    chunks = await document_store.list_chunks()
    scored_chunks: list[SourceChunk] = []

    for chunk in chunks:
        #TODO: Parametrizar Nível de similaridade em painel no frontend.
        score = cosine_similarity(question_embedding, chunk.embedding)
        if score <= 0:
            continue

        scored_chunks.append(
            SourceChunk(
                chunk=chunk.content,
                source=chunk.source,
                score=round(score, 4),
            )
        )

    return sorted(scored_chunks, key=lambda item: item.score, reverse=True)[:top_k]
