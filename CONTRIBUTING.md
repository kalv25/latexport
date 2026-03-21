# Contributing to texport

Thank you for your interest in contributing! This document covers everything you need to get started.

## Table of Contents

1. [Development setup](#1-development-setup)
2. [Running tests](#2-running-tests)
3. [Code style](#3-code-style)
4. [Project structure](#4-project-structure)
5. [Submitting changes](#5-submitting-changes)
6. [Reporting bugs](#6-reporting-bugs)

---

## 1. Development setup

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), LaTeXML, pdflatex (see [README prerequisites](README.md#prerequisites)).

```bash
git clone <repository-url>
cd texport
uv sync
uv pip install -e .
```

`uv sync` installs all runtime and dev dependencies. `uv pip install -e .` registers the CLI entry points (`texport`, `texport-index`, `texport-clean`, `texport-bundle`) in the virtual environment.

---

## 2. Running tests

```bash
# Full test suite
uv run pytest

# With coverage report
uv run pytest --cov=texport --cov-report=term-missing

# Single file
uv run pytest tests/test_main.py
```

All pull requests must keep the full test suite green. New functionality should include tests.

---

## 3. Code style

```bash
# Lint and format
uv run ruff check .
uv run ruff format .

# Type checking
uv run pyright
```

- **Formatting:** [Ruff](https://docs.astral.sh/ruff/) (replaces black + isort)
- **Type checking:** Pyright in strict mode — all new code must be fully typed
- **No docstrings required** on private helpers, but public functions should have them

---

## 4. Project structure

```
texport/                  ← Python package
  __init__.py             ← version
  config.py               ← all tunable constants; reads [tool.texport] from pyproject.toml
  main.py                 ← texport CLI: LaTeX → HTML + PDF pipeline
  create_main_index.py    ← texport-index CLI: generates navigation index
  embed_assets.py         ← texport-bundle CLI: inlines CSS/JS into a standalone file
  zip_project.py          ← developer utility: creates a timestamped project archive
  static/                 ← default web assets (CSS, JS); seeded into output/ on every run
  templates/              ← HTML templates
  latexml/                ← LaTeXML binding files (.ltxml); all loaded automatically
tests/                    ← pytest test suite (mirrors texport/ module structure)
examples/                 ← example .tex sources and attribution
```

### Adding a LaTeXML binding

Create a `.ltxml` file in `texport/latexml/`. It is automatically loaded on every `latexmlc` invocation — no changes to `main.py` needed.

### Adding a new CLI command

1. Implement the entry-point function in the appropriate module (or a new one).
2. Add it to `[project.scripts]` in `pyproject.toml`.
3. Run `uv pip install -e .` to register it.
4. Document it in `README.md` and `SPECS.md`.

---

## 5. Submitting changes

1. **Fork** the repository and create a feature branch (`git checkout -b my-feature`).
2. Make your changes with tests.
3. Run `ruff check .`, `ruff format .`, `pyright`, and `pytest` — all must pass.
4. Open a pull request against `main` with a clear description of what and why.

For significant changes, open an issue first to discuss the approach before investing time in an implementation.

---

## 6. Reporting bugs

Please [open an issue](../../issues) and include:

- texport version (`uv run texport --version` once implemented, or check `pyproject.toml`)
- Python version (`python --version`)
- LaTeXML version (`latexmlc --VERSION`)
- A minimal `.tex` file that reproduces the problem (if applicable)
- The full error output
