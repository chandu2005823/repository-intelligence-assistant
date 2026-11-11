import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import MagicMock, patch

import chromadb

from app.services import vector_store
from app.services.code_chunker import chunk_repository
from app.services.llm_service import build_repository_context


class TestRetrievalRegressions(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository_root = Path(self.temporary_directory.name)
        self.repository_id = "retrieval-fixture"

        files = {
            "frontend/src/main.tsx": (
                "import { createRoot } from 'react-dom/client';\n"
                "import App from './App';\n"
                "createRoot(document.getElementById('root')!).render(<App />);\n"
            ),
            "frontend/src/App.tsx": (
                "export default function App() {\n"
                "  return <main>Repository workspace</main>;\n"
                "}\n"
            ),
            "frontend/package.json": json.dumps(
                {"scripts": {"dev": "vite", "build": "vite build"}},
                indent=2,
            ),
            "backend/api.py": (
                "from fastapi import FastAPI\n"
                "from backend.routes import query, projects\n"
                "\n"
                "app = FastAPI()\n"
                "app.include_router(query.router)\n"
                "app.include_router(projects.router)\n"
            ),
            "rag/answer.py": (
                "def generate_repository_answer(question, chunks):\n"
                "    return f'{question}: {len(chunks)} evidence chunks'\n"
            ),
            "other/unrelated.py": (
                "def normalize_value(value):\n"
                "    return str(value).strip()\n"
            ),
        }
        for relative_path, content in files.items():
            path = self.repository_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        self.chunks = chunk_repository(self.repository_root, self.repository_id)["chunks"]
        self.client = chromadb.EphemeralClient()
        self.collection = self.client.create_collection(
            name=f"retrieval_fixture_{uuid4().hex}",
            metadata={"hnsw:space": "cosine"},
        )
        self.original_collection = vector_store.collection
        vector_store.collection = self.collection
        vector_store.index_chunks(self.repository_id, self.chunks)

    def tearDown(self):
        vector_store.collection = self.original_collection
        self.client.delete_collection(self.collection.name)
        self.temporary_directory.cleanup()

    def test_architecture_queries_retrieve_expected_source_files(self):
        evaluations = [
            (
                "Find the file that calls ReactDOM.createRoot or createRoot.",
                "frontend/src/main.tsx",
            ),
            (
                "Find where the main App component is imported and rendered.",
                "frontend/src/main.tsx",
            ),
            (
                "Find the frontend package.json and its scripts.",
                "frontend/package.json",
            ),
            (
                "Find the FastAPI application initialization.",
                "backend/api.py",
            ),
            (
                "Find where API routes are registered.",
                "backend/api.py",
            ),
            (
                "Find the function responsible for generating repository answers.",
                "rag/answer.py",
            ),
        ]

        for query, expected_path in evaluations:
            with self.subTest(query=query):
                results = vector_store.search_repository(
                    self.repository_id,
                    query,
                    top_k=5,
                )
                self.assertIn(expected_path, {result["file_path"] for result in results})

    def test_search_is_repository_scoped_and_lines_are_original(self):
        results = vector_store.search_repository(
            self.repository_id,
            "createRoot render App",
            top_k=5,
        )
        entry = next(result for result in results if result["file_path"] == "frontend/src/main.tsx")
        self.assertEqual((entry["start_line"], entry["end_line"]), (1, 3))

        other_repository = "different-repository"
        scoped_results = vector_store.search_repository(
            other_repository,
            "createRoot",
            top_k=5,
        )
        self.assertEqual(scoped_results, [])

    def test_missing_repository_returns_no_results(self):
        self.assertEqual(
            vector_store.search_repository("missing-repository", "createRoot", top_k=5),
            [],
        )

    def test_fusion_deduplicates_chunks_across_retrievers(self):
        duplicate = {
            "file_path": "frontend/src/main.tsx",
            "start_line": 1,
            "end_line": 3,
            "chunk_type": "source",
            "symbol_name": None,
            "content": "createRoot(...);",
            "distance": 0.1,
        }
        results = vector_store._reciprocal_rank_fusion(
            [[duplicate], [duplicate.copy()]],
            top_k=5,
        )

        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["hybrid_score"], 2 / (vector_store.RRF_K + 1))

    def test_context_includes_source_path_and_line_evidence_once(self):
        entry = next(chunk for chunk in self.chunks if chunk["file_path"] == "frontend/src/main.tsx")
        context = build_repository_context([entry, entry.copy()])

        self.assertIn("[SOURCE 1]", context)
        self.assertIn("File: frontend/src/main.tsx", context)
        self.assertIn(f"Lines: {entry['start_line']}-{entry['end_line']}", context)
        self.assertIn("createRoot", context)
        self.assertEqual(context.count("File: frontend/src/main.tsx"), 1)

    def test_generation_passes_constructed_sources_and_grounding_instructions(self):
        entry = next(chunk for chunk in self.chunks if chunk["file_path"] == "frontend/src/main.tsx")
        groq_client = MagicMock()
        groq_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="The entry point renders App [SOURCE 1]."))
        ]

        with patch.dict("os.environ", {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "fixture-key"}), patch(
            "app.services.llm_service.Groq",
            return_value=groq_client,
        ):
            from app.services.llm_service import generate_repository_answer

            generated = generate_repository_answer(
                "Where is the React entry point?",
                [entry],
            )

        self.assertIn("[SOURCE 1]", generated)
        request = groq_client.chat.completions.create.call_args.kwargs
        self.assertIn("frontend/src/main.tsx", request["messages"][1]["content"])
        self.assertIn("Do not invent file paths", request["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
