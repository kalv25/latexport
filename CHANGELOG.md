# Changelog

All notable changes to texport are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [CalVer](https://calver.org/): `YYYY.MM.micro`.

---

## 2026.3.0 — 2026-03-21

### Added
- Initial public release.
- `texport` CLI: converts `.tex` files to HTML (via LaTeXML) and PDF (via pdflatex) in one command.
- `texport-index` CLI: generates a navigable main index page over all output documents.
- `texport-clean` CLI: removes stray `latexml.log` files.
- `texport-bundle` CLI: bundles an HTML file with all CSS/JS inlined for offline use.
- Automatic bibliography detection and pre-processing (`bibtex`/`biber`) so LaTeXML HTML resolves citations correctly.
- LaTeXML custom bindings: `amsmath-compat.ltxml` (stubs for internal amsmath commands), `emph-in-math.ltxml` (redefines `\emph` as `\mathit` inside math mode).
- Accessible UI enhancements: configurable page width (slider, saved to `localStorage`), MathJax on/off toggle, go-to-top button — all dark-mode compatible.
- Toolbar i18n via `window.texportI18n` override object.
- Index template i18n via keyword arguments to `create_main_index_page`.
- `[tool.texport]` support in `pyproject.toml` for project-level configuration (`output_dir`, `static_dir`, `src_qed_symbol`).
- CalVer versioning (`YYYY.MM.micro`).
