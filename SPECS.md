# texport — Structured Specifications

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Configuration — `config.py`](#2-configuration--configpy)
3. [LaTeX Processor — `main.py`](#3-latex-processor--mainpy)
4. [Index Generator — `create_main_index.py`](#4-index-generator--create_main_indexpy)
5. [Asset Embedder — `embed_assets.py`](#5-asset-embedder--embed_assetspy)
6. [Project Archiver — `zip_project.py`](#6-project-archiver--zip_projectpy)
7. [End-to-End Pipeline](#7-end-to-end-pipeline)
8. [Dependencies & Environment](#8-dependencies--environment)

---

## 1. Project Overview

`texport` is a build pipeline that converts LaTeX (`.tex`) source files into
web-ready, accessible HTML pages, while simultaneously producing PDF versions.
The HTML output is post-processed to inject shared CSS/JS, replace typographic
symbols with accessible equivalents, and consolidate per-document stylesheets
into a shared folder. A secondary tool generates a navigable main index page
over all documents, and a utility script can bundle each HTML file into a
fully self-contained document by inlining all external assets.

### High-Level Data Flow

```
static/
  css/, js/  ──────────────► output/css/, output/js/   (_seed_output_dir)

tex_src/*.tex
     │
     ▼
 latexmlc  ─────────────────► output/{stem}/index.html
 (+ emph-in-math.ltxml)
 pdflatex  ─────────────────► output/{stem}/{stem}.pdf
     │
     ▼
 add_custom_css_and_js()   ── injects CSS/JS links, fixes QED symbols
 update_stylesheet_links() ── consolidates local CSS → ../css/
     │
     ▼
 create_main_index.py      ── output/index.html  (navigation page)
     │
     ▼ (optional)
 embed_assets.py           ── {stem}_bundled.html        (standalone file)
```

---

## 2. Configuration — `config.py`

### Purpose

Single source of truth for all tunable constants shared across modules.
No logic; only `Path` objects and scalar values.

### Constants

| Name | Type | Default | Used By | Description |
|---|---|---|---|---|
| `OUTPUT_DIR` | `Path` | `./output` | `main.py`, `create_main_index.py` | Root directory for all HTML/PDF output |
| `STATIC_DIR` | `Path` | `./static` | `main.py` | Source directory for shared CSS/JS assets; seeded into output on every run |
| `LATEXML_DIR` | `Path` | `<project_root>/latexml` | `main.py` | Directory containing LaTeXML binding files (`.ltxml`); absolute path derived from `config.py` location |
| `SRC_QED_SYMBOL` | `str` | `"∎"` | `main.py` | Raw QED character to search-replace in HTML |
| `ENCODING` | `str` | `"utf-8"` | `main.py`, `create_main_index.py` | Encoding used for all file I/O |
| `ROOT_DIR` | `Path` | alias of `OUTPUT_DIR` | `create_main_index.py` | Root to scan for `index.html` files |
| `PATTERN` | `str` | `"index.html"` | `create_main_index.py` | Glob filename pattern for discovery |
| `TEMPLATE_PATH` | `Path` | `templates/main_index_template.html` | `create_main_index.py` | Path to the index page Jinja-style template |

### Notes

- `OUTPUT_DIR`, `STATIC_DIR` are **relative to the working directory** at runtime.
  Importing modules must be run from the project root so these paths resolve correctly.
- `LATEXML_DIR` is **absolute** (`Path(__file__).parent / "latexml"`), so LaTeXML
  binding files are always found regardless of the working directory.

---

## 3. LaTeX Processor — `main.py`

### Purpose

Orchestrates the full per-document conversion pipeline: seeds the output
directory with shared static assets, calls external tools (`latexmlc`,
`pdflatex`) with a custom LaTeXML binding, and post-processes the generated HTML.

### CLI Interface

```
uv run texport [OPTIONS] TEX_FILE [TEX_FILE ...]
```

| Argument | Required | Description |
|---|---|---|
| `tex_files` | Yes (1+) | One or more `.tex` source files to process |
| `-o`, `--output` | No | Root output directory (default: `OUTPUT_DIR` from `config.py`). Per-file output is placed in `{output}/{stem}/`. |
| `-N`, `--name` | No | Override the output subdirectory name (default: source file stem). Only valid when processing a single file. |
| `-n`, `--dry-run` | No | Print all actions without executing or modifying anything |

**Exit codes:** `0` = all files succeeded; `1` = one or more files failed.

---

### Functions

---

#### `replace_qed_symbol(html_content: str) -> str`

**Purpose:** Replace the raw Unicode QED character (`SRC_QED_SYMBOL`) with an
accessible HTML equivalent that is visually identical but screen-reader-friendly.

**Input:** Raw HTML string.

**Output:** HTML string with every occurrence of `SRC_QED_SYMBOL` replaced by:

```html
<span aria-hidden="true" class="qed">∎</span>
<span class="visually-hidden">End of proof</span>
```

**Behavior:**
- Pure string replacement; no HTML parsing.
- Replaces all occurrences (not just the first).
- Returns the original string unchanged if `SRC_QED_SYMBOL` is not found.

**Side effects:** None.

---

#### `add_custom_css_and_js(file_path: str, dry_run: bool = False) -> bool`

**Purpose:** Post-process a single HTML file by (1) replacing QED symbols,
and (2) injecting CSS and JavaScript `<link>`/`<script>` tags into `<head>`.

**Inputs:**

| Parameter | Type | Description |
|---|---|---|
| `file_path` | `str` | Absolute or relative path to the target HTML file |
| `dry_run` | `bool` | If `True`, log intended changes and return `True` without modifying the file |

**Output:** `True` on success, `False` on any error.

**Behavior:**

1. In dry-run mode: prints four descriptive log lines and returns `True`.
2. Reads the file at `file_path` with `ENCODING`.
3. Calls `replace_qed_symbol()` on the raw HTML string.
4. Parses the result with BeautifulSoup (`html.parser`).
5. Validates that a `<head>` element exists; returns `False` with a warning if not.
6. Calls `_inject_resources(soup)` to append resource tags.
7. Serialises the soup back to a string and overwrites `file_path`.

**Error handling:**

| Condition | Behaviour |
|---|---|
| `FileNotFoundError` on read | Logs error, returns `False` |
| `IOError` on read | Logs error, returns `False` |
| Missing `<head>` tag | Logs warning, returns `False` |
| `IOError` on write | Logs error, returns `False` |

---

#### `_inject_resources(soup: BeautifulSoup) -> None`

**Purpose:** Append CSS and JS resource tags to `<head>` if they are not
already present. Private helper; not part of the public API.

**Injected resources (in order):**

| Tag | Key attribute | Value |
|---|---|---|
| `<link>` | `href` | `../css/custom.css` |
| `<script>` | `src` | `../js/custom.js` |
| `<script>` | `src` | `../js/mathjax-config.js` |
| `<script>` | `src` | `https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js` |

**Idempotency:** Each tag is only appended if an identical tag (same name +
attributes) is not already present, preventing duplicates on re-runs.

**Side effects:** Mutates `soup` in place; returns `None`.

---

#### `update_stylesheet_links(html_path: str | Path, css_folder: str | Path, dry_run: bool = False) -> list[str]`

**Purpose:** Consolidate per-document CSS files into a shared folder.
Finds local `<link rel="stylesheet">` tags, updates their `href` to point to
`../css/{filename}`, and deletes the original local copies.

**Inputs:**

| Parameter | Type | Description |
|---|---|---|
| `html_path` | `str \| Path` | Path to the HTML file to process |
| `css_folder` | `str \| Path` | Path to the shared CSS folder (must already contain the CSS files) |
| `dry_run` | `bool` | If `True`, print intended changes without modifying any files |

**Output:** List of CSS filenames that were (or would be) updated.
Returns an empty list if nothing was processed or an error occurred.

**Behavior:**

1. Reads and parses the HTML file.
2. Iterates over all `<link rel="stylesheet">` tags.
3. **Skips** tags whose `href`:
   - Is absent or empty.
   - Starts with `http://`, `https://`, or `//` (external URLs).
   - Already contains `../css/` or the `css_folder` path (already redirected).
4. For each remaining tag, derives `css_filename` and checks whether
   `css_folder / css_filename` exists. Skips if not found in shared folder.
5. Updates the `href` to `../css/{css_filename}`.
6. Deletes the original local CSS file (if it exists).
7. Writes the modified soup back to `html_path`.

**Error handling:**

| Condition | Behaviour |
|---|---|
| `FileNotFoundError` / `IOError` on read | Logs error, returns `[]` |
| `OSError` when deleting local CSS | Logs error, continues processing |
| `IOError` on write | Logs error |

**Side effects:** Modifies `html_path` in place; may delete local CSS files.

---

#### `process_file(cmd: str, dry_run: bool = False, cwd: Path | None = None, max_exit_code: int = 0) -> bool`

**Purpose:** Execute a single shell command string, capturing output.

**Inputs:**

| Parameter | Type | Description |
|---|---|---|
| `cmd` | `str` | Full shell command string (will be split with `shlex.split`) |
| `dry_run` | `bool` | If `True`, log the command and return `True` without executing |
| `cwd` | `Path \| None` | Working directory for the subprocess; defaults to the current process directory |
| `max_exit_code` | `int` | Highest exit code still treated as success (default `0`). Pass `1` for `latexmlc` to tolerate warning-only runs. |

**Output:** `True` if the command's exit code is ≤ `max_exit_code`, `False` otherwise.

**Behavior:**
- Uses `subprocess.run` (without `check=True`), capturing both `stdout` and `stderr`.
- Logs the command before running it.
- Logs a success message on completion.
- On failure, logs the exit code and any captured `stderr` (falling back to `stdout`).

**Error handling:**

| Condition | Behaviour |
|---|---|
| Exit code > `max_exit_code` | Logs error with exit code and output, returns `False` |
| `FileNotFoundError` (binary not in PATH) | Logs advisory error, returns `False` |

---

#### `_seed_output_dir(output_dir: Path, static_dir: Path = STATIC_DIR) -> None`

**Purpose:** Copy the contents of `static_dir` into `output_dir`, ensuring
that every output directory has the shared CSS/JS assets before any documents
are processed.

**Behavior:**
- Creates `output_dir` (and parents) if it does not exist.
- Uses `shutil.copytree(..., dirs_exist_ok=True)` so existing files are
  overwritten and the call is safe on re-runs.
- Logs a warning if `static_dir` does not exist; does not raise.

**Side effects:** Creates/updates files in `output_dir`.

---

#### `_create_include_subdirs(tex_file: Path, output_dir: Path) -> None`

**Purpose:** Scan a `.tex` file for `\include{subdir/name}` commands and
pre-create any required subdirectories inside `output_dir`.

**Why:** pdflatex's `-output-directory` flag writes all output files (including
per-include `.aux` files) into the output directory using the same relative
path as the `\include` argument. If `\include{notes/chapter1}` is present,
pdflatex expects `output_dir/notes/` to exist before it can write
`notes/chapter1.aux`; it does not create the subdirectory itself.

**Behavior:**
- Reads `tex_file` with `ENCODING`; silently returns on `OSError`.
- Finds all `\include{...}` arguments using a regex.
- Creates `output_dir / parent` for each argument whose parent component is
  not `"."` (i.e. includes a subdirectory).

**Side effects:** May create subdirectories inside `output_dir`.

---

#### `_remove_empty_subdirs(output_dir: Path) -> None`

**Purpose:** Remove any empty subdirectories inside `output_dir` after aux
file cleanup, typically the stubs created by `_create_include_subdirs` for
pdflatex that are no longer needed once aux files are deleted.

**Behavior:**
- Iterates subdirectories deepest-first (`sorted(..., reverse=True)`) so
  nested empties are removed before their parents.
- Only removes directories that are completely empty (`not any(d.iterdir())`).
- Logs each removal at `INFO`; logs a warning on `OSError`.

**Side effects:** May delete subdirectories inside `output_dir`.

---

#### `_detect_bibliography(tex_file: Path) -> str | None`

**Purpose:** Determine which external bibliography tool (if any) the document
requires.

**Detection rules (first match wins):**

| Pattern found | Returns |
|---|---|
| `\usepackage[...]{biblatex}` | `"biber"` |
| `\bibliography{` | `"bibtex"` |
| `\addbibresource{` | `"biber"` |
| None of the above | `None` |

**Side effects:** None (read-only).

---

#### `_has_cite_commands(tex_file: Path) -> bool`

**Purpose:** Detect whether the document uses `\cite` variants that require
an external bibliography pre-processing step before `latexmlc` runs.

**Returns `False` (no pre-processing needed) if:**
- The file cannot be read (`OSError`).
- The bibliography is inline (`\begin{thebibliography}` present) — both
  LaTeXML and pdflatex handle this natively.

**Returns `True` if** any of these command patterns are found:
`\cite…`, `\parencite…`, `\textcite…`, `\footcite…`, `\autocite…`
(and their starred/optional variants).

**Why:** LaTeXML needs a `.bbl` file in the source directory to resolve
citations in the HTML output. Without a pre-generated `.bbl`, citations
render as `[?]`. This function gates the preliminary pdflatex → bibtex/biber
pass that produces the `.bbl` before `latexmlc` runs.

**Side effects:** None (read-only).

---

#### `process_files() -> int`

**Purpose:** CLI entry point. Parses arguments, iterates over input `.tex`
files, runs the full per-file pipeline, and reports results.

**Pipeline (before per-file loop):**

```
0. _seed_output_dir(output) — copy static/ into the root output directory.
```

**Pipeline per file (no citations):**

```
1. Validate file exists on disk.
2. Derive output_dir = output / stem.
3. _create_include_subdirs() — pre-create \include subdirs in output_dir.
4. Run latexmlc → HTML    (process_file, max_exit_code=1).
   Preloads all *.ltxml bindings from latexml/ (sorted alphabetically).
   Remove latexml.log from cwd after the call.
5. Run pdflatex → PDF     (process_file, max_exit_code=0, cwd=src_dir).
6. Remove aux files       (rglob cleanup: .aux .log .out .bbl .blg .bcf .run.xml).
7. _remove_empty_subdirs() — remove subdirs left empty after aux cleanup.
8. Call add_custom_css_and_js(output_dir / "index.html").
9. Call update_stylesheet_links(output_dir / "index.html", output / "css").
```

**Pipeline per file (with `\cite` + external bibliography):**

```
1–3. Same as above.
4.   Run pdflatex pass 1 → .aux  (cwd=src_dir).
5.   Run bibtex/biber → .bbl     (cwd=src_dir, pointing at output_dir/stem).
6.   Copy .bbl to src_dir so latexmlc can find it via --sourcedirectory.
7.   Run latexmlc → HTML.
     Remove latexml.log from cwd after the call.
8.   Remove .bbl copy from src_dir.
9.   Run pdflatex pass 2 → final PDF (cwd=src_dir).
10–12. Aux cleanup, empty subdir removal, HTML post-processing.
```

If bibliography is declared but no `\cite` commands are detected, bibtex/biber
runs only as part of the pdflatex cycle (pass 1 → bib → pass 2); latexmlc
is unaffected.

Failure of any latexmlc or pdflatex step adds the file to `failed_files` and
skips remaining steps. A failed bibtex/biber step logs a warning but does not
abort. Steps 8–9 (HTML post-processing) always run; their failures are logged
but not added to `failed_files`.

**Command templates:**

| Command | Template variables | Notes |
|---|---|---|
| `latexmlc` | `{output_dir}`, `{input_file}`, `{src_dir}` | `max_exit_code=1`; auto-preloads all `latexml/*.ltxml` |
| `pdflatex` | `{output_dir}`, `{input_name}` | `cwd=source_file_directory` so `\include` paths resolve correctly |
| `bibtex` / `biber` | absolute path to aux stem | `cwd=source_file_directory` so `.bib` files are found |

**Output:** Integer exit code (`0` = success, `1` = partial or full failure).

---

#### `clean_logs() -> int`

**Purpose:** CLI entry point (`texport-clean`). Finds and removes all
`latexml.log` files left behind by `latexmlc` invocations.

**Behavior:**
- Checks `./latexml.log` in the current working directory.
- Recursively searches `OUTPUT_DIR` for any additional `latexml.log` files.
- Logs each removal at `INFO`; logs a warning on `OSError`.
- Reports total count removed, or "No latexml.log files found." if none.

**Note:** During a normal `texport` run, `latexml.log` is already removed
automatically after each `latexmlc` call. `texport-clean` is provided for
retrospective cleanup of files from previous runs.

**Output:** Always returns `0`.

---

## 4. Index Generator — `create_main_index.py`

### Purpose

Scans the output directory for all per-document `index.html` files, extracts
their `<title>` text, and renders a navigable main index page from an HTML
template.

### CLI Interface

```
uv run texport-index [-o DIR]
```

| Argument | Required | Description |
|---|---|---|
| `-o`, `--output` | No | Output directory to scan and write the index into (default: `ROOT_DIR` from `config.py`) |

---

### Functions

---

#### `read_file_content(file_path: Path | str) -> Optional[str]`

**Purpose:** Safely read a text file, returning `None` on failure.

**Output:** File content as a string, or `None` if the file is missing or
unreadable (errors are logged via `logger.error`).

---

#### `get_link_to_pdf(directory: Path, root_dir: Path) -> str`

**Purpose:** Produce an HTML anchor to a PDF if one exists alongside
the document's `index.html`.

**Convention:** Globs `directory/*.pdf` and uses the first match, regardless
of filename. This handles cases where pdflatex names the PDF after the source
file stem (e.g. `main.pdf`) rather than the output directory name.

**Output:**
- `', <a href="{relative_pdf_path}">PDF</a>'` if any PDF is found.
- `''` (empty string) if no PDF is found.

---

#### `link_to_page(directory: Path, title: str, root_dir: Path) -> str`

**Purpose:** Build a single HTML `<li>` element for one document.

**Output format:**

```html
<li><a href="{relative_dir}/">{html_escaped_title}</a>{pdf_link}</li>\n
```

- `title` is HTML-escaped via `html.escape()`.
- `pdf_link` is the output of `get_link_to_pdf()`.

---

#### `discover_index_files(root_dir: Path) -> list[tuple[Path, str]]`

**Purpose:** Recursively find all `index.html` files under `root_dir`,
extract their page titles, and return a list of `(directory, title)` pairs.

**Behavior:**
- Uses `root_dir.rglob(PATTERN)`.
- **Skips** `root_dir/index.html` (the main index itself).
- Extracts title from `<title>` tag; falls back to `"No Title"` if absent.

**Output:** `list[tuple[Path, str]]` — each tuple is `(parent_directory, title_string)`.

---

#### `generate_links_html(index_files: list[tuple[Path, str]], root_dir: Path) -> str`

**Purpose:** Map `discover_index_files` output to a concatenated HTML string
of `<li>` elements.

**Output:** A single string of concatenated `<li>` elements (no surrounding `<ul>`).

---

#### `create_main_index_page(root_dir, template_path, *, lang, title, description, heading, contents_label) -> None`

```python
def create_main_index_page(
    root_dir: Path = ROOT_DIR,
    template_path: Path = TEMPLATE_PATH,
    *,
    lang: str = "en",
    title: str = "Documents",
    description: str = "Document index",
    heading: str = "Documents",
    contents_label: str = "Contents",
) -> None
```

**Purpose:** Orchestrate the full index generation workflow.

**Behavior:**

1. Read template from `template_path` via `read_file_content`.
2. Abort with `logger.error` if template cannot be read.
3. Call `discover_index_files(root_dir)`.
4. Call `generate_links_html(...)` to produce `links_html`.
5. Substitute all named placeholders in the template via `str.format`.
6. Write result to `root_dir/index.html`.
7. Log the resolved output path.

**Template contract:** The template file must contain the following
Python `str.format`-style placeholders: `{lang}`, `{title}`,
`{description}`, `{heading}`, `{contents_label}`, `{links}`.
All are filled by `create_main_index_page`; the keyword arguments
supply the localised text values (all default to English).

---

#### `main() -> None`

**Purpose:** CLI entry point. Parses `-o`/`--output` argument, configures
`logging` at `INFO` level, and calls `create_main_index_page(root_dir=...)`.

---

## 5. Asset Embedder — `embed_assets.py`

### Purpose

Convert an HTML file that references external CSS and JS assets into a
fully self-contained ("bundled") HTML file by inlining every asset's content
directly into the document. Assets may be local files or remote URLs.

### CLI Interface

```
uv run embed_assets.py [INPUT] [OUTPUT] [OPTIONS]
```

| Argument / Option | Required | Default | Description |
|---|---|---|---|
| `INPUT` | No | `index.html` next to script | Source HTML file path |
| `OUTPUT` | No | `{stem}_bundled.html` | Output file path |
| `--encoding` | No | `utf-8` | Encoding for reading/writing HTML |
| `--skip-remote` | No | `False` | Log remote assets to stdout; they are still embedded (see `_tag_remote_assets`) |
| `--skip-js` | No | `False` | Skip JS embedding, leaving all `<script src>` tags untouched |

**Default behaviour:** All linked CSS and JS assets are embedded inline.
Pass `--skip-js` to leave scripts as external references.

---

### Functions

---

#### `is_remote(url: str) -> bool`

Returns `True` if `url` starts with `http://` or `https://`.

---

#### `fetch_remote(url: str) -> str`

**Purpose:** Download a remote URL and return its text content.

**Behavior:**
- Uses `urllib.request.urlopen` with a 30-second timeout.
- Detects charset from `Content-Type` response header via `_charset_from_headers`.
- Falls back to `utf-8` if charset is absent.
- Uses `errors="replace"` to avoid decode failures.

**Raises:** `RuntimeError` wrapping `urllib.error.URLError` on network failure.

---

#### `_charset_from_headers(headers) -> str | None`

**Purpose:** Parse the `charset` value from an HTTP `Content-Type` header.

**Output:** Charset string (e.g. `"utf-8"`) or `None` if not found.

---

#### `read_local(path: Path) -> str`

**Purpose:** Read a local file as UTF-8 text.

**Raises:** `FileNotFoundError` if `path` does not exist.

---

#### `resolve_local(href: str, html_dir: Path) -> Path`

**Purpose:** Resolve a relative or absolute asset `href` against the HTML
file's parent directory.

**Behavior:**
- If `href` is absolute, returns `Path(href)` directly.
- Otherwise, resolves `(html_dir / href).resolve()` to an absolute path.

---

#### `fetch_asset(href: str, html_dir: Path) -> str`

**Purpose:** Unified fetch: dispatches to `fetch_remote` or `read_local`
based on whether `href` is remote.

**Raises:** `FileNotFoundError` (local) or `RuntimeError` (remote) on failure.

---

#### `embed_stylesheets(soup: BeautifulSoup, html_dir: Path) -> int`

**Purpose:** Replace every `<link rel="stylesheet" href="...">` tag with an
inline `<style>` block containing the fetched CSS text.

**Behavior:**
- Preserves the `media` attribute on the generated `<style>` tag if present.
- Skips (with a `WARNING` print) any asset that cannot be fetched.

**Output:** Count of successfully embedded stylesheets.

**Side effects:** Mutates `soup` in place.

---

#### `embed_scripts(soup: BeautifulSoup, html_dir: Path) -> int`

**Purpose:** Replace `<script src="...">` tags with inline `<script>` blocks
containing the fetched JavaScript text.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `soup` | `BeautifulSoup` | Parsed HTML document (mutated in place) |
| `html_dir` | `Path` | Directory of the source HTML file, used to resolve relative paths |

**Behavior:**
- Iterates over all `<script src="...">` tags.
- Copies the `type` attribute to the new tag if present.
- Does **not** copy `src`, `defer`, or `async` attributes.
- Skips (with a `WARNING` print) any asset that cannot be fetched.

**Output:** Count of successfully embedded scripts.

**Side effects:** Mutates `soup` in place.

---

#### `build_parser() -> argparse.ArgumentParser`

Returns the fully configured `ArgumentParser` for the CLI. Separated from
`main()` to allow isolated testing of argument parsing.

Registers all arguments described in the [CLI Interface](#cli-interface-4)
table.

---

#### `_tag_remote_assets(soup: BeautifulSoup) -> None`

**Purpose:** When `--skip-remote` is active, log remote asset URLs without
modifying their tags (browser retains ability to load them if online).

**Note:** This function only prints; it intentionally does not alter the soup.
The embedding functions will still encounter the remote tags but
`fetch_asset` will attempt to download them — `--skip-remote` works by
logging intent, not by stripping `src`/`href`.

---

#### `main() -> None`

**Purpose:** CLI entry point.

**Behavior:**

1. Resolve `input_path` (default: `index.html` next to script).
2. Exit with error if input file does not exist.
3. Resolve `output_path` (default: `{stem}_bundled.html`).
4. Parse HTML with BeautifulSoup.
5. If `--skip-remote`: call `_tag_remote_assets` (logging only; remote assets are still embedded).
6. Call `embed_stylesheets` to inline all CSS.
7. **JS embedding:** If `--skip-js`: skip; otherwise call `embed_scripts` to inline all JS.
8. Create output parent directories if needed.
9. Write serialised soup to `output_path`.

---

## 6. Project Archiver — `zip_project.py`

### Purpose

Create a timestamped `.zip` archive of the project, automatically excluding
build artifacts, caches, lock files, and dotfiles.

### CLI Interface

```
python zip_project.py
```

No arguments. Output filename is auto-generated.

---

### Functions

---

#### `should_exclude(path: Path) -> bool`

**Purpose:** Determine whether a given relative file path should be omitted
from the archive.

**Exclusion rules (evaluated in order):**

| Rule | Examples |
|---|---|
| Any path component starts with `.` | `.git/`, `.venv/`, `.gitignore` |
| Any path component is in `exclude_dirs` | `build/`, `__pycache__/` |
| Filename is in `exclude_files` | `uv.lock` |
| File extension is in `exclude_extensions` | `.aux`, `.log`, `.synctex.gz`, `.cache`, `.zip`, `.pyc` |
| Filename ends with `.synctex.gz` | (belt-and-suspenders for multi-part extension) |

**Output:** `True` if the path should be excluded, `False` if it should be archived.

---

#### `create_zip(output_name: str | None = None) -> Path`

**Purpose:** Walk the project tree, filter files through `should_exclude`,
and write a deflate-compressed zip archive.

**Inputs:**

| Parameter | Type | Description |
|---|---|---|
| `output_name` | `str \| None` | Filename for the archive. Auto-generated if `None`. |

**Default filename format:** `texport-YYYY-Mon-DD_HHMMSS.zip`
(e.g. `texport-2026-Jan-21_071540.zip`)

**Behavior:**
- `project_root` is the directory containing `zip_project.py` itself
  (`Path(__file__).parent`), making the script location-independent.
- Archive paths are relative to `project_root` (no leading slash).
- Output file is written into `project_root`.
- Prints each added file and the final archive path to stdout.

**Output:** `Path` object pointing to the created `.zip` file.

---

## 7. End-to-End Pipeline

### Standard Workflow

```
# Step 1 — Convert LaTeX files to HTML + PDF, post-process HTML
uv run texport tex_src/lecture1.tex tex_src/lecture2.tex

# Step 2 — Build the navigable index page
uv run texport-index

# Step 3 — (Optional) Bundle a document into a standalone file
uv run embed_assets.py output/lecture1/index.html
```

### Project Layout (static assets and bindings)

```
texport/
├── static/                     ← source for shared web assets (maintained by hand)
│   ├── css/
│   │   └── custom.css
│   └── js/
│       ├── custom.js           ← toolbar, go-to-top, i18n via window.texportI18n
│       └── mathjax-config.js
├── latexml/                    ← LaTeXML binding files (.ltxml); all loaded automatically
│   ├── amsmath-compat.ltxml    ← stubs for amsmath internal commands
│   └── emph-in-math.ltxml      ← redefines \emph as \mathit inside math mode
└── templates/
    └── main_index_template.html  ← uses {lang},{title},{description},{heading},{contents_label},{links}
```

### Per-Document Output Layout

```
output/                         ← seeded from static/ on every texport run
├── index.html                  ← generated by texport-index
├── css/
│   └── custom.css              ← copied from static/css/
├── js/
│   ├── custom.js               ← copied from static/js/
│   └── mathjax-config.js
└── {stem}/
    ├── index.html              ← HTML from latexmlc, post-processed
    └── {stem}.pdf              ← PDF from pdflatex
```

### Dry-Run Mode

`main.py` supports `--dry-run` / `-n`. In this mode:
- No files are read, written, or deleted.
- No external commands (`latexmlc`, `pdflatex`) are executed.
- All intended actions are logged with a `[DRY-RUN]` prefix.
- The exit code is always `0`.

---

## 8. Dependencies & Environment

### Runtime Requirements

| Dependency | Version | Purpose |
|---|---|---|
| Python | ≥ 3.12 | Language runtime |
| `beautifulsoup4` | ≥ 4.14.3 | HTML parsing and manipulation |
| `latexmlc` | system | LaTeX → HTML5 conversion |
| `pdflatex` | system | LaTeX → PDF compilation |
| `bibtex` | system | Bibliography processing (traditional; auto-detected) |
| `biber` | system | Bibliography processing (biblatex; auto-detected) |

### Standard Library Modules Used

| Module | Used In |
|---|---|
| `argparse` | `main.py`, `create_main_index.py`, `embed_assets.py` |
| `html` | `create_main_index.py` |
| `logging` | `main.py`, `create_main_index.py` |
| `pathlib.Path` | all modules |
| `re` | `main.py` |
| `shlex` | `main.py` |
| `shutil` | `main.py` |
| `subprocess` | `main.py` |
| `sys` | `main.py`, `embed_assets.py` |
| `textwrap` | `main.py` |
| `urllib.request`, `urllib.error` | `embed_assets.py` |
| `zipfile` | `zip_project.py` |
| `datetime` | `zip_project.py` |

### LaTeXML Bindings

Custom `.ltxml` binding files live in `latexml/` and are **all loaded
automatically** via `--preload` on every `latexmlc` invocation (sorted
alphabetically, so load order is deterministic). Adding a new `.ltxml` file
to `latexml/` is sufficient — no changes to `main.py` are needed.

| File | Purpose |
|---|---|
| `amsmath-compat.ltxml` | Perl-level no-op stubs for amsmath internal commands (e.g. `\ctagsplit@true`) that LaTeXML cannot resolve, preventing "undefined macro" errors. Uses `DefMacroI` to bypass catcode restrictions. |
| `emph-in-math.ltxml` | Redefines `\emph{…}` as `\mathit{…}` inside math mode, `\textit{…}` elsewhere. Uses the Perl-level `AtBeginDocument` hook so the override fires after all packages (including those that define `\emph`) are loaded. |

### Package Management

Dependencies are managed with [uv](https://docs.astral.sh/uv/).
Use `uv sync` to install dependencies, then `uv pip install -e .` to register
the CLI entry points (`texport`, `texport-index`). Use `uv run <command>` to
execute commands inside the managed virtual environment.