"""
Testes de integração para o endpoint POST /upload/

Cobre:
  - Upload de arquivo único
  - Upload de múltiplos arquivos
  - Erro de API da OpenAI (502)
  - Documento salvo fica visível em GET /documents/
"""

from unittest.mock import patch


async def test_upload_arquivo_texto_retorna_documento(async_client):
    with patch(
        "app.services.ingestion.extract_document_text",
        return_value=("Conteúdo do arquivo de texto.", "text"),
    ):
        response = await async_client.post(
            "/upload/",
            files={"files": ("doc.txt", b"Conteudo de texto simples", "text/plain")},
        )

    assert response.status_code == 200
    dados = response.json()
    assert len(dados) == 1
    doc = dados[0]
    assert doc["filename"] == "doc.txt"
    assert doc["reader_method"] == "text"
    assert doc["content_type"] == "text/plain"
    assert doc["chunks_count"] >= 1
    assert doc["id"]
    assert doc["created_at"]


async def test_upload_multiplos_arquivos_retorna_lista(async_client):
    with patch(
        "app.services.ingestion.extract_document_text",
        return_value=("Conteúdo de exemplo.", "text"),
    ):
        response = await async_client.post(
            "/upload/",
            files=[
                ("files", ("a.txt", b"Conteudo A", "text/plain")),
                ("files", ("b.txt", b"Conteudo B", "text/plain")),
            ],
        )

    assert response.status_code == 200
    dados = response.json()
    assert len(dados) == 2
    filenames = {d["filename"] for d in dados}
    assert filenames == {"a.txt", "b.txt"}


async def test_upload_erro_openai_retorna_502(async_client, mock_openai_client):
    from openai import OpenAIError

    mock_openai_client.embeddings.create.side_effect = OpenAIError("Falha na API da OpenAI")

    with patch(
        "app.services.ingestion.extract_document_text",
        return_value=("Texto longo " * 100, "text"),
    ):
        response = await async_client.post(
            "/upload/",
            files={"files": ("doc.txt", b"Conteudo qualquer", "text/plain")},
        )

    assert response.status_code == 502
    detalhe = response.json()["detail"]
    assert "OpenAI" in detalhe


async def test_upload_documento_fica_disponivel_em_get_documents(async_client):
    with patch(
        "app.services.ingestion.extract_document_text",
        return_value=("Conteúdo salvo para listagem.", "text"),
    ):
        upload_resp = await async_client.post(
            "/upload/",
            files={"files": ("listavel.txt", b"Conteudo listavel", "text/plain")},
        )

    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()[0]["id"]

    list_resp = await async_client.get("/documents/")
    assert list_resp.status_code == 200
    ids = [d["id"] for d in list_resp.json()]
    assert doc_id in ids


async def test_upload_chunks_count_reflete_tamanho_do_texto(async_client):
    texto_longo = "Palavra de conteudo longo. " * 300
    with patch(
        "app.services.ingestion.extract_document_text",
        return_value=(texto_longo, "text"),
    ):
        response = await async_client.post(
            "/upload/",
            files={"files": ("longo.txt", texto_longo.encode(), "text/plain")},
        )

    assert response.status_code == 200
    doc = response.json()[0]
    assert doc["chunks_count"] > 1
