import re
from collections import defaultdict
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CHROMA_PATH = BACKEND_ROOT / "data" / "chroma_db"

CHROMA_PATH.mkdir(parents=True, exist_ok=True)

client = chromadb.PersistentClient(path=str(CHROMA_PATH))

collection = client.get_or_create_collection(
    name="repository_code",
    metadata={"hnsw:space": "cosine"},
)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)

# Reciprocal Rank Fusion constant.
RRF_K = 60
QUERY_TOKEN_SYNONYMS = {
    "application": {"app"},
}


# --------------------------------------------------
# Document Preparation
# --------------------------------------------------

def create_document(chunk: dict) -> str:
    """Create searchable text from code and metadata."""

    return (
        f"File: {chunk['file_path']}\n"
        f"Type: {chunk['chunk_type']}\n"
        f"Symbol: {chunk.get('symbol_name') or 'module'}\n"
        f"Code:\n{chunk['content']}"
    )


# --------------------------------------------------
# Indexing
# --------------------------------------------------

def index_chunks(repository_id: str, chunks: list[dict]) -> dict:
    """Generate embeddings and persist code chunks."""

    if not chunks:
        return {
            "repository_id": repository_id,
            "indexed_chunks": 0,
        }

    documents = [
        create_document(chunk)
        for chunk in chunks
    ]

    embeddings = model.encode(
        documents,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    ids = [
        f"{repository_id}_{index}"
        for index in range(len(chunks))
    ]

    metadatas = []

    for chunk in chunks:
        metadatas.append({
            "repository_id": repository_id,
            "file_path": chunk["file_path"],
            "chunk_type": chunk["chunk_type"],
            "symbol_name": chunk.get("symbol_name") or "",
            "start_line": int(chunk["start_line"]),
            "end_line": int(chunk["end_line"]),
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return {
        "repository_id": repository_id,
        "indexed_chunks": len(chunks),
    }


# --------------------------------------------------
# Shared Search Helpers
# --------------------------------------------------

def _format_result(
    document: str,
    metadata: dict,
    distance: float | None = None,
) -> dict:
    """Return a consistent representation of a code chunk."""

    return {
        "file_path": metadata["file_path"],
        "chunk_type": metadata["chunk_type"],
        "symbol_name": metadata["symbol_name"],
        "start_line": metadata["start_line"],
        "end_line": metadata["end_line"],
        "content": document,
        "distance": distance,
    }


def _get_repository_chunks(repository_id: str) -> list[dict]:
    """Retrieve indexed documents belonging to one repository."""

    results = collection.get(
        where={"repository_id": repository_id},
        include=["documents", "metadatas"],
    )

    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []

    return [
        _format_result(document, metadata)
        for document, metadata in zip(documents, metadatas)
    ]


# --------------------------------------------------
# Semantic Search
# --------------------------------------------------

def _semantic_search(
    repository_id: str,
    query: str,
    top_k: int,
) -> list[dict]:
    """Retrieve code using embedding similarity."""

    query_embedding = model.encode(
        [query],
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where={"repository_id": repository_id},
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    if not documents or not documents[0]:
        return []

    matches = []

    for document, metadata, distance in zip(
        documents[0],
        metadatas[0],
        distances[0],
    ):
        matches.append(
            _format_result(
                document=document,
                metadata=metadata,
                distance=float(distance),
            )
        )

    return matches


# --------------------------------------------------
# Keyword Search
# --------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Extract identifiers and words while preserving code terms."""

    return {
        token.lower()
        for token in re.findall(
            r"[A-Za-z_][A-Za-z0-9_]*|\d+",
            text,
        )
        if len(token) > 1
    }


def _query_tokens(query: str) -> set[str]:
    tokens = _tokenize(query)
    for token in tuple(tokens):
        tokens.update(QUERY_TOKEN_SYNONYMS.get(token, ()))
    return tokens


def _keyword_search(
    repository_id: str,
    query: str,
    top_k: int,
) -> list[dict]:
    """
    Rank repository chunks using lexical overlap.

    Exact identifier matches receive additional weight.
    """

    chunks = _get_repository_chunks(repository_id)

    query_tokens = _query_tokens(query)

    if not query_tokens:
        return []

    query_lower = query.lower()
    scored_chunks = []

    for chunk in chunks:
        content = chunk["content"]
        content_lower = content.lower()

        content_tokens = _tokenize(content)

        overlap = query_tokens & content_tokens

        if not overlap:
            continue

        # Give matches in identifiers more importance than
        # ordinary words in source code.
        symbol = (chunk.get("symbol_name") or "").lower()
        file_path = chunk.get("file_path", "").lower()

        score = len(overlap) / len(query_tokens)

        for token in overlap:
            if token == symbol:
                score += 1.5
            elif token in symbol:
                score += 0.75

            if token in file_path:
                score += 0.5

        # Additional signals for direct-execution questions.
        if (
            "__main__" in query_lower
            or "executed directly" in query_lower
            or "run directly" in query_lower
        ):
            if "__main__" in content_lower:
                score += 2.0

        # Preserve useful code matches only.
        if score > 0:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        chunk
        for _, chunk in scored_chunks[:top_k]
    ]


# --------------------------------------------------
# Reciprocal Rank Fusion
# --------------------------------------------------

def _reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    top_k: int,
) -> list[dict]:
    """
    Combine ranked lists using Reciprocal Rank Fusion.

    RRF score = sum(1 / (RRF_K + rank))
    """

    fused_scores = defaultdict(float)
    result_by_key = {}

    for ranked_list in ranked_lists:
        for rank, chunk in enumerate(ranked_list, start=1):
            key = (
                chunk["file_path"],
                chunk["start_line"],
                chunk["end_line"],
                chunk["chunk_type"],
                chunk["symbol_name"],
            )

            fused_scores[key] += 1.0 / (RRF_K + rank)

            if key not in result_by_key:
                result_by_key[key] = chunk.copy()
            else:
                existing = result_by_key[key]

                # Preserve semantic distance when the same chunk
                # appears in both retrieval lists.
                if (
                    existing.get("distance") is None
                    and chunk.get("distance") is not None
                ):
                    existing["distance"] = chunk["distance"]

    ranked_keys = sorted(
        fused_scores,
        key=lambda key: fused_scores[key],
        reverse=True,
    )

    fused_results = []

    for key in ranked_keys[:top_k]:
        result = result_by_key[key].copy()

        result["hybrid_score"] = fused_scores[key]

        fused_results.append(result)

    return fused_results


# --------------------------------------------------
# Public Search API
# --------------------------------------------------

def get_repository_chunk_count(repository_id: str) -> int:
    """Return the number of indexed chunks for a repository."""

    repository_id = (repository_id or "").strip()
    if not repository_id:
        return 0

    repository_records = collection.get(
        where={"repository_id": repository_id},
        include=[],
    )

    return len(repository_records.get("ids") or [])


def search_repository(
    repository_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Perform hybrid search combining semantic retrieval,
    keyword retrieval, and Reciprocal Rank Fusion.
    """

    repository_id = repository_id.strip()
    query = query.strip()

    if not repository_id:
        raise ValueError("Repository ID cannot be empty.")

    if not query:
        raise ValueError("Search query cannot be empty.")

    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20.")

    # Retrieve more candidates than the final result count.
    candidate_count = min(
        max(top_k * 3, 10),
        100,
    )

    # Ensure the repository exists in the index.
    repository_records = collection.get(
        where={"repository_id": repository_id},
        include=[],
    )

    repository_count = len(repository_records["ids"])

    if repository_count == 0:
        return []

    candidate_count = min(
        candidate_count,
        repository_count,
    )

    semantic_results = _semantic_search(
        repository_id=repository_id,
        query=query,
        top_k=candidate_count,
    )

    keyword_results = _keyword_search(
        repository_id=repository_id,
        query=query,
        top_k=candidate_count,
    )

    # A hybrid search can still work if one retriever returns
    # no matches.
    hybrid_results = _reciprocal_rank_fusion(
        ranked_lists=[
            semantic_results,
            keyword_results,
        ],
        top_k=top_k,
    )

    return hybrid_results