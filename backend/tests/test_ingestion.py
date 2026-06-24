"""
Testes para a camada de ingestão:
  - chunk_text  : função pura de divisão de texto
  - ingest_file : pipeline completo (leitura → chunking → embedding → Redis)
"""

import json
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.ingestion import CHUNK_OVERLAP, CHUNK_SIZE, chunk_text, ingest_file


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_upload_file(content: bytes, filename: str, content_type: str) -> UploadFile:
    headers = Headers({"content-type": content_type})
    return UploadFile(file=BytesIO(content), filename=filename, headers=headers)


# ── chunk_text ────────────────────────────────────────────────────────────────

def test_chunk_text_string_vazia_retorna_lista_vazia():
    assert chunk_text("") == []


def test_chunk_text_apenas_espacos_retorna_lista_vazia():
    assert chunk_text("   \n\t   ") == []


def test_chunk_text_texto_curto_retorna_um_chunk():
    texto = "Texto curto que cabe em um único chunk."
    resultado = chunk_text(texto)
    assert len(resultado) == 1
    assert resultado[0] == texto


def test_chunk_text_tamanho_exato_retorna_um_chunk():
    texto = "Z" * CHUNK_SIZE
    resultado = chunk_text(texto)
    assert len(resultado) == 1


def test_chunk_text_texto_longo_gera_multiplos_chunks():
    texto = "palavra " * 500
    chunks = chunk_text(texto, chunk_size=100, overlap=10)
    assert len(chunks) > 1


def test_chunk_text_sem_overlap_chunks_nao_se_repetem():
    texto = "A" * 400
    chunks = chunk_text(texto, chunk_size=200, overlap=0)
    assert len(chunks) == 2
    assert chunks[0] == "A" * 200
    assert chunks[1] == "A" * 200


def test_chunk_text_overlap_conteudo_repetido_entre_chunks():
    # Com overlap=50: o final do chunk[0] deve aparecer no início do chunk[1]
    texto = "X" * 500
    chunks = chunk_text(texto, chunk_size=200, overlap=50)
    sobreposicao = chunks[0][150:]  # últimos 50 caracteres do primeiro chunk
    assert chunks[1].startswith(sobreposicao)


def test_chunk_text_normaliza_multiplos_espacos():
    texto = "  palavra1  \n\n\t  palavra2   palavra3  "
    resultado = chunk_text(texto)
    assert resultado == ["palavra1 palavra2 palavra3"]


def test_chunk_text_ultimo_chunk_nao_ultrapassa_texto():
    texto = "B" * 350
    chunks = chunk_text(texto, chunk_size=200, overlap=50)
    reconstruido = chunks[0] + chunks[-1][50:]  # remove a sobreposicao
    assert len(reconstruido) == 350


# ── ingest_file ───────────────────────────────────────────────────────────────

async def test_ingest_file_retorna_documento_correto(patched_services):
    texto = "Conteúdo de exemplo para ingestão do documento de teste."
    upload = _make_upload_file(texto.encode(), "doc.txt", "text/plain")

    with patch("app.services.ingestion.extract_document_text", return_value=(texto, "text")):
        resultado = await ingest_file(upload)

    assert resultado.filename == "doc.txt"
    assert resultado.content_type == "text/plain"
    assert resultado.reader_method == "text"
    assert resultado.chunks_count >= 1
    assert resultado.id  # UUID gerado


async def test_ingest_file_persiste_documento_no_redis(patched_services, fake_redis):
    texto = "Conteúdo para armazenar no Redis."
    upload = _make_upload_file(texto.encode(), "arq.txt", "text/plain")

    with patch("app.services.ingestion.extract_document_text", return_value=(texto, "text")):
        doc = await ingest_file(upload)

    payload = await fake_redis.get(f"documents:item:{doc.id}")
    assert payload is not None

    dados = json.loads(payload)
    assert dados["id"] == doc.id
    assert dados["filename"] == "arq.txt"
    assert dados["reader_method"] == "text"


async def test_ingest_file_registra_documento_no_indice_redis(patched_services, fake_redis):
    texto = "Texto para índice."
    upload = _make_upload_file(texto.encode(), "idx.txt", "text/plain")

    with patch("app.services.ingestion.extract_document_text", return_value=(texto, "text")):
        doc = await ingest_file(upload)

    ids_no_indice = await fake_redis.zrange("documents:index", 0, -1)
    assert doc.id in ids_no_indice


async def test_ingest_file_persiste_chunks_no_redis(patched_services, fake_redis):
    texto = "Parágrafo de teste. " * 200  # longo o suficiente para múltiplos chunks
    upload = _make_upload_file(texto.encode(), "grande.txt", "text/plain")

    with patch("app.services.ingestion.extract_document_text", return_value=(texto, "text")):
        doc = await ingest_file(upload)

    chunk_ids = await fake_redis.smembers("documents:chunks")
    assert len(chunk_ids) == doc.chunks_count
    assert doc.chunks_count > 1


async def test_ingest_file_chama_embed_por_chunk(patched_services, fake_redis, mock_openai_client):
    texto = "Texto para embedding. " * 200
    upload = _make_upload_file(texto.encode(), "emb.txt", "text/plain")

    with patch("app.services.ingestion.extract_document_text", return_value=(texto, "text")):
        doc = await ingest_file(upload)

    assert mock_openai_client.embeddings.create.call_count == doc.chunks_count


async def test_ingest_file_chunk_armazena_embedding_no_redis(patched_services, fake_redis, mock_embedding):
    texto = "Texto simples."
    upload = _make_upload_file(texto.encode(), "emb2.txt", "text/plain")

    with patch("app.services.ingestion.extract_document_text", return_value=(texto, "text")):
        await ingest_file(upload)

    chunk_ids = await fake_redis.smembers("documents:chunks")
    assert chunk_ids

    primeiro_chunk_payload = await fake_redis.get(f"documents:chunk:{next(iter(chunk_ids))}")
    chunk_data = json.loads(primeiro_chunk_payload)
    assert chunk_data["embedding"] == mock_embedding
