import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.services.code_intelligence_service import analyze_code
from app.services.code_review_service import analyze_code_review
from app.services.dependency_service import analyze_dependencies
from app.services.llm_service import LLMServiceError, generate_repository_answer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/repositories", tags=["Repository Analysis"])
STORAGE_ROOT = Path(__file__).resolve().parents[2] / "data" / "repositories"


def _repository_root(repository_id: str) -> Path:
    normalized_id = (repository_id or "").strip()
    if not normalized_id or len(normalized_id) > 100 or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for character in normalized_id
    ):
        raise HTTPException(status_code=400, detail="Invalid repository ID.")

    root = STORAGE_ROOT / normalized_id
    if root.is_symlink() or not root.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found.")
    try:
        root.resolve().relative_to(STORAGE_ROOT.resolve())
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Repository not found.") from error
    return root


@router.get("/{repository_id}/dependencies")
def get_repository_dependencies(repository_id: str):
    root = _repository_root(repository_id)
    try:
        return analyze_dependencies(repository_id, root)
    except Exception as error:
        logger.exception("Dependency analysis failed for repository.")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while analyzing repository dependencies.",
        ) from error


@router.get("/{repository_id}/intelligence")
def get_code_intelligence(
    repository_id: str,
    query: str = Query(default="", max_length=500),
    file_path: str = Query(default="", max_length=1000),
):
    root = _repository_root(repository_id)
    try:
        return analyze_code(repository_id, root, query=query, file_path=file_path)
    except Exception as error:
        logger.exception("Code intelligence analysis failed for repository.")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while analyzing repository code.",
        ) from error


@router.post("/{repository_id}/review")
def review_repository(repository_id: str):
    root = _repository_root(repository_id)
    try:
        findings = analyze_code_review(root)
    except Exception as error:
        logger.exception("Static code review failed for repository.")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while reviewing repository source.",
        ) from error

    ai_status = "not_configured"
    ai_explanation = None
    ai_error = None
    ai_sources = []
    if findings:
        chunks = []
        for finding in findings[:10]:
            source_path = root / finding["file_path"]
            try:
                lines = source_path.read_text(encoding="utf-8-sig").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            start = max(1, finding["start_line"] - 2)
            end = min(len(lines), finding["end_line"] + 2)
            chunks.append({
                "file_path": finding["file_path"],
                "chunk_type": "review_evidence",
                "symbol_name": finding["title"],
                "start_line": start,
                "end_line": end,
                "content": "\n".join(lines[start - 1:end]),
            })
        ai_sources = [
            {
                "file_path": chunk["file_path"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
            }
            for chunk in chunks
        ]
        if chunks:
            try:
                ai_explanation = generate_repository_answer(
                    (
                        "Explain the following static code review findings using only the "
                        "provided source excerpts. For each, explain why it may matter and "
                        "give a practical mitigation. Treat every finding as a potential "
                        "concern rather than a confirmed exploit or bug unless the code "
                        "directly proves it. Cite supported claims with the provided "
                        "[SOURCE N] identifiers. Do not invent additional findings, "
                        "locations, or behavior.\n\n"
                        f"Static findings:\n{findings[:10]}"
                    ),
                    chunks,
                )
                ai_status = "available"
            except LLMServiceError as error:
                ai_status = (
                    "missing_api_key"
                    if error.code in {
                        "groq_configuration_missing",
                        "gemini_configuration_missing",
                    }
                    else "failed"
                )
                ai_error = error.message
                logger.warning(
                    "AI code review explanation failed: code=%s",
                    error.code,
                )
    else:
        ai_status = "no_findings"

    return {
        "repository_id": repository_id,
        "findings": findings,
        "summary": (
            f"Static review reported {len(findings)} potential finding(s). "
            "Findings require developer verification; no source files were changed."
        ),
        "ai_status": ai_status,
        "ai_explanation": ai_explanation,
        "ai_error": ai_error,
        "ai_sources": ai_sources,
    }
