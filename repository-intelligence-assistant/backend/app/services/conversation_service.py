import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_ROOT / "data"
DB_PATH = DATA_DIR / "conversations.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_repository ON conversations(repository_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at)"
        )


def create_conversation(repository_id: str, title: str | None = None) -> dict:
    if not repository_id or not repository_id.strip():
        raise ValueError("Repository ID is required.")

    normalized_title = (title or "New conversation").strip() or "New conversation"
    conversation_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO conversations (id, repository_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, repository_id.strip(), normalized_title, timestamp, timestamp),
        )

    return {
        "id": conversation_id,
        "repository_id": repository_id.strip(),
        "title": normalized_title,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def list_conversations(repository_id: str) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, repository_id, title, created_at, updated_at
            FROM conversations
            WHERE repository_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (repository_id.strip(),),
        ).fetchall()

    return [dict(row) for row in rows]


def get_conversation(repository_id: str, conversation_id: str) -> dict | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, repository_id, title, created_at, updated_at
            FROM conversations
            WHERE repository_id = ? AND id = ?
            """,
            (repository_id.strip(), conversation_id),
        ).fetchone()

    if row is None:
        return None

    messages = list_messages(conversation_id)
    record = dict(row)
    record["messages"] = messages
    return record


def add_message(conversation_id: str, role: str, content: str, metadata: dict | None = None) -> dict:
    if not conversation_id:
        raise ValueError("Conversation ID is required.")

    normalized_role = role.strip().lower()
    if normalized_role not in {"user", "assistant"}:
        raise ValueError("Role must be user or assistant.")

    text = (content or "").strip()
    if not text:
        raise ValueError("Message content is required.")

    message_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    payload = json.dumps(metadata or {}, sort_keys=True)

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, conversation_id, normalized_role, text, timestamp, payload),
        )
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (timestamp, conversation_id),
        )

    return {
        "id": message_id,
        "conversation_id": conversation_id,
        "role": normalized_role,
        "content": text,
        "created_at": timestamp,
        "metadata": metadata or {},
    }


def add_exchange(
    conversation_id: str,
    user_content: str,
    assistant_content: str,
    assistant_metadata: dict | None = None,
) -> tuple[dict, dict]:
    if not conversation_id:
        raise ValueError("Conversation ID is required.")

    user_text = (user_content or "").strip()
    assistant_text = (assistant_content or "").strip()
    if not user_text or not assistant_text:
        raise ValueError("Both exchange messages are required.")

    user_message_id = uuid.uuid4().hex
    assistant_message_id = uuid.uuid4().hex
    user_timestamp = datetime.now(timezone.utc)
    assistant_timestamp = max(
        datetime.now(timezone.utc),
        user_timestamp + timedelta(microseconds=1),
    )
    user_created_at = user_timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z")
    assistant_created_at = assistant_timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z")
    assistant_payload = json.dumps(assistant_metadata or {}, sort_keys=True)

    with _connect() as connection:
        connection.executemany(
            """
            INSERT INTO messages (id, conversation_id, role, content, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    user_message_id,
                    conversation_id,
                    "user",
                    user_text,
                    user_created_at,
                    "{}",
                ),
                (
                    assistant_message_id,
                    conversation_id,
                    "assistant",
                    assistant_text,
                    assistant_created_at,
                    assistant_payload,
                ),
            ],
        )
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (assistant_created_at, conversation_id),
        )

    return (
        {
            "id": user_message_id,
            "conversation_id": conversation_id,
            "role": "user",
            "content": user_text,
            "created_at": user_created_at,
            "metadata": {},
        },
        {
            "id": assistant_message_id,
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": assistant_text,
            "created_at": assistant_created_at,
            "metadata": assistant_metadata or {},
        },
    )


def list_messages(conversation_id: str, limit: int | None = None) -> list[dict]:
    with _connect() as connection:
        if limit is None:
            rows = connection.execute(
                """
                SELECT id, conversation_id, role, content, created_at, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (conversation_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id, conversation_id, role, content, created_at, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()

    results = []
    for row in rows:
        record = dict(row)
        record["metadata"] = json.loads(record["metadata"] or "{}")
        results.append(record)

    if limit is not None and results:
        results.reverse()
    return results


def conversation_exists(conversation_id: str) -> bool:
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
    return row is not None


init_db()
