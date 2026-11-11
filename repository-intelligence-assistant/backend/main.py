from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.conversations import router as conversations_router
from app.api.repositories import router as repositories_router
from app.api.repository_search import router as search_router
from app.api.repository_qa import router as qa_router
from app.api.repository_analysis import router as repository_analysis_router

app = FastAPI(
    title="AI-Powered Repository Intelligence Assistant",
    description=(
        "Analyze software repositories, explain source code, "
        "explore dependencies, and investigate bugs."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations_router)
app.include_router(repositories_router)
app.include_router(search_router)
app.include_router(qa_router)
app.include_router(repository_analysis_router)


@app.get("/")
def home():
    return {
        "message": "Repository Intelligence Assistant is running!",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "repository-intelligence-backend",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
