"""
Testes de integração para os endpoints de documentos:
  GET  /documents/         → lista documentos
  DELETE /documents/{id}   → remove documento e seus chunks

Os testes de seed injetam dados diretamente no fake_redis usando os mesmos
prefixos de chave definidos em document_store.py para simular dados pré-existentes.
"""

from unittest.mock import patch


# ── GET /documents/ ───────────────────────────────────────────────────────────

async def test_list_documentos_retorna_lista_vazia(async_client):
    response = await async_client.get("/documents/")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_documentos_retorna_documento_seedado(async_client, fake_redis, sample_document):
    await fake_redis.set(
        f"documents:item:{sample_document.id}",
        sample_document.model_dump_json(),
    )
    await fake_redis.zadd("documents:index", {sample_document.id: 0.0})

    response = await async_client.get("/documents/")
    assert response.status_code == 200

    dados = response.json()
    assert len(dados) == 1
    assert dados[0]["id"] == sample_document.id
    assert dados[0]["filename"] == sample_document.filename
    assert dados[0]["reader_method"] == sample_document.reader_method


async def test_list_documentos_ordem_cronologica_decrescente(async_client, fake_redis):
    from app.models.schemas import UploadedDocument

    doc_antigo = UploadedDocument(
        id="doc-antigo",
        filename="antigo.txt",
        content_type="text/plain",
        reader_method="text",
        chunks_count=1,
        created_at="2024-01-01T00:00:00+00:00",
    )
    doc_novo = UploadedDocument(
        id="doc-novo",
        filename="novo.txt",
        content_type="text/plain",
        reader_method="text",
        chunks_count=1,
        created_at="2024-06-01T00:00:00+00:00",
    )

    for doc in [doc_antigo, doc_novo]:
        await fake_redis.set(f"documents:item:{doc.id}", doc.model_dump_json())
        from datetime import datetime
        score = datetime.fromisoformat(doc.created_at).timestamp()
        await fake_redis.zadd("documents:index", {doc.id: score})

    response = await async_client.get("/documents/")
    assert response.status_code == 200
    dados = response.json()
    assert len(dados) == 2
    # zrevrange devolve do mais recente para o mais antigo
    assert dados[0]["id"] == "doc-novo"
    assert dados[1]["id"] == "doc-antigo"


async def test_list_documentos_via_upload_retorna_documento(async_client):
    with patch(
        "app.services.ingestion.extract_document_text",
        return_value=("Texto simples para listagem.", "text"),
    ):
        upload_resp = await async_client.post(
            "/upload/",
            files={"files": ("via_upload.txt", b"Conteudo via upload", "text/plain")},
        )
    assert upload_resp.status_code == 200

    list_resp = await async_client.get("/documents/")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


# ── DELETE /documents/{id} ────────────────────────────────────────────────────

async def test_delete_documento_existente_retorna_204(async_client, fake_redis, sample_document, sample_chunk):
    await fake_redis.set(f"documents:item:{sample_document.id}", sample_document.model_dump_json())
    await fake_redis.zadd("documents:index", {sample_document.id: 0.0})
    await fake_redis.set(f"documents:chunk:{sample_chunk.id}", sample_chunk.model_dump_json())
    await fake_redis.sadd("documents:chunks", sample_chunk.id)

    response = await async_client.delete(f"/documents/{sample_document.id}")
    assert response.status_code == 204


async def test_delete_remove_documento_do_redis(async_client, fake_redis, sample_document):
    await fake_redis.set(f"documents:item:{sample_document.id}", sample_document.model_dump_json())
    await fake_redis.zadd("documents:index", {sample_document.id: 0.0})

    await async_client.delete(f"/documents/{sample_document.id}")

    assert await fake_redis.get(f"documents:item:{sample_document.id}") is None


async def test_delete_remove_chunks_do_redis(async_client, fake_redis, sample_document, sample_chunk):
    await fake_redis.set(f"documents:item:{sample_document.id}", sample_document.model_dump_json())
    await fake_redis.zadd("documents:index", {sample_document.id: 0.0})
    await fake_redis.set(f"documents:chunk:{sample_chunk.id}", sample_chunk.model_dump_json())
    await fake_redis.sadd("documents:chunks", sample_chunk.id)

    await async_client.delete(f"/documents/{sample_document.id}")

    assert await fake_redis.get(f"documents:chunk:{sample_chunk.id}") is None
    chunk_ids = await fake_redis.smembers("documents:chunks")
    assert sample_chunk.id not in chunk_ids


async def test_delete_documento_nao_aparece_mais_na_listagem(async_client, fake_redis, sample_document):
    await fake_redis.set(f"documents:item:{sample_document.id}", sample_document.model_dump_json())
    await fake_redis.zadd("documents:index", {sample_document.id: 0.0})

    await async_client.delete(f"/documents/{sample_document.id}")

    list_resp = await async_client.get("/documents/")
    ids = [d["id"] for d in list_resp.json()]
    assert sample_document.id not in ids


async def test_delete_documento_inexistente_retorna_404(async_client):
    response = await async_client.delete("/documents/id-que-nao-existe")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


async def test_delete_idempotente_segundo_delete_retorna_404(async_client, fake_redis, sample_document):
    await fake_redis.set(f"documents:item:{sample_document.id}", sample_document.model_dump_json())
    await fake_redis.zadd("documents:index", {sample_document.id: 0.0})

    primeiro = await async_client.delete(f"/documents/{sample_document.id}")
    segundo = await async_client.delete(f"/documents/{sample_document.id}")

    assert primeiro.status_code == 204
    assert segundo.status_code == 404
