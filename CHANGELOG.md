# Changelog

All notable changes to latexport are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [CalVer](https://calver.org/): `YYYY.MM.micro`.

---

## 2026.3.2 — 2026-03-21

### Added
- Live example demos published to GitHub Pages at https://kalv25.github.io/latexport/.
- GitHub Actions workflow (`deploy-pages.yml`) to auto-deploy `examples/output` on every push to `main`.

---

## 2026.3.0 — 2026-03-21

### Added
- Initial public release.
- `latexport` CLI: converts `.tex` files to HTML (via LaTeXML) and PDF (via pdflatex) in one command.
- `latexport-index` CLI: generates a navigable main index page over all output documents.
- `latexport-clean` CLI: removes stray `latexml.log` files.
- `latexport-bundle` CLI: bundles an HTML file with all CSS/JS inlined for offline use.
- Automatic bibliography detection and pre-processing (`bibtex`/`biber`) so LaTeXML HTML resolves citations correctly.
- LaTeXML custom bindings: `amsmath-compat.ltxml` (stubs for internal amsmath commands), `emph-in-math.ltxml` (redefines `\emph` as `\mathit` inside math mode).
- Accessible UI enhancements: configurable page width (slider, saved to `localStorage`), MathJax on/off toggle, go-to-top button — all dark-mode compatible.
- Toolbar i18n via `window.latexportI18n` override object.
- Index template i18n via keyword arguments to `create_main_index_page`.
- `[tool.latexport]` support in `pyproject.toml` for project-level configuration (`output_dir`, `static_dir`, `src_qed_symbol`).
- CalVer versioning (`YYYY.MM.micro`).
