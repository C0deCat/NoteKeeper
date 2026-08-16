"""Architecture checks for the composition/runtime split."""

import ast
from pathlib import Path

import notekeeper.composition as composition


PROJECT_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "notekeeper"


def test_removed_composition_roots_are_not_public() -> None:
    for name in (
        "build_runtime",
        "build_infrastructure",
        "build_stage1_use_cases",
        "NoteKeeperRuntime",
        "InfrastructureBundle",
        "Stage1UseCases",
    ):
        assert not hasattr(composition, name)


def test_process_and_capacity_implementations_live_in_infrastructure() -> None:
    composition_root = SOURCE_ROOT / "composition"
    infrastructure_jobs = SOURCE_ROOT / "infrastructure" / "runtime" / "jobs"
    moved_modules = (
        "job_capacity.py",
        "process_execution_registry.py",
        "process_job_executor.py",
        "process_message_writer.py",
        "process_tree.py",
    )

    assert all(not (composition_root / name).exists() for name in moved_modules)
    assert all((infrastructure_jobs / name).is_file() for name in moved_modules)


def test_infrastructure_does_not_import_composition() -> None:
    infrastructure_root = SOURCE_ROOT / "infrastructure"
    violations = []
    for path in infrastructure_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = (alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names = (node.module or "",)
            else:
                continue
            if any(name.startswith("notekeeper.composition") for name in names):
                violations.append(path.relative_to(PROJECT_ROOT))

    assert violations == []
