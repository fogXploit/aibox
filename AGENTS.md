# Repository Guidelines

## Project Structure & Modules
`aibox/` houses the CLI, config models, container orchestration, profile definitions, and AI providers—keep domain logic in these subpackages so commands stay thin. `tests/` mirrors those modules (`tests/unit`, `tests/fixtures`), while `docs/` collects architecture, multi-agent, and configuration references; helpers live in `scripts/`. Treat `htmlcov/` as disposable coverage output.

## Build, Test, and Development Commands
```bash
uv pip install -e ".[dev]"            # install runtime + dev extras
ruff check aibox tests                # lint/import order
ruff format aibox tests               # auto-format
mypy aibox                            # strict typing
pytest                                # full suite (markers/opts in pyproject)
pytest --cov=aibox --cov-report=html  # coverage (≥80% floor)
pre-commit run --all-files
aibox --help                          # quick CLI smoke test
```

## Coding Style & Simple Design
Use Python 3.11+, 4-space indentation, and explicit type hints everywhere to satisfy strict `mypy`. Ruff enforces 100-character lines and naming; only `__init__.py` may ignore unused imports. Refactor using Kent Beck’s rules in priority order: all tests pass → intent is obvious → no duplication → fewest necessary elements. Document mass deltas when refactors stall.

## TDD Workflow
Start every problem by listing base `pytest` cases (`it.todo()` conceptually) before activating exactly one test. Follow Red (compilation/runtime failure), Green (minimal implementation), and Refactor (mandatory improvement) phases with explicit “guessing game” predictions before each run. Stick to baby steps, resist lookahead, and never implement beyond the current failing test; update docs/tests together to keep coverage stable.

## Human-in-the-Loop Checkpoints
After each phase summarize what happened (test chosen, prediction accuracy, implementation, refactors/mass changes) and pause for approval before moving on. If a prediction is wrong, stop and explain why before continuing or investigating per human guidance. No batch execution—every Red/Green/Refactor loop or phase transition requires confirmation.

## Commit & Pull Request Guidance
History favors short, imperative subjects (`Add configuration system with Pydantic models`, `Fix GitHub Actions CI workflow`, `chore: remove all ClaudeBox references`). Keep scopes tight, pair code/tests/docs/`CHANGELOG.md` updates, and avoid WIP commits. Pull requests should link issues, describe user-visible CLI effects, include `pytest`/`ruff` snippets, and add Rich output screenshots when formatting changes.

## Security & Configuration
Never commit provider credentials; rely on `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in your shell. Keep `.aibox/config.yml` examples minimal, document new schema fields in `docs/configuration.md`, and ensure `aibox init` plus `slot add` stay backward compatible without secrets to protect CI runs.
