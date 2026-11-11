import ast
from pathlib import Path

from app.services.repository_service import (
    IGNORED_DIRECTORIES,
    IGNORED_FILES,
    LANGUAGE_EXTENSIONS,
)

MAX_CHUNK_LINES = 80


def split_large_block(
    source_lines: list[str],
    start_line: int,
    end_line: int,
    max_lines: int = MAX_CHUNK_LINES,
) -> list[tuple[int, int, str]]:
    """
    Split a large source block into bounded line-based chunks.

    Line numbers are one-based and inclusive.
    """

    chunks = []

    for start in range(start_line, end_line + 1, max_lines):
        end = min(start + max_lines - 1, end_line)

        content = "\n".join(source_lines[start - 1:end])

        if not content.strip():
            continue

        chunks.append((start, end, content))

    return chunks


def chunk_python_file(
    file_path: Path,
    repository_root: Path,
    repository_id: str,
) -> list[dict]:
    """
    Create source-code chunks from a Python file.

    Functions and classes are kept together when they fit within
    MAX_CHUNK_LINES. Large blocks are split into smaller chunks.
    """

    if any(part in IGNORED_DIRECTORIES for part in file_path.parts):
        return []

    try:
        source_code = file_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []

    source_lines = source_code.splitlines()

    if not source_lines:
        return []

    relative_path = file_path.relative_to(repository_root).as_posix()

    try:
        tree = ast.parse(source_code, filename=relative_path)
    except SyntaxError:
        # Preserve invalid Python source for later inspection.
        return [
            {
                "repository_id": repository_id,
                "file_path": relative_path,
                "chunk_type": "file",
                "symbol_name": None,
                "start_line": 1,
                "end_line": len(source_lines),
                "content": source_code,
            }
        ]

    blocks = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            blocks.append({
                "chunk_type": "function",
                "symbol_name": node.name,
                "start_line": node.lineno,
                "end_line": node.end_lineno or node.lineno,
            })

        elif isinstance(node, ast.ClassDef):
            blocks.append({
                "chunk_type": "class",
                "symbol_name": node.name,
                "start_line": node.lineno,
                "end_line": node.end_lineno or node.lineno,
            })

    chunks = []
    covered_lines = set()

    for block in blocks:
        start_line = block["start_line"]
        end_line = block["end_line"]

        if end_line - start_line + 1 > MAX_CHUNK_LINES:
            segments = split_large_block(
                source_lines,
                start_line,
                end_line,
            )
        else:
            segments = [
                (
                    start_line,
                    end_line,
                    "\n".join(source_lines[start_line - 1:end_line]),
                )
            ]

        for index, (start, end, content) in enumerate(segments, start=1):
            chunks.append({
                "repository_id": repository_id,
                "file_path": relative_path,
                "chunk_type": block["chunk_type"],
                "symbol_name": block["symbol_name"],
                "chunk_part": index,
                "start_line": start,
                "end_line": end,
                "content": content,
            })

            covered_lines.update(range(start, end + 1))

    # Preserve imports, module-level statements, comments, and any other
    # source lines not covered by a top-level function or class.
    remaining_lines = [
        index
        for index in range(1, len(source_lines) + 1)
        if index not in covered_lines
    ]

    if remaining_lines:
        groups = []
        current_group = [remaining_lines[0]]

        for line_number in remaining_lines[1:]:
            if line_number == current_group[-1] + 1:
                current_group.append(line_number)
            else:
                groups.append(current_group)
                current_group = [line_number]

        groups.append(current_group)

        for group in groups:
            start = group[0]
            end = group[-1]

            segments = split_large_block(
                source_lines,
                start,
                end,
            )

            for index, (segment_start, segment_end, content) in enumerate(
                segments,
                start=1,
            ):
                chunks.append({
                    "repository_id": repository_id,
                    "file_path": relative_path,
                    "chunk_type": "module",
                    "symbol_name": None,
                    "chunk_part": index,
                    "start_line": segment_start,
                    "end_line": segment_end,
                    "content": content,
                })

    chunks.sort(key=lambda chunk: chunk["start_line"])

    return chunks


def chunk_python_repository(
    repository_root: Path,
    repository_id: str,
) -> dict:
    """
    Chunk all eligible Python files in a repository.
    """

    all_chunks = []
    analyzed_files = 0

    for file_path in repository_root.rglob("*.py"):
        if any(part in IGNORED_DIRECTORIES for part in file_path.parts):
            continue

        file_chunks = chunk_python_file(
            file_path=file_path,
            repository_root=repository_root,
            repository_id=repository_id,
        )

        if file_chunks:
            analyzed_files += 1
            all_chunks.extend(file_chunks)

    return {
        "python_files_processed": analyzed_files,
        "chunk_count": len(all_chunks),
        "chunks": all_chunks,
    }


def _chunk_text_file(
    file_path: Path,
    repository_root: Path,
    repository_id: str,
) -> list[dict]:
    if file_path.is_symlink() or any(
        part in IGNORED_DIRECTORIES
        for part in file_path.relative_to(repository_root).parts[:-1]
    ):
        return []

    if file_path.name in IGNORED_FILES or file_path.name.startswith(".env."):
        return []

    try:
        source_code = file_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []

    lines = source_code.splitlines()
    if not lines:
        return []

    relative_path = file_path.relative_to(repository_root).as_posix()
    chunks = []
    for start_line in range(1, len(lines) + 1, MAX_CHUNK_LINES):
        end_line = min(start_line + MAX_CHUNK_LINES - 1, len(lines))
        content = "\n".join(lines[start_line - 1:end_line])
        if not content.strip():
            continue
        chunks.append({
            "repository_id": repository_id,
            "file_path": relative_path,
            "chunk_type": "source",
            "symbol_name": None,
            "start_line": start_line,
            "end_line": end_line,
            "content": content,
        })

    return chunks


def chunk_repository(repository_root: Path, repository_id: str) -> dict:
    """Chunk Python structurally and other supported text files by source lines."""
    python_result = chunk_python_repository(repository_root, repository_id)
    all_chunks = list(python_result["chunks"])
    source_files_processed = {
        chunk["file_path"]
        for chunk in all_chunks
    }

    for file_path in sorted(repository_root.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in LANGUAGE_EXTENSIONS:
            continue
        if file_path.suffix.lower() == ".py":
            continue

        source_chunks = _chunk_text_file(
            file_path=file_path,
            repository_root=repository_root,
            repository_id=repository_id,
        )
        if source_chunks:
            source_files_processed.add(source_chunks[0]["file_path"])
            all_chunks.extend(source_chunks)

    return {
        "python_files_processed": python_result["python_files_processed"],
        "source_files_processed": len(source_files_processed),
        "chunk_count": len(all_chunks),
        "chunks": all_chunks,
    }