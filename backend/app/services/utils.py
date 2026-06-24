from datetime import UTC, datetime

import redis.asyncio as redis

from app.config import settings


def now_iso() -> str:
    """Retorna a data e hora atual em UTC no formato ISO 8601."""
    return datetime.now(UTC).isoformat()


def score_from_iso(value: str) -> float:
    """Converte uma string ISO 8601 em timestamp UNIX (usado como score no Redis sorted set)."""
    return datetime.fromisoformat(value).timestamp()


def get_redis_client() -> redis.Redis:
    """Cria e retorna um cliente Redis assíncrono configurado via settings."""
    return redis.from_url(settings.redis_url, decode_responses=True)
