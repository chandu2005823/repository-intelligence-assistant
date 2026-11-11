import tempfile
import unittest
from pathlib import Path

from app.services.code_analyzer import analyze_python_file
from app.services.repository_service import analyze_repository


class TestCodeAnalyzer(unittest.TestCase):

    def test_extracts_functions_classes_and_imports(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            python_file = root / "sample.py"
            python_file.write_text(
                "import os\n"
                "from pathlib import Path\n\n"
                "class Repository:\n"
                "    pass\n\n"
                "def analyze():\n"
                "    return True\n",
                encoding="utf-8",
            )

            result = analyze_python_file(python_file, root)

            self.assertEqual(result["path"], "sample.py")
            self.assertEqual(len(result["functions"]), 1)
            self.assertEqual(result["functions"][0]["name"], "analyze")
            self.assertEqual(len(result["classes"]), 1)
            self.assertEqual(result["classes"][0]["name"], "Repository")
            self.assertIn("os", result["imports"])
            self.assertIsNone(result["syntax_error"])

    def test_reports_syntax_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            python_file = root / "invalid.py"
            python_file.write_text(
                "def broken(:\n    pass\n",
                encoding="utf-8",
            )

            result = analyze_python_file(python_file, root)

            self.assertIsNotNone(result["syntax_error"])
            self.assertEqual(result["syntax_error"]["line"], 1)

    def test_skips_pycache_when_analyzing_repository(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cache_dir = root / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "cached.py").write_text("def cached():\n    pass\n", encoding="utf-8")

            python_file = root / "main.py"
            python_file.write_text("def main():\n    return 42\n", encoding="utf-8")

            result = analyze_repository(root)

            self.assertEqual(result["file_count"], 1)
            self.assertEqual(result["files"][0]["name"], "main.py")


if __name__ == "__main__":
    unittest.main()