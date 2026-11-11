import ast
import re
from collections import defaultdict, deque
from pathlib import Path

from app.services.dependency_service import analyze_dependencies, list_source_files

PYTHON_BUILTINS = set(dir(__builtins__))
JS_DEFINITION_PATTERN = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)"
    r"|^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>|[\w$]+\s*=>)",
    re.MULTILINE,
)
JS_CALL_PATTERN = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
JS_METHOD_PATTERN = re.compile(
    r"^\s*(?:(?:static|async|public|private|protected|override|get|set)\s+)*"
    r"([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*(?::\s*[^{}]+)?\{",
)
JS_IMPORT_BINDING_PATTERN = re.compile(
    r"""(?ms)^\s*import\s+(?!['"])(.*?)\s+from\s*['"]([^'"]+)['"]"""
)


def _read_source(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def _find_brace_end(source: str, opening_brace: int) -> int:
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return opening_brace + 1


def _analyze_python_file(path: Path, relative_path: str, source: str) -> tuple[list[dict], list[dict]]:
    try:
        tree = ast.parse(source, filename=relative_path)
    except SyntaxError:
        return [], []

    definitions = []
    calls = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self._definition(node, "class")
            self.scope.append(node.name)
            for child in node.body:
                self.visit(child)
            self.scope.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._function(node)

        def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self._definition(node, "function" if len(self.scope) == 0 else "method")
            qualified = ".".join([*self.scope, node.name])
            definition_index = len(definitions) - 1
            self.scope.append(node.name)
            for child in node.body:
                self.visit(child)
            self.scope.pop()
            definitions[definition_index]["qualified_name"] = qualified

        def _definition(self, node: ast.AST, kind: str) -> None:
            definitions.append({
                "name": node.name,
                "qualified_name": ".".join([*self.scope, node.name]),
                "kind": kind,
                "file_path": relative_path,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", None) or node.lineno,
            })

        def visit_Call(self, node: ast.Call) -> None:
            caller = ".".join(self.scope) if self.scope else "<module>"
            receiver = None
            if isinstance(node.func, ast.Name):
                callee = node.func.id
            elif isinstance(node.func, ast.Attribute):
                callee = node.func.attr
                if isinstance(node.func.value, ast.Name):
                    receiver = node.func.value.id
            else:
                callee = None
            if callee:
                calls.append({
                    "caller": caller,
                    "callee": callee,
                    "file_path": relative_path,
                    "line": node.lineno,
                    "resolved": False,
                    "receiver": receiver,
                })
            self.generic_visit(node)

    Visitor().visit(tree)
    return definitions, calls


def _analyze_javascript_file(path: Path, relative_path: str, source: str) -> tuple[list[dict], list[dict]]:
    definitions = []
    definition_ranges = []
    for match in JS_DEFINITION_PATTERN.finditer(source):
        name = match.group(1) or match.group(2)
        if not name:
            continue
        prefix = source[:match.start()]
        line = prefix.count("\n") + 1
        is_class = "class " in match.group(0)
        end_index = match.end()
        arrow = source.find("=>", match.start(), match.end())
        opening_brace = (
            source.find("{", arrow + 2)
            if arrow >= 0
            else source.find("{", match.end())
        )
        if arrow >= 0:
            body_start = arrow + 2
            while body_start < len(source) and source[body_start].isspace():
                body_start += 1
            if body_start < len(source) and source[body_start] != "{":
                opening_brace = -1
        if opening_brace >= 0:
            end_index = _find_brace_end(source, opening_brace)
        end_line = source.count("\n", 0, end_index) + 1
        qualified_name = name
        if not is_class:
            enclosing_class = next((
                item["name"] for item in reversed(definitions)
                if item["kind"] == "class"
                and item["line"] < line <= item["end_line"]
            ), None)
            if enclosing_class:
                qualified_name = f"{enclosing_class}.{name}"
        definitions.append({
            "name": name,
            "qualified_name": qualified_name,
            "kind": "class" if is_class else "function",
            "file_path": relative_path,
            "line": line,
            "end_line": end_line,
        })
        if not is_class:
            definition_ranges.append((line, end_line, qualified_name))

    lines = source.splitlines()
    class_definitions = [item for item in definitions if item["kind"] == "class"]
    for class_definition in class_definitions:
        for line_number in range(class_definition["line"] + 1, class_definition["end_line"] + 1):
            line = lines[line_number - 1]
            method_match = JS_METHOD_PATTERN.match(line)
            if not method_match:
                continue
            name = method_match.group(1)
            if name in {"if", "for", "while", "switch", "catch"}:
                continue
            absolute_start = sum(len(item) + 1 for item in lines[:line_number - 1])
            opening_brace = source.find("{", absolute_start, absolute_start + len(line))
            if opening_brace < 0:
                continue
            end_index = _find_brace_end(source, opening_brace)
            end_line = source.count("\n", 0, end_index) + 1
            qualified_name = f"{class_definition['name']}.{name}"
            definitions.append({
                "name": name,
                "qualified_name": qualified_name,
                "kind": "method",
                "file_path": relative_path,
                "line": line_number,
                "end_line": end_line,
            })
            definition_ranges.append((line_number, end_line, qualified_name))

    calls = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.lstrip()
        if (
            stripped.startswith(("//", "*", "/*", "import "))
            or re.match(r"(?:async\s+)?function\s+", stripped)
            or re.match(r"class\s+", stripped)
            or re.match(r"export\s+(?:\{|\*)", stripped)
            or JS_METHOD_PATTERN.match(stripped)
        ):
            continue
        call_source = re.sub(
            r"^\s*export\s+(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*",
            "",
            line,
        )
        caller_candidates = [
            item for item in definition_ranges
            if item[0] <= line_number <= item[1]
        ]
        caller = min(caller_candidates, key=lambda item: item[1] - item[0])[2] if caller_candidates else "<module>"
        for match in JS_CALL_PATTERN.finditer(call_source):
            name = match.group(1)
            if name in {"if", "for", "while", "switch", "catch", "function"}:
                continue
            calls.append({
                "caller": caller,
                "callee": name,
                "file_path": relative_path,
                "line": line_number,
                "resolved": False,
                "receiver": (
                    "this"
                    if call_source[max(0, match.start() - 6):match.start()].endswith("this.")
                    else None
                ),
            })
    return definitions, calls


def analyze_code(repository_id: str, repository_root: Path, query: str = "", file_path: str = "") -> dict:
    graph = analyze_dependencies(repository_id, repository_root)
    definitions = []
    calls = []
    files = list_source_files(repository_root)

    for path in files:
        relative = path.relative_to(repository_root).as_posix()
        source = _read_source(path)
        if source is None:
            continue
        if path.suffix.lower() == ".py":
            file_definitions, file_calls = _analyze_python_file(path, relative, source)
        else:
            file_definitions, file_calls = _analyze_javascript_file(path, relative, source)
        definitions.extend(file_definitions)
        calls.extend(file_calls)

    definitions_by_name: dict[str, list[dict]] = defaultdict(list)
    definitions_by_qualified: dict[str, list[dict]] = defaultdict(list)
    for definition in definitions:
        definitions_by_name[definition["name"]].append(definition)
        definitions_by_qualified[definition["qualified_name"]].append(definition)

    import_bindings: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    graph_edges_by_source: dict[str, list[dict]] = defaultdict(list)
    for edge in graph["edges"]:
        graph_edges_by_source[edge["source"]].append(edge)
    for path in files:
        relative = path.relative_to(repository_root).as_posix()
        source = _read_source(path)
        if source is None:
            continue
        if path.suffix.lower() == ".py":
            try:
                tree = ast.parse(source, filename=relative)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                targets = {
                    edge["target"]
                    for edge in graph_edges_by_source.get(relative, [])
                    if edge["module"] == (node.module or "")
                    or edge["module"].startswith(f"{node.module}.")
                }
                for alias in node.names:
                    for target in targets:
                        import_bindings[relative].append((
                            alias.asname or alias.name,
                            target,
                            alias.name,
                        ))
        else:
            for match in JS_IMPORT_BINDING_PATTERN.finditer(source):
                bindings, module = match.groups()
                targets = {
                    edge["target"]
                    for edge in graph_edges_by_source.get(relative, [])
                    if edge["module"] == module
                }
                named = re.search(r"\{([^}]+)\}", bindings)
                if named:
                    for item in named.group(1).split(","):
                        parts = item.strip().split()
                        if not parts:
                            continue
                        original = parts[0]
                        local = parts[-1] if len(parts) > 1 and parts[-2] == "as" else original
                        for target in targets:
                            import_bindings[relative].append((local, target, original))
                else:
                    default = bindings.strip().split(",")[0].strip()
                    if default and not default.startswith("*"):
                        for target in targets:
                            import_bindings[relative].append((default, target, default))

    unresolved_calls = []
    for call in calls:
        candidates = definitions_by_name.get(call["callee"], [])
        same_file = [item for item in candidates if item["file_path"] == call["file_path"]]
        if call.get("receiver") in {"self", "cls", "this"} and "." in call["caller"]:
            class_name = call["caller"].rsplit(".", 1)[0]
            method = definitions_by_qualified.get(
                f"{class_name}.{call['callee']}", []
            )
            target = method[0] if len(method) == 1 else None
        elif call.get("receiver") in definitions_by_qualified:
            method = definitions_by_qualified.get(
                f"{call['receiver']}.{call['callee']}", []
            )
            target = method[0] if len(method) == 1 else None
        elif len(same_file) == 1:
            target = same_file[0]
        else:
            imported_symbols = [
                (target_path, original_name)
                for local_name, target_path, original_name
                in import_bindings.get(call["file_path"], [])
                if local_name == call["callee"]
            ]
            imported_candidates = []
            for target_path, original_name in imported_symbols:
                imported_candidates.extend(
                    candidate
                    for candidate in definitions_by_name.get(original_name, [])
                    if candidate["file_path"] == target_path
                )
            target = imported_candidates[0] if len(imported_candidates) == 1 else None
        if target:
            call["callee"] = target["qualified_name"]
            call["resolved"] = True
        elif call["callee"] not in PYTHON_BUILTINS:
            unresolved_calls.append({
                key: value for key, value in call.items() if key != "receiver"
            })

    filtered_definitions = definitions
    if query:
        normalized = query.strip().lower()
        filtered_definitions = [
            item for item in definitions
            if normalized in item["name"].lower()
            or normalized in item["qualified_name"].lower()
        ]

    if file_path:
        filtered_definitions = [item for item in filtered_definitions if item["file_path"] == file_path]

    matched_names = {
        definition["qualified_name"] for definition in filtered_definitions
    } | {definition["name"] for definition in filtered_definitions}
    filtered_calls = [
        call for call in calls
        if (not query or query.lower() in call["caller"].lower() or query.lower() in call["callee"].lower())
        and (not file_path or call["file_path"] == file_path)
    ]
    public_calls = [
        {key: value for key, value in call.items() if key != "receiver"}
        for call in filtered_calls
    ]

    impacted_files: set[str] = set()
    if file_path:
        reverse_dependencies: dict[str, set[str]] = defaultdict(set)
        for edge in graph["edges"]:
            reverse_dependencies[edge["target"]].add(edge["source"])
        queue = deque([file_path])
        seen = {file_path}
        while queue:
            dependency = queue.popleft()
            for importer in reverse_dependencies.get(dependency, set()):
                impacted_files.add(importer)
                if importer not in seen:
                    seen.add(importer)
                    queue.append(importer)

    impacted_functions = set()
    if matched_names:
        reverse_calls: dict[str, set[str]] = defaultdict(set)
        for call in calls:
            if call["resolved"]:
                reverse_calls[call["callee"]].add(call["caller"])
        queue = deque(matched_names)
        seen_functions = set(matched_names)
        while queue:
            callee = queue.popleft()
            for caller in reverse_calls.get(callee, set()):
                if caller not in seen_functions:
                    seen_functions.add(caller)
                    impacted_functions.add(caller)
                    queue.append(caller)

    return {
        "repository_id": repository_id,
        "definitions": filtered_definitions[:500],
        "calls": public_calls[:1000],
        "impact": {
            "files": sorted(impacted_files),
            "functions": sorted(impacted_functions),
        },
        "unresolved": unresolved_calls[:500],
    }
