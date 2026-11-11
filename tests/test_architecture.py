"""The core package must stay independent of the UI framework."""

import ast
from pathlib import Path

CORE = Path(__file__).parent.parent / "src" / "portfolio" / "core"
FORBIDDEN = {"streamlit", "portfolio.ui"}


def imported_modules(path: Path) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_core_does_not_import_ui():
    offenders = {
        str(path.relative_to(CORE)): bad
        for path in CORE.rglob("*.py")
        if (
            bad := {
                m
                for m in imported_modules(path)
                if any(m == f or m.startswith(f + ".") for f in FORBIDDEN)
            }
        )
    }
    assert not offenders
