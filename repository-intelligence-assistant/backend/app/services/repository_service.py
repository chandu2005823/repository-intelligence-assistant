from pathlib import Path

IGNORED_DIRECTORIES = {
".git",
".venv",
"venv",
"__pycache__",
"node_modules",
"dist",
"build",
".next",
".idea",
".vscode",
}

IGNORED_FILES = {
".env",
".env.local",
".env.production",
}

LANGUAGE_EXTENSIONS = {
".py": "Python",
".js": "JavaScript",
".jsx": "JavaScript React",
".ts": "TypeScript",
".tsx": "TypeScript React",
".java": "Java",
".c": "C",
".h": "C/C++ Header",
".cpp": "C++",
".hpp": "C++ Header",
".cs": "C#",
".go": "Go",
".rs": "Rust",
".php": "PHP",
".rb": "Ruby",
".html": "HTML",
".css": "CSS",
".sql": "SQL",
".md": "Markdown",
".json": "JSON",
".yaml": "YAML",
".yml": "YAML",
".toml": "TOML",
".xml": "XML",
}

def analyze_repository(repository_path: Path) -> dict:
    """Analyze files in an already safely extracted repository."""


    file_count = 0
    total_size = 0
    language_counts = {}
    files = []
    directories = set()
    important_files = []

    for file_path in repository_path.rglob("*"):
        relative_path = file_path.relative_to(repository_path)

        # Ignore directories and files inside excluded directories.
        if any(
            part in IGNORED_DIRECTORIES
            for part in relative_path.parts[:-1]
        ):
            continue

        if file_path.is_dir():
            continue

        if file_path.is_symlink():
            continue

        if file_path.name in IGNORED_FILES:
            continue

        # Ignore files commonly used to store local secrets.
        if file_path.name.startswith(".env."):
            continue

        extension = file_path.suffix.lower()

        # Only index known text/source formats in this initial version.
        if extension not in LANGUAGE_EXTENSIONS:
            continue

        try:
            size = file_path.stat().st_size
        except OSError:
            continue

        file_count += 1
        total_size += size

        language = LANGUAGE_EXTENSIONS[extension]
        language_counts[language] = (
            language_counts.get(language, 0) + 1
        )

        directories.add(relative_path.parent.as_posix())

        files.append({
            "path": relative_path.as_posix(),
            "name": file_path.name,
            "language": language,
            "size_bytes": size,
        })

        if file_path.name.lower() in {
            "readme.md",
            "requirements.txt",
            "pyproject.toml",
            "package.json",
            "pom.xml",
            "build.gradle",
        }:
            important_files.append(relative_path.as_posix())

    files.sort(key=lambda item: item["path"])

    return {
        "repository_name": repository_path.name,
        "file_count": file_count,
        "total_size_bytes": total_size,
        "languages": language_counts,
        "directories": sorted(directories),
        "important_files": sorted(important_files),
        "files": files,
    }

