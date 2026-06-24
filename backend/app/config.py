
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BASE_DIR.parent

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=True)


class Settings:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    openai_embedding_model = os.getenv(
        "OPENAI_EMBEDDING_MODEL",
        "text-embedding-3-small",
    )


settings = Settings()
