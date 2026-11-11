import ast
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from app.services.repository_service import IGNORED_DIRECTORIES, IGNORED_FILES

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DATABASE = BACKEND_ROOT / "data" / "repository_analysis.db"
SOURCE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}
IMPORT_PATTERN = re.compile(
    r"""(?mx)^\s*(?:import\s+(?:[^'";]*?\s+from\s+)?|"""
    r"""export\s+[^'";]*?\s+from\s+)['"]([^'"]+)['"]"""
)
REQUIRE_PATTERN = re.compile(
    r"""(?m)^\s*(?:(?:const|let|var)\s+[^=;]+?=\s*)?"""
    r"""require\(\s*['"]([^'"]+)['"]\s*\)"""
)


def _initialize_database() -> None:
    ANALYSIS_DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(ANALYSIS_DATABASE)) as database:
        with database:
            database.execute(
                """
                CREATE TABLE IF NOT EXISTS dependency_edges (
                    repository_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    module TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    line INTEGER NOT NULL,
                    PRIMARY KEY (repository_id, source, target, module, kind, line)
                )
                """
            )
            database.execute(
                """
                CREATE TABLE IF NOT EXISTS unresolved_dependencies (
                    repository_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    module TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    line INTEGER NOT NULL,
                    PRIMARY KEY (repository_id, file_path, module, kind, line)
                )
                """
            )


def list_source_files(repository_root: Path) -> list[Path]:
    files = []
    for path in repository_root.rglob("*"):
        relative = path.relative_to(repository_root)
        if (
            path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in SOURCE_EXTENSIONS
            and path.name not in IGNORED_FILES
            and not path.name.startswith(".env.")
            and not any(part in IGNORED_DIRECTORIES for part in relative.parts[:-1])
        ):
            files.append(path)
    return sorted(files, key=lambda item: item.as_posix().lower())


def _resolve_module(
    repository_root: Path,
    importer: Path,
    module: str,
    python_level: int = 0,
) -> Path | None:
    if python_level or (module.startswith(".") and importer.suffix.lower() == ".py"):
        parts = importer.relative_to(repository_root).with_suffix("").parts
        base_parts = list(parts[:-1])
        if python_level:
            base_parts = base_parts[:max(0, len(base_parts) - python_level + 1)]
        if module:
            base_parts.extend(module.lstrip(".").split("."))
        base = repository_root.joinpath(*base_parts)
        candidates = [base.with_suffix(".py"), base / "__init__.py"]
    elif module.startswith("."):
        base = (importer.parent / module).resolve()
        try:
            base.relative_to(repository_root.resolve())
        except ValueError:
            return None
        candidates = [base] if base.suffix.lower() in SOURCE_EXTENSIONS else [
            base.with_suffix(ext) for ext in (".ts", ".tsx", ".js", ".jsx", ".py")
        ]
        candidates.extend(
            base / f"index{ext}" for ext in (".ts", ".tsx", ".js", ".jsx")
        )
    else:
        aliased = module.startswith(("@/", "~/"))
        normalized = module[2:] if aliased else module.replace(".", "/").strip("/")
        if not normalized:
            return None
        candidates = []
        # Try conventional root-relative imports and common src/app layouts.
        prefixes = (Path("src"), Path()) if aliased else (Path(), Path("src"), Path("app"))
        for prefix in prefixes:
            base = repository_root / prefix / normalized
            candidates.extend([base] if base.suffix.lower() in SOURCE_EXTENSIONS else [
                base.with_suffix(ext) for ext in (".py", ".js", ".jsx", ".ts", ".tsx")
            ])
            candidates.extend(base / f"index{ext}" for ext in (".js", ".jsx", ".ts", ".tsx"))
            candidates.append(base / "__init__.py")

    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate

    return None


def _extract_python_imports(
    source: str,
    file_path: Path,
    repository_root: Path,
) -> tuple[list[dict], list[dict]]:
    try:
        tree = ast.parse(source, filename=file_path.as_posix())
    except SyntaxError:
        return [], []

    resolved = []
    unresolved = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports = [(alias.name, 0) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports = [(node.module or "", node.level)]
            if node.module:
                # "from pkg import local_module" may identify a source file.
                imports.extend(
                    (f"{node.module}.{alias.name}", node.level)
                    for alias in node.names
                    if alias.name != "*"
                )
            elif node.level:
                imports.extend(
                    (alias.name, node.level)
                    for alias in node.names
                    if alias.name != "*"
                )
        else:
            continue

        for module, level in imports:
            target = _resolve_module(repository_root, file_path, module, level)
            record = {
                "module": module or ("." * level),
                "kind": "import",
                "line": node.lineno,
            }
            if target:
                resolved.append((target, record))
            else:
                unresolved.append(record)
    return resolved, unresolved


def _extract_javascript_imports(
    source: str,
    file_path: Path,
    repository_root: Path,
) -> tuple[list[dict], list[dict]]:
    patterns = [IMPORT_PATTERN, REQUIRE_PATTERN]
    matches = []
    for pattern in patterns:
        for match in pattern.finditer(source):
            module = match.group(1)
            line = source.count("\n", 0, match.start()) + 1
            kind = "export" if source[match.start():match.end()].lstrip().startswith("export") else "import"
            matches.append((line, module, kind))

    resolved = []
    unresolved = []
    seen = set()
    for line, module, kind in sorted(matches):
        key = (line, module, kind)
        if key in seen:
            continue
        seen.add(key)
        target = _resolve_module(repository_root, file_path, module)
        record = {"module": module, "kind": kind, "line": line}
        if target:
            resolved.append((target, record))
        else:
            unresolved.append(record)
    return resolved, unresolved


def analyze_dependencies(repository_id: str, repository_root: Path) -> dict:
    files = list_source_files(repository_root)
    paths = {path: path.relative_to(repository_root).as_posix() for path in files}
    edges = []
    unresolved = []
    for source_path in files:
        try:
            source = source_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        if source_path.suffix.lower() == ".py":
            imports, missing = _extract_python_imports(source, source_path, repository_root)
        else:
            imports, missing = _extract_javascript_imports(source, source_path, repository_root)
        source_name = paths[source_path]
        for target_path, record in imports:
            target_name = paths.get(target_path)
            if target_name is None:
                continue
            edges.append({
                "source": source_name,
                "target": target_name,
                "module": record["module"],
                "kind": record["kind"],
                "line": record["line"],
            })
        unresolved.extend({
            "file_path": source_name,
            **record,
        } for record in missing)

    edges.sort(key=lambda edge: (edge["source"], edge["line"], edge["target"]))
    unresolved.sort(key=lambda item: (item["file_path"], item["line"], item["module"]))
    nodes = []
    for path in files:
        relative = paths[path]
        nodes.append({
            "id": relative,
            "path": relative,
            "label": path.name,
            "language": path.suffix.lower().lstrip("."),
        })

    _initialize_database()
    with closing(sqlite3.connect(ANALYSIS_DATABASE)) as database:
        with database:
            database.execute("BEGIN")
            database.execute(
                "DELETE FROM dependency_edges WHERE repository_id = ?",
                (repository_id,),
            )
            database.execute(
                "DELETE FROM unresolved_dependencies WHERE repository_id = ?",
                (repository_id,),
            )
            database.executemany(
                """
                INSERT INTO dependency_edges
                (repository_id, source, target, module, kind, line)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        repository_id,
                        edge["source"],
                        edge["target"],
                        edge["module"],
                        edge["kind"],
                        edge["line"],
                    )
                    for edge in edges
                ],
            )
            database.executemany(
                """
                INSERT INTO unresolved_dependencies
                (repository_id, file_path, module, kind, line)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        repository_id,
                        item["file_path"],
                        item["module"],
                        item["kind"],
                        item["line"],
                    )
                    for item in unresolved
                ],
            )

    return {
        "repository_id": repository_id,
        "nodes": nodes,
        "edges": edges,
        "unresolved": unresolved,
    }


def get_persisted_dependencies(repository_id: str) -> dict:
    _initialize_database()
    with closing(sqlite3.connect(ANALYSIS_DATABASE)) as database:
        edges = [
            {
                "source": row[0],
                "target": row[1],
                "module": row[2],
                "kind": row[3],
                "line": row[4],
            }
            for row in database.execute(
                """
                SELECT source, target, module, kind, line
                FROM dependency_edges WHERE repository_id = ?
                ORDER BY source, line
                """,
                (repository_id,),
            )
        ]
        unresolved = [
            {
                "file_path": row[0],
                "module": row[1],
                "kind": row[2],
                "line": row[3],
            }
            for row in database.execute(
                """
                SELECT file_path, module, kind, line
                FROM unresolved_dependencies WHERE repository_id = ?
                ORDER BY file_path, line
                """,
                (repository_id,),
            )
        ]
    return {"repository_id": repository_id, "edges": edges, "unresolved": unresolved}
