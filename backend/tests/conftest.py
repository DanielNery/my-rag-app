"""
Fixtures compartilhadas para toda a suite de testes.

Estratégia de mocks:
- Redis  → fakeredis com FakeServer compartilhado por teste, garantindo
           isolamento entre testes e consistência de dados entre fixtures.
- OpenAI → MagicMock/AsyncMock nas camadas embeddings e rag_chain.
"""

import fakeredis
import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.models.schemas import DocumentChunk, UploadedDocument

# Embedding fixo de 1536 dimensões para uso previsível nos testes
_MOCK_EMBEDDING = [round(0.001 * i, 4) for i in range(1536)]


# ── Redis ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_redis_server():
    """Servidor Redis em memória compartilhado por todas as fixtures de um teste."""
    return fakeredis.FakeServer()


@pytest.fixture
def fake_redis(fake_redis_server):
    """
    Instância FakeRedis para uso direto nos testes (seed/leitura).
    Compartilha o mesmo FakeServer que os serviços patchados usam.
    """
    return fakeredis.aioredis.FakeRedis(server=fake_redis_server, decode_responses=True)


# ── OpenAI ────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_embedding():
    return _MOCK_EMBEDDING.copy()


@pytest.fixture
def mock_openai_client(mock_embedding):
    """Cliente OpenAI mockado com embeddings e respostas pré-configurados."""
    client = MagicMock()

    embedding_data = MagicMock()
    embedding_data.embedding = mock_embedding
    embedding_response = MagicMock()
    embedding_response.data = [embedding_data]
    client.embeddings.create = AsyncMock(return_value=embedding_response)

    chat_response = MagicMock()
    chat_response.output_text = "Resposta mockada do modelo."
    client.responses.create = AsyncMock(return_value=chat_response)

    return client


# ── Dados de exemplo ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_document():
    return UploadedDocument(
        id="doc-test-123",
        filename="arquivo_teste.txt",
        content_type="text/plain",
        reader_method="text",
        chunks_count=1,
        created_at="2024-01-01T00:00:00+00:00",
    )


@pytest.fixture
def sample_chunk(mock_embedding):
    return DocumentChunk(
        id="chunk-test-123",
        document_id="doc-test-123",
        source="arquivo_teste.txt",
        content="Conteúdo do chunk de teste para verificação.",
        embedding=mock_embedding,
        reader_method="text",
        created_at="2024-01-01T00:00:00+00:00",
    )


# ── Helpers de patch ──────────────────────────────────────────────────────────

def _redis_factory(fake_redis_server):
    """Retorna um callable que cria novas instâncias FakeRedis no mesmo servidor."""
    def _make():
        return fakeredis.aioredis.FakeRedis(server=fake_redis_server, decode_responses=True)
    return _make


# ── Fixtures de integração ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def async_client(fake_redis_server, mock_openai_client):
    """
    AsyncClient do httpx apontado para a aplicação FastAPI com todos os
    serviços externos (Redis e OpenAI) substituídos por mocks.
    """
    make_redis = _redis_factory(fake_redis_server)
    with (
        patch("app.services.document_store.get_redis_client", side_effect=make_redis),
        patch("app.services.session_store.get_redis_client", side_effect=make_redis),
        patch("app.services.embeddings.get_openai_client", return_value=mock_openai_client),
        patch("app.services.rag_chain.get_openai_client", return_value=mock_openai_client),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


@pytest_asyncio.fixture
async def patched_services(fake_redis_server, mock_openai_client):
    """
    Aplica os patches de serviços sem criar cliente HTTP.
    Útil para testes unitários de services/ingestion.
    """
    make_redis = _redis_factory(fake_redis_server)
    with (
        patch("app.services.document_store.get_redis_client", side_effect=make_redis),
        patch("app.services.session_store.get_redis_client", side_effect=make_redis),
        patch("app.services.embeddings.get_openai_client", return_value=mock_openai_client),
    ):
        yield
