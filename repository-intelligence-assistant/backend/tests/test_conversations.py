import json
import sqlite3
import subprocess
import sys
import unittest
import uuid
from contextlib import closing
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

from app.services.conversation_service import DB_PATH, add_exchange
from app.services.llm_service import LLMServiceError
from main import app


class TestConversationApi(unittest.TestCase):
    def test_exchange_enforces_conversation_foreign_key(self):
        with self.assertRaises(sqlite3.IntegrityError):
            add_exchange(
                f"missing-conversation-{uuid.uuid4().hex}",
                "A question",
                "An answer",
            )

    def test_provider_failure_returns_structured_error_without_persisting_failed_turn(self):
        repository_id = f"conversation-error-test-{uuid.uuid4().hex}"
        client = TestClient(app)
        created = client.post(
            f"/api/repositories/{repository_id}/conversations",
            json={"title": "Failed request test"},
        )
        conversation_id = created.json()["id"]

        try:
            with patch(
                "app.api.conversations.search_repository",
                return_value=[
                    {
                        "file_path": "auth.py",
                        "chunk_type": "function",
                        "symbol_name": "authenticate_user",
                        "start_line": 1,
                        "end_line": 2,
                    }
                ],
            ), patch(
                "app.api.conversations.generate_repository_answer",
                side_effect=LLMServiceError(
                    "groq_authentication_failed",
                    "Groq rejected the configured API key.",
                ),
            ):
                response = client.post(
                    f"/api/repositories/{repository_id}/conversations/{conversation_id}/messages",
                    json={"message": "Explain authenticate_user"},
                )

            self.assertEqual(response.status_code, 502)
            self.assertEqual(
                response.json()["detail"]["code"],
                "groq_authentication_failed",
            )
            history = client.get(
                f"/api/repositories/{repository_id}/conversations/{conversation_id}"
            )
            self.assertEqual(history.status_code, 200)
            self.assertEqual(history.json()["messages"], [])
        finally:
            with closing(sqlite3.connect(DB_PATH)) as connection:
                connection.execute(
                    "DELETE FROM messages WHERE conversation_id = ?",
                    (conversation_id,),
                )
                connection.execute(
                    "DELETE FROM conversations WHERE id = ?",
                    (conversation_id,),
                )
                connection.commit()

    def test_conversation_lifecycle_is_repository_scoped_and_persistent(self):
        repository_id = f"conversation-api-test-{uuid.uuid4().hex}"
        client = TestClient(app)
        conversation_id = None
        retrieved_chunks = [
            {
                "file_path": "auth.py",
                "chunk_type": "function",
                "symbol_name": "authenticate_user",
                "start_line": 4,
                "end_line": 8,
                "distance": 0.12,
            }
        ]

        try:
            created = client.post(
                f"/api/repositories/{repository_id}/conversations",
                json={"title": "Authentication questions"},
            )
            self.assertEqual(created.status_code, 200)
            conversation_id = created.json()["id"]
            self.assertEqual(created.json()["repository_id"], repository_id)

            listed = client.get(f"/api/repositories/{repository_id}/conversations")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()["conversations"][0]["id"], conversation_id)

            with patch("app.api.conversations.search_repository", return_value=retrieved_chunks), patch(
                "app.api.conversations.generate_repository_answer",
                return_value="It checks the supplied credentials.",
            ) as generate_answer:
                first = client.post(
                    f"/api/repositories/{repository_id}/conversations/{conversation_id}/messages",
                    json={"message": "Explain authenticate_user"},
                )
                self.assertEqual(first.status_code, 200)

                followup = client.post(
                    f"/api/repositories/{repository_id}/conversations/{conversation_id}/messages",
                    json={"message": "What does it do?"},
                )
                self.assertEqual(followup.status_code, 200)
                self.assertEqual(
                    followup.json()["resolved_question"],
                    "Explain authenticate_user What does it do?",
                )
                self.assertEqual(
                    generate_answer.call_args.kwargs["question"],
                    "Explain authenticate_user What does it do?",
                )
                self.assertEqual(
                    followup.json()["assistant_message"]["metadata"]["sources"][0]["file_path"],
                    "auth.py",
                )

            persisted = client.get(
                f"/api/repositories/{repository_id}/conversations/{conversation_id}"
            )
            self.assertEqual(persisted.status_code, 200)
            self.assertEqual(len(persisted.json()["messages"]), 4)
            self.assertEqual(persisted.json()["messages"][-1]["role"], "assistant")

            script = (
                "import json, sys; "
                "from app.services.conversation_service import get_conversation; "
                "record = get_conversation(sys.argv[1], sys.argv[2]); "
                "print(json.dumps(record))"
            )
            restarted_process = subprocess.run(
                [sys.executable, "-c", script, repository_id, conversation_id],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                check=True,
                text=True,
            )
            after_restart = json.loads(restarted_process.stdout)
            self.assertEqual(len(after_restart["messages"]), 4)
            self.assertEqual(after_restart["messages"][-1]["role"], "assistant")

            wrong_repository = client.get(
                f"/api/repositories/another-repository/conversations/{conversation_id}"
            )
            self.assertEqual(wrong_repository.status_code, 404)
        finally:
            if conversation_id:
                with closing(sqlite3.connect(DB_PATH)) as connection:
                    connection.execute(
                        "DELETE FROM messages WHERE conversation_id = ?",
                        (conversation_id,),
                    )
                    connection.execute(
                        "DELETE FROM conversations WHERE id = ?",
                        (conversation_id,),
                    )
                    connection.commit()


if __name__ == "__main__":
    unittest.main()
