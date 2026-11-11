from app.services.vector_store import index_chunks

repository_id = "debug-test"

chunks = [
    {
        "repository_id": repository_id,
        "file_path": "main.py",
        "chunk_type": "function",
        "symbol_name": "hello",
        "start_line": 1,
        "end_line": 2,
        "content": 'def hello(): return "hello"',
    }
]

result = index_chunks(
    repository_id=repository_id,
    chunks=chunks,
)

print("Indexing result:", result)
