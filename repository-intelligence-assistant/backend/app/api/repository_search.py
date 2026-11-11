import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.vector_store import search_repository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/repositories",
    tags=["Repository Search"],
)


class SearchRequest(BaseModel):
    repository_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/search")
def search_code(request: SearchRequest):
    """Search an indexed repository using natural language."""

    try:
        results = search_repository(
            repository_id=request.repository_id,
            query=request.query,
            top_k=request.top_k,
        )

        return {
            "repository_id": request.repository_id,
            "query": request.query,
            "result_count": len(results),
            "results": results,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.exception("Search request failed.")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while searching the repository.",
        ) from error