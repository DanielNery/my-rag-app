import json
from uuid import uuid4

from app.models.schemas import DocumentChunk, UploadedDocument
from app.services.utils import get_redis_client, now_iso, score_from_iso

DOCUMENTS_INDEX_KEY = "documents:index"
DOCUMENT_KEY_PREFIX = "documents:item:"
CHUNKS_INDEX_KEY = "documents:chunks"
CHUNK_KEY_PREFIX = "documents:chunk:"


def document_key(document_id: str) -> str:
    """Retorna a chave do documento no Redis.

    Args:
        document_id (str): ID do documento.

    Returns:
        str: Chave do documento no Redis.
    """
    return f"{DOCUMENT_KEY_PREFIX}{document_id}"


def chunk_key(chunk_id: str) -> str:
    """Retorna a chave do chunk no Redis.

    Args:
        chunk_id (str): ID do chunk.

    Returns:
        str: Chave do chunk no Redis.
    """
    return f"{CHUNK_KEY_PREFIX}{chunk_id}"


async def save_document(document: UploadedDocument, chunks: list[DocumentChunk]) -> None:
    """Salva um documento e seus chunks no Redis.

    Args:
        document (UploadedDocument): Documento a ser salvo.
        chunks (list[DocumentChunk]): Chunks do documento.

    """
    redis_client = get_redis_client()
    try:
        await redis_client.set(document_key(document.id), document.model_dump_json())
        await redis_client.zadd(DOCUMENTS_INDEX_KEY, {document.id: score_from_iso(document.created_at)})

        for chunk in chunks:
            await redis_client.set(chunk_key(chunk.id), chunk.model_dump_json())
            await redis_client.sadd(CHUNKS_INDEX_KEY, chunk.id)
    finally:
        await redis_client.aclose()


async def list_documents() -> list[UploadedDocument]:
    """Lista todos os documentos no Redis.

    Returns:
        list[UploadedDocument]: Lista de documentos.
    """
    redis_client = get_redis_client()
    try:
        document_ids = await redis_client.zrevrange(DOCUMENTS_INDEX_KEY, 0, -1)
        documents: list[UploadedDocument] = []

        for document_id in document_ids:
            payload = await redis_client.get(document_key(document_id))
            if payload:
                documents.append(UploadedDocument.model_validate(json.loads(payload)))

        return documents
    finally:
        await redis_client.aclose()


async def list_chunks() -> list[DocumentChunk]:
    """Lista todos os chunks no Redis.

    Returns:
        list[DocumentChunk]: Lista de chunks.
    """
    redis_client = get_redis_client()
    try:
        chunk_ids = await redis_client.smembers(CHUNKS_INDEX_KEY)
        chunks: list[DocumentChunk] = []

        for chunk_id in chunk_ids:
            payload = await redis_client.get(chunk_key(chunk_id))
            if payload:
                chunks.append(DocumentChunk.model_validate(json.loads(payload)))

        return chunks
    finally:
        await redis_client.aclose()


def create_document(filename: str, content_type: str | None, reader_method: str, chunks_count: int) -> UploadedDocument:
    """Cria um novo documento.

    Args:
        filename (str): Nome do arquivo.
        content_type (str | None): Tipo de conteúdo do arquivo.
        reader_method (str): Método de leitura usado.
        chunks_count (int): Número de chunks do documento.
    """
    return UploadedDocument(
        id=str(uuid4()),
        filename=filename,
        content_type=content_type,
        reader_method=reader_method,
        chunks_count=chunks_count,
        created_at=now_iso(),
    )


async def delete_document(document_id: str) -> bool:
    """Deleta um documento e seus chunks no Redis.

    Args:
        document_id (str): ID do documento.

    Returns:
        bool: True se o documento foi deletado, False caso contrário.
    """
    redis_client = get_redis_client()
    try:
        if not await redis_client.exists(document_key(document_id)):
            return False

        chunk_ids = await redis_client.smembers(CHUNKS_INDEX_KEY)
        for chunk_id in chunk_ids:
            payload = await redis_client.get(chunk_key(chunk_id))
            if payload:
                chunk_data = json.loads(payload)
                if chunk_data.get("document_id") == document_id:
                    await redis_client.delete(chunk_key(chunk_id))
                    await redis_client.srem(CHUNKS_INDEX_KEY, chunk_id)

        await redis_client.delete(document_key(document_id))
        await redis_client.zrem(DOCUMENTS_INDEX_KEY, document_id)
        return True
    finally:
        await redis_client.aclose()
