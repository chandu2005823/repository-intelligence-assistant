import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm_service import LLMServiceError, generate_repository_answer
from app.services.vector_store import search_repository

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/repositories",
    tags=["Repository Question Answering"],
)


class QuestionRequest(BaseModel):
    repository_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)


@router.post("/ask")
def ask_repository_question(request: QuestionRequest):
    """
    Retrieve relevant repository code and generate an AI answer.
    """

    try:
        retrieved_chunks = search_repository(
            repository_id=request.repository_id,
            query=request.question,
            top_k=request.top_k,
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "repository_retrieval_failed",
                "message": "Repository search failed. Check the backend logs and try again.",
            },
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.error(
            "Repository retrieval failed: exception_type=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "repository_retrieval_failed",
                "message": "Repository search failed. Check the backend logs and try again.",
            },
        ) from error

    try:
        answer = generate_repository_answer(
            question=request.question,
            retrieved_chunks=retrieved_chunks,
        )
    except LLMServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.error(
            "Repository answer generation failed: exception_type=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "repository_answer_failed",
                "message": "Answer generation failed unexpectedly. Check the backend logs and try again.",
            },
        ) from error

    sources = [
        {
            "file_path": chunk.get("file_path"),
            "chunk_type": chunk.get("chunk_type"),
            "symbol_name": chunk.get("symbol_name"),
            "start_line": chunk.get("start_line"),
            "end_line": chunk.get("end_line"),
            "distance": chunk.get("distance"),
        }
        for chunk in retrieved_chunks
    ]

    return {
        "repository_id": request.repository_id,
        "question": request.question,
        "answer": answer,
        "source_count": len(sources),
        "sources": sources,
    }
    