import math

from app.config import settings
from app.services.openai_client import get_openai_client


async def embed_text(text: str) -> list[float]:
    """Gera embeddings para um texto usando o modelo de embedding do OpenAI.

    Args:
        text (str): Texto a ser embedado.

    Returns:
        list[float]: Embeddings do texto.
    """
    client = get_openai_client()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
    )

    return response.data[0].embedding


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Calcula a similaridade cosseno entre dois vetores.

    Args:
        left (list[float]): Vetor esquerdo.
        right (list[float]): Vetor direito.

    Returns:
        float: Similaridade cosseno entre os dois vetores.
    """
    if not left or not right:
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)
