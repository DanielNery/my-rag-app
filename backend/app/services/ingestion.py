from uuid import uuid4

from fastapi import UploadFile

from app.models.schemas import DocumentChunk, UploadedDocument
from app.services import document_store
from app.services.document_reader import extract_document_text
from app.services.embeddings import embed_text

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 180


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Divide um texto em chunks de tamanho fixo com overlap.

    Args:
        text (str): Texto a ser dividido.
        chunk_size (int, optional): Tamanho de cada chunk. Defaults to CHUNK_SIZE.
        overlap (int, optional): Overlap entre chunks. Defaults to CHUNK_OVERLAP.

    Returns:
        list[str]: Lista de chunks.
    """
    clean_text = " ".join(text.split())
    if not clean_text:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(clean_text):
        end = min(start + chunk_size, len(clean_text))
        chunks.append(clean_text[start:end])
        if end == len(clean_text):
            break
        start = max(0, end - overlap)

    return chunks


async def ingest_file(file: UploadFile) -> UploadedDocument:
    """Ingestão de um arquivo.

    Args:
        file (UploadFile): Arquivo enviado pelo usuário.

    Returns:
        UploadedDocument: Documento criado.
    """
    content = await file.read()
    text, reader_method = extract_document_text(file.filename or "documento", content)
    text_chunks = chunk_text(text)

    document = document_store.create_document(
        filename=file.filename or "documento",
        content_type=file.content_type,
        reader_method=reader_method,
        chunks_count=len(text_chunks),
    )

    chunks = [
        DocumentChunk(
            id=str(uuid4()),
            document_id=document.id,
            source=document.filename,
            content=chunk,
            embedding=await embed_text(chunk),
            reader_method=reader_method,
            created_at=document.created_at,
        )
        for chunk in text_chunks
    ]

    await document_store.save_document(document, chunks)
    return document


async def ingest_files(files: list[UploadFile]) -> list[UploadedDocument]:
    """Ingestão de uma lista de arquivos.

    Args:
        files (list[UploadFile]): Lista de arquivos enviados pelo usuário.

    Returns:
        list[UploadedDocument]: Lista de documentos criados.
    """
    documents: list[UploadedDocument] = []

    for file in files:
        documents.append(await ingest_file(file))

    return documents
