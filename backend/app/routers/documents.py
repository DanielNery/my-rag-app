from fastapi import APIRouter, HTTPException, status

from app.models.schemas import UploadedDocument
from app.services import document_store

documents_router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


@documents_router.get("/", response_model=list[UploadedDocument])
async def get_documents():
    return await document_store.list_documents()


@documents_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str):
    was_deleted = await document_store.delete_document(document_id)
    if not was_deleted:
        raise HTTPException(status_code=404, detail="Document not found")
