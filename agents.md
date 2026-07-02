# NoteKeeper Agent Guidelines

## File Organization

- Keep importable production code under `src/notekeeper`.
- Keep tests outside production code under `tests`, mirroring project layers where practical.
- Use one behaviorful concrete implementation class per `.py` file.
- Protocol, interface, and abstract-class files may group multiple related interfaces.
- DTO barrels such as command/result/snapshot modules may remain grouped unless a task explicitly asks to split them.
- Keep `__init__.py` files as package markers and public facades only.
- Public facades must use explicit imports and explicit `__all__`.
- Do not put business logic, persistence logic, runtime side effects, or hidden initialization work in `__init__.py`.

## Utilities

- Put helper functions in a local `utils` package, split by role when the utilities grow.
- Code inside a feature folder must not import utilities from sibling feature folders.
- If multiple sibling folders need the same helper, move that helper to the nearest common parent `utils` package.
- Keep utility modules behavior-focused: path safety, row mapping, serialization, checksums, job helpers, and similar roles should live in separate files when they evolve independently.

## Imports

- Use explicit imports.
- Avoid wildcard imports except for an intentional public facade re-export with explicit `__all__`.
- Group imports in PEP 8 order: standard library, third-party libraries, local application/library imports.
- Prefer absolute imports for cross-package dependencies.
- Use relative imports only inside a package when they make a local relationship clearer and do not cross layer boundaries.

## Layer Boundaries

- `domain` must not depend on `application`, `infrastructure`, `interfaces`, or `composition`.
- `application` may depend on `domain` and application ports/results/commands, but not concrete infrastructure.
- `infrastructure` implements application ports and may depend on external libraries, local filesystems, SQLite, subprocesses, and API clients.
- `composition` wires concrete implementations together and owns runtime configuration.

## References

- PyPA: `src` layout helps prevent accidental imports from the working tree and keeps importable packages under `src`: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- pytest: tests outside application code are a supported layout and work well with `src` layout: https://docs.pytest.org/en/stable/explanation/goodpractices.html
- PEP 8: import grouping, explicit imports, and wildcard-import guidance: https://peps.python.org/pep-0008/#imports
- Python docs: `__init__.py` marks packages and can define public `__all__`: https://docs.python.org/3/tutorial/modules.html#packages
- PEP 8: module-level dunder names such as `__all__` placement: https://peps.python.org/pep-0008/#module-level-dunder-names
