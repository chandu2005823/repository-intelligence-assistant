import logging
import os
import shutil
import uuid
import zipfile

from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import NamedTemporaryFile

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.repository_service import analyze_repository
from app.services.code_analyzer import analyze_python_repository
from app.services.code_chunker import chunk_repository
from app.services.vector_store import get_repository_chunk_count, index_chunks


router = APIRouter(
    prefix="/api/repositories",
    tags=["Repositories"],
)


# Project storage configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = PROJECT_ROOT / "data" / "repositories"

# Load environment configuration
load_dotenv(PROJECT_ROOT / ".env")

# Configurable upload limits (in MB, converted to bytes)
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "2048"))
MAX_EXTRACTED_SIZE_MB = int(os.getenv("MAX_EXTRACTED_SIZE_MB", "2048"))
MAX_SINGLE_FILE_SIZE_MB = int(os.getenv("MAX_SINGLE_FILE_SIZE_MB", "50"))
MAX_REPOSITORY_FILES = int(os.getenv("MAX_REPOSITORY_FILES", "50000"))

# Convert MB to bytes
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
MAX_EXTRACTED_SIZE = MAX_EXTRACTED_SIZE_MB * 1024 * 1024
MAX_SINGLE_FILE_SIZE = MAX_SINGLE_FILE_SIZE_MB * 1024 * 1024
MAX_FILES = MAX_REPOSITORY_FILES

# Streaming chunk size (1 MB)
UPLOAD_CHUNK_SIZE = 1024 * 1024

# ZIP bomb protection: max compression ratio
MAX_COMPRESSION_RATIO = 100

ALLOWED_EXTENSIONS = {".zip"}


def validate_archive_member(name: str) -> bool:
    """
    Reject archive paths that could escape the extraction directory.
    """

    if "\x00" in name:
        return False

    posix_path = PurePosixPath(name)
    windows_path = PureWindowsPath(name)

    if posix_path.is_absolute() or windows_path.is_absolute():
        return False

    if windows_path.drive:
        return False

    if ".." in posix_path.parts or ".." in windows_path.parts:
        return False

    return True


def _serialize_repository(repository_id: str, include_analysis: bool = False) -> dict | None:
    repository_path = STORAGE_ROOT / repository_id

    if not repository_path.exists() or not repository_path.is_dir():
        return None

    summary = analyze_repository(repository_path)
    indexed_chunk_count = get_repository_chunk_count(repository_id)

    record = {
        "repository_id": repository_id,
        "repository_name": summary["repository_name"],
        "file_count": summary["file_count"],
        "total_size_bytes": summary["total_size_bytes"],
        "languages": summary["languages"],
        "directories": summary["directories"],
        "important_files": summary["important_files"],
        "indexed_chunk_count": indexed_chunk_count,
        "indexing_status": "indexed" if indexed_chunk_count > 0 else "missing",
        "created_at": repository_path.stat().st_mtime,
    }

    if include_analysis:
        record["analysis"] = analyze_python_repository(repository_path)

    return record


@router.get("")
async def list_repositories():
    """Return metadata for previously indexed repositories."""

    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    repositories = []

    for repository_directory in sorted(STORAGE_ROOT.iterdir()):
        if not repository_directory.is_dir():
            continue

        repository = _serialize_repository(repository_directory.name)
        if repository is not None:
            repositories.append(repository)

    return {
        "count": len(repositories),
        "repositories": repositories,
    }


@router.get("/{repository_id}")
async def get_repository(repository_id: str):
    """Return analysis detail for a single repository."""

    normalized_id = (repository_id or "").strip()
    if not normalized_id:
        raise HTTPException(status_code=400, detail="Repository ID is required.")

    repository = _serialize_repository(normalized_id, include_analysis=True)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found.")

    return repository


@router.post("/upload")
async def upload_repository(file: UploadFile = File(...)):
    """
    Upload, safely extract, analyze, chunk, and index a repository ZIP.
    Supports up to 2 GB uploads with streaming and comprehensive safety checks.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A filename is required.",
        )

    if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only ZIP files are supported.",
        )

    repository_id = uuid.uuid4().hex

    STORAGE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = None
    repository_path = STORAGE_ROOT / repository_id
    should_cleanup_repository = True
    
    # Tracking for reporting
    files_skipped = 0
    files_skipped_reasons = []

    try:
        # --------------------------------------------------
        # 1. Stream upload with size limit (no full load to RAM)
        # --------------------------------------------------
        upload_size = 0

        with NamedTemporaryFile(
            mode="wb",
            suffix=".zip",
            dir=STORAGE_ROOT,
            delete=False,
        ) as temporary_file:

            temporary_path = Path(temporary_file.name)

            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)

                if not chunk:
                    break

                upload_size += len(chunk)

                if upload_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"ZIP file exceeds the {MAX_UPLOAD_SIZE_MB} MB upload limit.",
                    )

                temporary_file.write(chunk)

        logger.info(f"Uploaded ZIP size: {upload_size / (1024 * 1024):.2f} MB")

        # --------------------------------------------------
        # 2. Validate ZIP and check for ZIP bombs
        # --------------------------------------------------
        with zipfile.ZipFile(temporary_path, "r") as archive:

            members = archive.infolist()

            if len(members) > MAX_FILES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Archive contains too many entries. Maximum allowed: {MAX_FILES}.",
                )

            total_uncompressed_size = 0
            file_count = 0

            for member in members:

                if not member.filename or not member.filename.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="Archive contains an empty file name.",
                    )

                if not validate_archive_member(member.filename):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Archive contains an unsafe file path: {member.filename}",
                    )

                # Reject symbolic links in ZIP metadata
                unix_mode = (member.external_attr >> 16) & 0o170000

                if unix_mode == 0o120000:
                    raise HTTPException(
                        status_code=400,
                        detail="Symbolic links are not allowed.",
                    )

                # Check individual file size limit
                if member.file_size > MAX_SINGLE_FILE_SIZE:
                    files_skipped += 1
                    files_skipped_reasons.append(
                        f"File '{member.filename}' exceeds {MAX_SINGLE_FILE_SIZE_MB} MB limit"
                    )
                    continue

                if not member.is_dir():
                    file_count += 1

                total_uncompressed_size += member.file_size

            # Check total extracted size
            if total_uncompressed_size > MAX_EXTRACTED_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Extracted archive exceeds the {MAX_EXTRACTED_SIZE_MB} MB limit. "
                        f"Uncompressed size: {total_uncompressed_size / (1024 * 1024):.2f} MB"
                    ),
                )

            # ZIP bomb detection: check compression ratio
            if upload_size > 0:
                compression_ratio = total_uncompressed_size / upload_size
                if compression_ratio > MAX_COMPRESSION_RATIO:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Suspicious compression ratio detected (ZIP bomb protection). "
                            f"Ratio: {compression_ratio:.1f}:1, Maximum allowed: {MAX_COMPRESSION_RATIO}:1"
                        ),
                    )

            logger.info(
                f"ZIP validation passed: {file_count} files, "
                f"{total_uncompressed_size / (1024 * 1024):.2f} MB uncompressed, "
                f"compression ratio: {compression_ratio:.1f}:1"
            )

            # --------------------------------------------------
            # 3. Extract files with safety checks during extraction
            # --------------------------------------------------
            repository_path.mkdir(
                parents=True,
                exist_ok=False,
            )

            extracted_size = 0
            extracted_files = 0

            for member in members:

                if member.is_dir():
                    continue

                # Skip files that exceeded individual size limit
                if member.file_size > MAX_SINGLE_FILE_SIZE:
                    continue

                relative_path = Path(
                    *PurePosixPath(member.filename).parts
                )

                destination = repository_path / relative_path

                # Defense in depth: prevent extraction outside the root
                if not destination.resolve().is_relative_to(
                    repository_path.resolve()
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Archive contains an unsafe destination: {member.filename}",
                    )

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                # Extract with size tracking (protection during extraction)
                with archive.open(member, "r") as source:
                    with destination.open("wb") as target:
                        bytes_written = 0
                        while True:
                            chunk = source.read(UPLOAD_CHUNK_SIZE)
                            if not chunk:
                                break
                            
                            bytes_written += len(chunk)
                            extracted_size += len(chunk)
                            
                            # Real-time extracted size check
                            if extracted_size > MAX_EXTRACTED_SIZE:
                                raise HTTPException(
                                    status_code=413,
                                    detail=f"Extraction stopped: exceeded {MAX_EXTRACTED_SIZE_MB} MB limit during extraction.",
                                )
                            
                            target.write(chunk)
                        
                        extracted_files += 1

            logger.info(f"Extracted {extracted_files} files, {extracted_size / (1024 * 1024):.2f} MB total")

        # --------------------------------------------------
        # 4. Analyze repository inventory
        # --------------------------------------------------
        summary = analyze_repository(repository_path)

        # --------------------------------------------------
        # 5. Analyze Python source code using AST
        # --------------------------------------------------
        code_analysis = analyze_python_repository(
            repository_path
        )

        # --------------------------------------------------
        # 6. Generate structured source-code chunks
        # --------------------------------------------------
        chunking_result = chunk_repository(
            repository_root=repository_path,
            repository_id=repository_id,
        )

        # --------------------------------------------------
        # 7. Generate embeddings and index chunks in ChromaDB
        # --------------------------------------------------
        indexing_result = index_chunks(
            repository_id=repository_id,
            chunks=chunking_result["chunks"],
        )

        # --------------------------------------------------
        # 8. Return complete analysis response with warnings if files were skipped
        # --------------------------------------------------
        should_cleanup_repository = False
        
        response = {
            "repository_id": repository_id,
            "status": "analyzed",
            "upload_info": {
                "compressed_size_mb": round(upload_size / (1024 * 1024), 2),
                "extracted_size_mb": round(extracted_size / (1024 * 1024), 2),
                "extracted_files": extracted_files,
                "compression_ratio": round(extracted_size / upload_size, 2) if upload_size > 0 else 0,
            },
            "summary": summary,
            "code_analysis": code_analysis,
            "chunking": {
                "python_files_processed": (
                    chunking_result["python_files_processed"]
                ),
                "source_files_processed": (
                    chunking_result["source_files_processed"]
                ),
                "chunk_count": chunking_result["chunk_count"],
                "chunks": chunking_result["chunks"],
            },
            "indexing": indexing_result,
        }
        
        # Include warnings about skipped files if any
        if files_skipped > 0:
            response["warnings"] = {
                "files_skipped": files_skipped,
                "reasons": files_skipped_reasons[:10],  # Limit to first 10 reasons
                "message": f"{files_skipped} file(s) were skipped due to size limits. Repository indexed successfully with remaining files."
            }
        
        return response

    except zipfile.BadZipFile as error:
        logger.exception("ZIP validation failed.")
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid ZIP archive.",
        ) from error

    except HTTPException:
        raise

    except OSError as error:
        logger.exception("Repository processing failed while writing files.")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the repository.",
        ) from error

    except Exception as error:
        logger.exception("Unexpected repository upload failure.")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the repository.",
        ) from error

    finally:
        # Clean up temporary ZIP file regardless of outcome
        if temporary_path and temporary_path.exists():
            try:
                temporary_path.unlink(missing_ok=True)
                logger.debug(f"Cleaned up temporary file: {temporary_path}")
            except OSError as cleanup_error:
                logger.warning(f"Could not delete temporary file {temporary_path}: {cleanup_error}")

        # Clean up incomplete repository directory on failure
        if should_cleanup_repository and repository_path.exists() and repository_path.is_dir():
            try:
                shutil.rmtree(repository_path)
                logger.info(f"Cleaned up incomplete repository directory: {repository_path}")
            except OSError as cleanup_error:
                logger.warning(f"Could not clean up repository directory {repository_path}: {cleanup_error}")

        # Ensure file handle is closed
        await file.close()