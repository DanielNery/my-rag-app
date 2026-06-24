from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.chat import chat_router
from app.routers.documents import documents_router
from app.routers.session import session_router
from app.routers.upload import upload_router

app = FastAPI(
    title="API for the backend",
    description="API for the backend",
    version="0.1.0",
    contact={
        "name": "API Support",
        "url": "https://www.google.com",
        "email": "support@example.com",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://master.d2lr5f2wgywxvc.amplifyapp.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(session_router)
app.include_router(upload_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
