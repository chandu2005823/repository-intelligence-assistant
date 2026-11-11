import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import repository_analysis, repositories as repositories_api
from app.services import dependency_service
from app.services.code_intelligence_service import analyze_code
from app.services.code_review_service import analyze_code_review
from app.services.dependency_service import (
    analyze_dependencies,
    get_persisted_dependencies,
)
from main import app


class TestRepositoryAnalysis(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "fixture"
        self.root.mkdir()
        (self.root / "pkg").mkdir()
        (self.root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "pkg" / "base.py").write_text(
            "def target():\n"
            "    return True\n",
            encoding="utf-8",
        )
        (self.root / "pkg" / "caller.py").write_text(
            "from .base import target\n"
            "\n"
            "def start():\n"
            "    return target()\n",
            encoding="utf-8",
        )
        (self.root / "src").mkdir()
        (self.root / "src" / "helper.ts").write_text(
            "export function helper() {\n  return true;\n}\n",
            encoding="utf-8",
        )
        (self.root / "src" / "main.ts").write_text(
            "import { helper } from './helper';\n"
            "export const run = () => helper();\n",
            encoding="utf-8",
        )
        (self.root / "src" / "view.tsx").write_text(
            "import {\n"
            "  helper as importedHelper,\n"
            "} from './helper';\n"
            "export const runView = () => importedHelper();\n",
            encoding="utf-8",
        )
        (self.root / "src" / "widget.jsx").write_text(
            "export function Widget() { return null; }\n",
            encoding="utf-8",
        )
        (self.root / "src" / "component.jsx").write_text(
            "import { Widget } from './widget';\n"
            "export function Component() { return <Widget />; }\n",
            encoding="utf-8",
        )
        (self.root / "src" / "external.js").write_text(
            "import client from 'third-party-client';\n",
            encoding="utf-8",
        )
        (self.root / "src" / "worker.js").write_text(
            "class Worker {\n"
            "  start() {\n"
            "    this.finish();\n"
            "  }\n"
            "  finish() {\n"
            "    return true;\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        self.database_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.database_directory.name) / "analysis.db"
        self.database_patch = patch.object(dependency_service, "ANALYSIS_DATABASE", self.database)
        self.database_patch.start()

    def tearDown(self):
        self.database_patch.stop()
        self.database_directory.cleanup()
        self.temporary_directory.cleanup()

    def test_dependency_extraction_resolves_python_and_typescript_and_persists(self):
        result = analyze_dependencies("fixture", self.root)
        edges = {(edge["source"], edge["target"]) for edge in result["edges"]}

        self.assertIn(("pkg/caller.py", "pkg/base.py"), edges)
        self.assertIn(("src/main.ts", "src/helper.ts"), edges)
        self.assertIn(("src/view.tsx", "src/helper.ts"), edges)
        self.assertIn(("src/component.jsx", "src/widget.jsx"), edges)
        self.assertTrue(any(
            entry["module"] == "third-party-client"
            for entry in result["unresolved"]
        ))
        persisted = get_persisted_dependencies("fixture")
        self.assertEqual(persisted["edges"], result["edges"])

    def test_code_intelligence_only_reports_resolved_calls_and_file_impact(self):
        result = analyze_code("fixture", self.root, query="target")
        self.assertTrue(any(
            call["caller"] == "start"
            and call["callee"] == "target"
            and call["resolved"]
            for call in result["calls"]
        ))
        self.assertIn("start", result["impact"]["functions"])

        impact = analyze_code("fixture", self.root, file_path="pkg/base.py")
        self.assertIn("pkg/caller.py", impact["impact"]["files"])

    def test_code_intelligence_resolves_a_javascript_imported_function(self):
        result = analyze_code("fixture", self.root, query="helper")
        self.assertTrue(any(
            call["caller"] == "run"
            and call["callee"] == "helper"
            and call["resolved"]
            for call in result["calls"]
        ))
        aliased = analyze_code("fixture", self.root, query="runView")
        self.assertTrue(any(
            call["caller"] == "runView"
            and call["callee"] == "helper"
            and call["resolved"]
            for call in aliased["calls"]
        ))
        methods = analyze_code("fixture", self.root, query="Worker")
        self.assertTrue(any(
            call["caller"] == "Worker.start"
            and call["callee"] == "Worker.finish"
            and call["resolved"]
            for call in methods["calls"]
        ))

    def test_review_reports_potential_findings_with_exact_source_lines(self):
        reviewed = self.root / "review.py"
        reviewed.write_text(
            "import subprocess\n"
            "def run(command):\n"
            "    subprocess.run(command, shell=True)\n"
            "try:\n"
            "    run('echo ok')\n"
            "except Exception:\n"
            "    pass\n",
            encoding="utf-8",
        )
        findings = analyze_code_review(self.root)
        shell_finding = next(item for item in findings if item["title"] == "Subprocess uses a shell")
        broad_finding = next(item for item in findings if item["title"] == "Broad exception is silently ignored")
        self.assertEqual((shell_finding["file_path"], shell_finding["start_line"]), ("review.py", 3))
        self.assertEqual(broad_finding["start_line"], 6)
        self.assertEqual(shell_finding["status"], "Potential")

    def test_dependency_and_review_api_preserve_repository_scoping(self):
        with tempfile.TemporaryDirectory() as storage_directory:
            repository_id = "api-fixture"
            repository_path = Path(storage_directory) / repository_id
            repository_path.mkdir()
            (repository_path / "main.py").write_text(
                "def active():\n    return eval('1')\n",
                encoding="utf-8",
            )
            with patch.object(repository_analysis, "STORAGE_ROOT", Path(storage_directory)), patch.dict(
                os.environ,
                {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": ""},
            ):
                client = TestClient(app)
                dependencies = client.get(f"/api/repositories/{repository_id}/dependencies")
                intelligence = client.get(
                    f"/api/repositories/{repository_id}/intelligence?query=active"
                )
                review = client.post(f"/api/repositories/{repository_id}/review", json={})
                missing = client.get("/api/repositories/missing/dependencies")

            self.assertEqual(dependencies.status_code, 200, dependencies.text)
            self.assertIn("main.py", {node["path"] for node in dependencies.json()["nodes"]})
            self.assertEqual(intelligence.status_code, 200, intelligence.text)
            self.assertEqual(intelligence.json()["definitions"][0]["name"], "active")
            self.assertEqual(review.status_code, 200, review.text)
            self.assertEqual(review.json()["ai_status"], "missing_api_key")
            self.assertTrue(review.json()["findings"])
            self.assertEqual(missing.status_code, 404)

    def test_review_uses_configured_groq_provider(self):
        with tempfile.TemporaryDirectory() as storage_directory:
            repository_id = "groq-review-fixture"
            repository_path = Path(storage_directory) / repository_id
            repository_path.mkdir()
            (repository_path / "main.py").write_text(
                "def active():\n    return eval('1')\n",
                encoding="utf-8",
            )
            with patch.object(repository_analysis, "STORAGE_ROOT", Path(storage_directory)), patch.dict(
                os.environ,
                {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key"},
            ), patch.object(
                repository_analysis,
                "generate_repository_answer",
                return_value="Grounded review explanation.",
            ) as generate_answer:
                client = TestClient(app)
                review = client.post(f"/api/repositories/{repository_id}/review", json={})

            self.assertEqual(review.status_code, 200, review.text)
            self.assertEqual(review.json()["ai_status"], "available")
            self.assertEqual(review.json()["ai_explanation"], "Grounded review explanation.")
            generate_answer.assert_called_once()

    def test_upload_enforces_one_gibibyte_zip_limit(self):
        self.assertEqual(repositories_api.MAX_UPLOAD_SIZE, 1024 ** 3)

        with tempfile.TemporaryDirectory() as storage_directory:
            with patch.object(repositories_api, "STORAGE_ROOT", Path(storage_directory)), patch.object(
                repositories_api,
                "MAX_UPLOAD_SIZE",
                3,
            ):
                client = TestClient(app)
                response = client.post(
                    "/api/repositories/upload",
                    files={"file": ("repository.zip", b"four", "application/zip")},
                )

        self.assertEqual(response.status_code, 413, response.text)
        self.assertIn("1 GB upload limit", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
