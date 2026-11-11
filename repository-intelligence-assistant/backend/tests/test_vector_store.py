import unittest
from uuid import uuid4
from unittest.mock import patch

import chromadb
from fastapi.testclient import TestClient

from app.services.vector_store import (
    index_chunks,
    search_repository,
)
from main import app


class TestVectorStore(unittest.TestCase):

    def test_indexes_and_searches_code(self):
        repository_id = "vector-store-test"

        chunks = [
            {
                "repository_id": repository_id,
                "file_path": "auth.py",
                "chunk_type": "function",
                "symbol_name": "authenticate_user",
                "start_line": 1,
                "end_line": 4,
                "content": (
                    "def authenticate_user(username, password):\n"
                    "    return verify_credentials(username, password)"
                ),
            },
            {
                "repository_id": repository_id,
                "file_path": "reports.py",
                "chunk_type": "function",
                "symbol_name": "generate_report",
                "start_line": 1,
                "end_line": 3,
                "content": (
                    "def generate_report():\n"
                    "    return 'Monthly sales report'"
                ),
            },
        ]

        client = chromadb.EphemeralClient()
        test_collection = client.create_collection(
            name=f"vector_store_test_{uuid4().hex}",
            metadata={"hnsw:space": "cosine"},
        )
        try:
            with patch("app.services.vector_store.collection", test_collection):
                index_result = index_chunks(repository_id, chunks)
                self.assertEqual(index_result["indexed_chunks"], 2)

                results = search_repository(
                    repository_id=repository_id,
                    query="Where are user login credentials checked?",
                    top_k=2,
                )

                self.assertGreaterEqual(len(results), 1)
                self.assertTrue(any(
                    result["symbol_name"] == "authenticate_user"
                    for result in results
                ))
        finally:
            client.delete_collection(test_collection.name)

    def test_rejects_empty_repository_or_query(self):
        with self.assertRaises(ValueError):
            search_repository(repository_id="   ", query="login")

        with self.assertRaises(ValueError):
            search_repository(repository_id="repo-1", query="   ")

    def test_lists_repository_metadata(self):
        client = TestClient(app)

        response = client.get('/api/repositories')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('repositories', payload)
        self.assertGreaterEqual(payload['count'], 1)

        repo_id = payload['repositories'][0]['repository_id']
        detail = client.get(f'/api/repositories/{repo_id}')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['repository_id'], repo_id)

        missing = client.get('/api/repositories/does-not-exist')
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()