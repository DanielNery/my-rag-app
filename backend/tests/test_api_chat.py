"""
Testes de integração para o endpoint POST /chat/

Cobre o pipeline RAG completo:
  - Resposta normal (sem documentos, sem sessão)
  - Resposta com sessão válida pré-criada
  - Persistência das mensagens na sessão após chamada
  - Comportamento com erro da OpenAI (resposta graceful, não 5xx)
  - Fontes vazias quando Redis não tem chunks
"""


async def test_chat_retorna_resposta_basica(async_client):
    response = await async_client.post(
        "/chat/",
        json={"question": "O que é Python?", "session_id": "sessao-inexistente", "top_k": 3},
    )

    assert response.status_code == 200
    dados = response.json()
    assert "answer" in dados
    assert "sources" in dados
    assert isinstance(dados["answer"], str)
    assert len(dados["answer"]) > 0


async def test_chat_retorna_resposta_mockada_do_modelo(async_client):
    response = await async_client.post(
        "/chat/",
        json={"question": "Qual o conteúdo dos documentos?", "session_id": "qualquer", "top_k": 5},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Resposta mockada do modelo."


async def test_chat_fontes_vazias_quando_redis_sem_chunks(async_client):
    response = await async_client.post(
        "/chat/",
        json={"question": "Pergunta sem documentos.", "session_id": "sessao-vazia", "top_k": 5},
    )

    assert response.status_code == 200
    assert response.json()["sources"] == []


async def test_chat_com_sessao_valida(async_client):
    sessao_resp = await async_client.post("/session/", json={"name": "Sessão de Teste"})
    assert sessao_resp.status_code == 201
    session_id = sessao_resp.json()["id"]

    response = await async_client.post(
        "/chat/",
        json={"question": "Pergunta com sessão.", "session_id": session_id, "top_k": 3},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Resposta mockada do modelo."


async def test_chat_persiste_mensagens_na_sessao(async_client):
    sessao_resp = await async_client.post("/session/", json={"name": "Sessão Persistência"})
    session_id = sessao_resp.json()["id"]

    await async_client.post(
        "/chat/",
        json={"question": "Minha pergunta de teste.", "session_id": session_id, "top_k": 3},
    )

    sessao_atualizada = await async_client.get(f"/session/{session_id}")
    assert sessao_atualizada.status_code == 200

    mensagens = sessao_atualizada.json()["messages"]
    roles = [m["role"] for m in mensagens]
    assert "user" in roles
    assert "assistant" in roles


async def test_chat_mensagem_usuario_salva_com_texto_correto(async_client):
    sessao_resp = await async_client.post("/session/", json={"name": "Sessão Texto"})
    session_id = sessao_resp.json()["id"]

    pergunta = "Qual é a capital do Brasil?"
    await async_client.post(
        "/chat/",
        json={"question": pergunta, "session_id": session_id, "top_k": 3},
    )

    sessao = await async_client.get(f"/session/{session_id}")
    mensagens = sessao.json()["messages"]
    mensagens_usuario = [m for m in mensagens if m["role"] == "user"]
    assert any(m["text"] == pergunta for m in mensagens_usuario)


async def test_chat_erro_openai_retorna_mensagem_graceful(async_client, mock_openai_client):
    from openai import OpenAIError

    mock_openai_client.responses.create.side_effect = OpenAIError("Erro simulado de API")

    response = await async_client.post(
        "/chat/",
        json={"question": "Pergunta que causa erro.", "session_id": "qualquer", "top_k": 3},
    )

    # O router captura OpenAIError e retorna 200 com mensagem de erro no campo answer
    assert response.status_code == 200
    dados = response.json()
    assert "Erro" in dados["answer"] or "OpenAI" in dados["answer"]
    assert dados["sources"] == []


async def test_chat_top_k_minimo_aceito(async_client):
    response = await async_client.post(
        "/chat/",
        json={"question": "Pergunta.", "session_id": "s", "top_k": 1},
    )
    assert response.status_code == 200


async def test_chat_top_k_maximo_aceito(async_client):
    response = await async_client.post(
        "/chat/",
        json={"question": "Pergunta.", "session_id": "s", "top_k": 20},
    )
    assert response.status_code == 200


async def test_chat_top_k_invalido_retorna_422(async_client):
    response = await async_client.post(
        "/chat/",
        json={"question": "Pergunta.", "session_id": "s", "top_k": 0},
    )
    assert response.status_code == 422


async def test_chat_question_vazia_retorna_422(async_client):
    response = await async_client.post(
        "/chat/",
        json={"question": "", "session_id": "s", "top_k": 5},
    )
    assert response.status_code == 422
