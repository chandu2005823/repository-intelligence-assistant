import io
import shutil
import unittest
import zipfile
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.repositories import STORAGE_ROOT
from app.services.llm_service import LLMServiceError
from app.services.vector_store import collection
from main import app


class TestApplicationWorkflow(unittest.TestCase):
    def test_upload_listing_search_and_repository_qa(self):
        client = TestClient(app)
        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(archive_buffer, "w") as archive:
            archive.writestr(
                "sample_repo/auth.py",
                "def authenticate_user(username, password):\n"
                "    return verify_credentials(username, password)\n",
            )

        repository_id = None
        try:
            upload = client.post(
                "/api/repositories/upload",
                files={
                    "file": (
                        "sample-repository.zip",
                        archive_buffer.getvalue(),
                        "application/zip",
                    )
                },
            )
            self.assertEqual(upload.status_code, 200, upload.text)
            upload_payload = upload.json()
            repository_id = upload_payload["repository_id"]
            self.assertGreater(upload_payload["indexing"]["indexed_chunks"], 0)

            listing = client.get("/api/repositories")
            self.assertEqual(listing.status_code, 200)
            self.assertTrue(
                any(
                    item["repository_id"] == repository_id
                    for item in listing.json()["repositories"]
                )
            )

            search = client.post(
                "/api/repositories/search",
                json={
                    "repository_id": repository_id,
                    "query": "authenticate_user credentials",
                    "top_k": 5,
                },
            )
            self.assertEqual(search.status_code, 200, search.text)
            self.assertGreater(search.json()["result_count"], 0)

            with patch(
                "app.api.repository_qa.generate_repository_answer",
                return_value="The function checks the credentials.",
            ):
                answer = client.post(
                    "/api/repositories/ask",
                    json={
                        "repository_id": repository_id,
                        "question": "What does authenticate_user do?",
                    },
                )
            self.assertEqual(answer.status_code, 200, answer.text)
            self.assertEqual(answer.json()["answer"], "The function checks the credentials.")
            self.assertGreater(answer.json()["source_count"], 0)

            with patch(
                "app.api.repository_qa.generate_repository_answer",
                side_effect=LLMServiceError(
                    "groq_authentication_failed",
                    "Groq rejected the configured API key.",
                ),
            ):
                failed_answer = client.post(
                    "/api/repositories/ask",
                    json={
                        "repository_id": repository_id,
                        "question": "What does authenticate_user do?",
                    },
                )
            self.assertEqual(failed_answer.status_code, 502)
            self.assertEqual(
                failed_answer.json()["detail"]["code"],
                "groq_authentication_failed",
            )
        finally:
            if repository_id:
                collection.delete(where={"repository_id": repository_id})
                shutil.rmtree(STORAGE_ROOT / repository_id, ignore_errors=False)


if __name__ == "__main__":
    unittest.main()
