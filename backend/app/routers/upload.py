from fastapi import APIRouter, File, HTTPException, UploadFile
from openai import OpenAIError

from app.models.schemas import UploadedDocument
from app.services.ingestion import ingest_files

upload_router = APIRouter(
    prefix="/upload",
    tags=["upload"],
)

@upload_router.post("/", response_model=list[UploadedDocument])
async def upload_files(files: list[UploadFile] = File(...)):
    try:
        return await ingest_files(files)
    except OpenAIError as error:
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao gerar embeddings com OpenAI: {error}",
        ) from error
