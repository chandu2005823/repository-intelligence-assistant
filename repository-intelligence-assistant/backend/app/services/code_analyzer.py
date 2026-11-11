import ast
from pathlib import Path


def analyze_python_file(file_path: Path, repository_root: Path) -> dict:
    """
    Analyze a Python file without executing its code.
    Extract functions, classes, imports, and line counts.
    """

    relative_path = file_path.relative_to(repository_root).as_posix()

    result = {
        "path": relative_path,
        "functions": [],
        "classes": [],
        "imports": [],
        "total_lines": 0,
        "syntax_error": None,
    }

    try:
        source_code = file_path.read_text(encoding="utf-8-sig")
        result["total_lines"] = len(source_code.splitlines())

        syntax_tree = ast.parse(source_code, filename=relative_path)

        for node in ast.walk(syntax_tree):

            # Extract function definitions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result["functions"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "async": isinstance(node, ast.AsyncFunctionDef),
                })

            # Extract class definitions
            elif isinstance(node, ast.ClassDef):
                result["classes"].append({
                    "name": node.name,
                    "line": node.lineno,
                })

            # Extract import statements
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                result["imports"].append({
                    "module": node.module,
                    "names": [alias.name for alias in node.names],
                    "level": node.level,
                })

    except SyntaxError as error:
        result["syntax_error"] = {
            "message": error.msg,
            "line": error.lineno,
        }

    except (UnicodeDecodeError, OSError) as error:
        result["syntax_error"] = {
            "message": f"Could not read file: {error}",
            "line": None,
        }

    return result
def analyze_python_repository(repository_root: Path) -> dict:
    """
    Analyze Python files throughout an extracted repository.
    """

    results = []
    total_functions = 0
    total_classes = 0
    total_lines = 0
    files_with_errors = 0

    ignored_directories = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "site-packages",
        "dist",
        "build",
    }

    for file_path in repository_root.rglob("*.py"):
        if any(part in ignored_directories for part in file_path.parts):
            continue

        try:
            result = analyze_python_file(file_path, repository_root)
        except (OSError, ValueError):
            continue

        results.append(result)

        total_functions += len(result["functions"])
        total_classes += len(result["classes"])
        total_lines += result["total_lines"]

        if result["syntax_error"] is not None:
            files_with_errors += 1

    return {
        "python_file_count": len(results),
        "total_functions": total_functions,
        "total_classes": total_classes,
        "total_lines": total_lines,
        "files_with_syntax_errors": files_with_errors,
        "files": results,
    }