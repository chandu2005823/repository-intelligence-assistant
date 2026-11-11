import tempfile
import unittest
from pathlib import Path

from app.services.code_chunker import (
    chunk_repository,
    chunk_python_file,
    chunk_python_repository,
)


class TestCodeChunker(unittest.TestCase):

    def test_chunks_python_functions_and_module_code(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            python_file = root / "main.py"

            python_file.write_text(
                "import os\n"
                "\n"
                "def authenticate_user(username):\n"
                "    return username is not None\n"
                "\n"
                "def logout_user():\n"
                "    return True\n",
                encoding="utf-8",
            )

            chunks = chunk_python_file(
                file_path=python_file,
                repository_root=root,
                repository_id="test-repository",
            )

            function_names = {
                chunk["symbol_name"]
                for chunk in chunks
                if chunk["chunk_type"] == "function"
            }

            self.assertIn("authenticate_user", function_names)
            self.assertIn("logout_user", function_names)

            self.assertTrue(
                any(
                    chunk["chunk_type"] == "module"
                    and "import os" in chunk["content"]
                    for chunk in chunks
                )
            )

            for chunk in chunks:
                self.assertEqual(
                    chunk["repository_id"],
                    "test-repository",
                )
                self.assertGreaterEqual(chunk["start_line"], 1)
                self.assertGreaterEqual(
                    chunk["end_line"],
                    chunk["start_line"],
                )

    def test_chunks_repository(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            (root / "main.py").write_text(
                "def main():\n"
                "    return 'hello'\n",
                encoding="utf-8",
            )

            result = chunk_python_repository(
                repository_root=root,
                repository_id="test-repository",
            )

            self.assertEqual(result["python_files_processed"], 1)
            self.assertGreater(result["chunk_count"], 0)

    def test_chunks_supported_frontend_and_manifest_files_with_source_lines(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "frontend" / "src").mkdir(parents=True)
            (root / "frontend" / "src" / "main.tsx").write_text(
                "import { createRoot } from 'react-dom/client';\n"
                "import App from './App';\n"
                "createRoot(document.getElementById('root')!).render(<App />);\n",
                encoding="utf-8",
            )
            (root / "frontend" / "package.json").write_text(
                '{\n  "scripts": {\n    "build": "vite build"\n  }\n}\n',
                encoding="utf-8",
            )
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.ts").write_text("createRoot(null);\n", encoding="utf-8")
            (root / ".env").write_text("SECRET=value\n", encoding="utf-8")

            result = chunk_repository(root, "fixture-repository")

            entry_chunk = next(
                chunk for chunk in result["chunks"]
                if chunk["file_path"] == "frontend/src/main.tsx"
            )
            manifest_chunk = next(
                chunk for chunk in result["chunks"]
                if chunk["file_path"] == "frontend/package.json"
            )
            indexed_paths = {chunk["file_path"] for chunk in result["chunks"]}

            self.assertEqual(entry_chunk["repository_id"], "fixture-repository")
            self.assertEqual((entry_chunk["start_line"], entry_chunk["end_line"]), (1, 3))
            self.assertIn("createRoot", entry_chunk["content"])
            self.assertIn('"build": "vite build"', manifest_chunk["content"])
            self.assertEqual((manifest_chunk["start_line"], manifest_chunk["end_line"]), (1, 5))
            self.assertNotIn(".venv/ignored.ts", indexed_paths)
            self.assertNotIn(".env", indexed_paths)


if __name__ == "__main__":
    unittest.main()