"""Tests for main.py — LaTeX processor and HTML post-processor."""

import logging
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from latexport.config import ENCODING, SRC_QED_SYMBOL
from latexport.main import (
    _create_include_subdirs,  # pyright: ignore[reportPrivateUsage]
    _detect_bibliography,  # pyright: ignore[reportPrivateUsage]
    _has_cite_commands,  # pyright: ignore[reportPrivateUsage]
    _inject_resources,  # pyright: ignore[reportPrivateUsage]
    _remove_empty_subdirs,  # pyright: ignore[reportPrivateUsage]
    _seed_output_dir,  # pyright: ignore[reportPrivateUsage]
    add_custom_css_and_js,
    process_file,
    replace_qed_symbol,
    update_stylesheet_links,
)

# ---------------------------------------------------------------------------
# Shared HTML fixtures
# ---------------------------------------------------------------------------

MINIMAL_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body><p>Content</p></body>
</html>"""

HTML_WITH_QED = """\
<!DOCTYPE html>
<html>
<head><title>Proof</title></head>
<body><p>Proof complete.\u220e</p></body>
</html>"""

HTML_NO_HEAD = "<html><body><p>No head element here</p></body></html>"


# ---------------------------------------------------------------------------
# replace_qed_symbol
# ---------------------------------------------------------------------------


class TestReplaceQedSymbol:
    def test_replaces_symbol_with_accessible_spans(self):
        content = f"Proof complete. {SRC_QED_SYMBOL}"
        result = replace_qed_symbol(content)
        assert SRC_QED_SYMBOL not in result.split('<span')[0]
        assert 'class="qed"' in result
        assert 'aria-hidden="true"' in result
        assert 'class="visually-hidden"' in result
        assert "End of proof" in result

    def test_returns_string_unchanged_when_no_symbol_present(self):
        content = "A proof with no QED symbol."
        result = replace_qed_symbol(content)
        assert result == content

    def test_replaces_all_occurrences(self):
        content = f"{SRC_QED_SYMBOL} first proof. {SRC_QED_SYMBOL} second proof."
        result = replace_qed_symbol(content)
        assert result.count('class="qed"') == 2
        assert result.count("End of proof") == 2

    def test_replacement_contains_qed_character_for_display(self):
        """The visual ∎ character must survive inside the replacement span."""
        result = replace_qed_symbol(f"End. {SRC_QED_SYMBOL}")
        assert "\u220e" in result  # character still present inside the new span

    def test_empty_string_returns_empty_string(self):
        assert replace_qed_symbol("") == ""

    def test_returns_str(self):
        result = replace_qed_symbol(f"ok {SRC_QED_SYMBOL}")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _inject_resources
# ---------------------------------------------------------------------------


class TestInjectResources:
    def _make_soup(self, html: str = MINIMAL_HTML) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def test_injects_custom_css_link(self):
        soup = self._make_soup()
        _inject_resources(soup)
        assert soup.find("link", href="../css/custom.css") is not None

    def test_injects_custom_js_script(self):
        soup = self._make_soup()
        _inject_resources(soup)
        assert soup.find("script", src="../js/custom.js") is not None

    def test_injects_mathjax_config_script(self):
        soup = self._make_soup()
        _inject_resources(soup)
        assert soup.find("script", src="../js/mathjax-config.js") is not None

    def test_injects_mathjax_cdn_script(self):
        soup = self._make_soup()
        _inject_resources(soup)
        cdn = "https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js"
        assert soup.find("script", src=cdn) is not None

    def test_injects_exactly_four_new_tags(self):
        soup = self._make_soup()
        head = soup.head
        assert head is not None
        before = len(head.find_all(True))
        _inject_resources(soup)
        after = len(head.find_all(True))
        assert after - before == 4  # 1 <link> + 3 <script>

    def test_idempotent_does_not_duplicate_css_link(self):
        soup = self._make_soup()
        _inject_resources(soup)
        _inject_resources(soup)
        links = soup.find_all("link", href="../css/custom.css")
        assert len(links) == 1

    def test_idempotent_does_not_duplicate_js_scripts(self):
        soup = self._make_soup()
        _inject_resources(soup)
        _inject_resources(soup)
        scripts = soup.find_all("script", src="../js/custom.js")
        assert len(scripts) == 1

    def test_all_scripts_have_defer_attribute(self):
        soup = self._make_soup()
        _inject_resources(soup)
        for src in (
            "../js/custom.js",
            "../js/mathjax-config.js",
            "https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js",
        ):
            script = soup.find("script", src=src)
            assert script is not None
            assert script.has_attr("defer"), f"<script src='{src}'> missing defer"


# ---------------------------------------------------------------------------
# add_custom_css_and_js
# ---------------------------------------------------------------------------


class TestAddCustomCssAndJs:
    def test_dry_run_returns_true_without_touching_file(self, tmp_path: Path):
        target = tmp_path / "index.html"
        # File does not need to exist for dry-run
        result = add_custom_css_and_js(str(target), dry_run=True)
        assert result is True
        assert not target.exists()

    def test_dry_run_prints_dry_run_prefix(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.INFO, logger="latexport.main"):
            _ = add_custom_css_and_js(str(tmp_path / "x.html"), dry_run=True)
        assert "[DRY-RUN]" in caplog.text

    def test_missing_file_returns_false(self, tmp_path: Path):
        result = add_custom_css_and_js(str(tmp_path / "missing.html"))
        assert result is False

    def test_missing_file_prints_to_stderr(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.ERROR, logger="latexport.main"):
            _ = add_custom_css_and_js(str(tmp_path / "missing.html"))
        assert caplog.records

    def test_html_without_head_returns_false(self, tmp_path: Path):
        f = tmp_path / "nohead.html"
        _ = f.write_text(HTML_NO_HEAD, encoding=ENCODING)
        result = add_custom_css_and_js(str(f))
        assert result is False

    def test_valid_html_returns_true(self, tmp_path: Path):
        f = tmp_path / "index.html"
        _ = f.write_text(MINIMAL_HTML, encoding=ENCODING)
        result = add_custom_css_and_js(str(f))
        assert result is True

    def test_injects_css_link_into_file(self, tmp_path: Path):
        f = tmp_path / "index.html"
        _ = f.write_text(MINIMAL_HTML, encoding=ENCODING)
        _ = add_custom_css_and_js(str(f))
        assert "../css/custom.css" in f.read_text(encoding=ENCODING)

    def test_injects_js_scripts_into_file(self, tmp_path: Path):
        f = tmp_path / "index.html"
        _ = f.write_text(MINIMAL_HTML, encoding=ENCODING)
        _ = add_custom_css_and_js(str(f))
        content = f.read_text(encoding=ENCODING)
        assert "../js/custom.js" in content
        assert "../js/mathjax-config.js" in content

    def test_replaces_qed_symbol_in_file(self, tmp_path: Path):
        f = tmp_path / "index.html"
        _ = f.write_text(HTML_WITH_QED, encoding=ENCODING)
        _ = add_custom_css_and_js(str(f))
        content = f.read_text(encoding=ENCODING)
        assert 'class="qed"' in content
        assert "End of proof" in content

    def test_dry_run_does_not_modify_file(self, tmp_path: Path):
        f = tmp_path / "index.html"
        _ = f.write_text(MINIMAL_HTML, encoding=ENCODING)
        _ = add_custom_css_and_js(str(f), dry_run=True)
        assert f.read_text(encoding=ENCODING) == MINIMAL_HTML

    def test_is_idempotent(self, tmp_path: Path):
        """Running twice should not inject duplicate resource tags."""
        f = tmp_path / "index.html"
        _ = f.write_text(MINIMAL_HTML, encoding=ENCODING)
        _ = add_custom_css_and_js(str(f))
        _ = add_custom_css_and_js(str(f))
        content = f.read_text(encoding=ENCODING)
        assert content.count("../css/custom.css") == 1
        assert content.count("../js/custom.js") == 1


# ---------------------------------------------------------------------------
# update_stylesheet_links
# ---------------------------------------------------------------------------


class TestUpdateStylesheetLinks:
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _html_with_links(*hrefs: str) -> str:
        link_tags = "\n".join(
            f'<link rel="stylesheet" href="{href}">' for href in hrefs
        )
        return (
            f"<!DOCTYPE html>\n<html>\n<head><title>T</title>\n"
            f"{link_tags}\n</head>\n<body></body>\n</html>"
        )

    @staticmethod
    def _make_doc_dir(tmp_path: Path) -> tuple[Path, Path]:
        """Return (doc_dir, css_dir) with both created."""
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()
        css_dir = tmp_path / "css"
        css_dir.mkdir()
        return doc_dir, css_dir

    # ------------------------------------------------------------------
    # Error / edge cases
    # ------------------------------------------------------------------

    def test_missing_html_file_returns_empty_list(self, tmp_path: Path):
        result = update_stylesheet_links(tmp_path / "nope.html", tmp_path / "css")
        assert result == []

    def test_no_stylesheet_links_returns_empty_list(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        f = doc_dir / "index.html"
        _ = f.write_text(MINIMAL_HTML, encoding=ENCODING)
        result = update_stylesheet_links(f, css_dir)
        assert result == []

    # ------------------------------------------------------------------
    # Skipping rules
    # ------------------------------------------------------------------

    def test_skips_http_external_urls(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        _ = (css_dir / "style.css").write_text("", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(
            self._html_with_links("https://example.com/style.css"),
            encoding=ENCODING,
        )
        result = update_stylesheet_links(f, css_dir)
        assert result == []

    def test_skips_protocol_relative_urls(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        _ = (css_dir / "style.css").write_text("", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(
            self._html_with_links("//cdn.example.com/style.css"),
            encoding=ENCODING,
        )
        result = update_stylesheet_links(f, css_dir)
        assert result == []

    def test_skips_already_redirected_links(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        f = doc_dir / "index.html"
        _ = f.write_text(
            self._html_with_links("../css/already.css"), encoding=ENCODING
        )
        result = update_stylesheet_links(f, css_dir)
        assert result == []

    def test_skips_css_absent_from_shared_folder(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        # Local CSS exists but NOT in the shared css/ folder
        _ = (doc_dir / "orphan.css").write_text("", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(self._html_with_links("orphan.css"), encoding=ENCODING)
        result = update_stylesheet_links(f, css_dir)
        assert result == []

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_updates_href_to_shared_css_folder(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        _ = (css_dir / "style.css").write_text("body {}", encoding=ENCODING)
        _ = (doc_dir / "style.css").write_text("body {}", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(self._html_with_links("style.css"), encoding=ENCODING)

        _ = update_stylesheet_links(f, css_dir)

        content = f.read_text(encoding=ENCODING)
        assert "../css/style.css" in content

    def test_returns_list_of_updated_filenames(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        _ = (css_dir / "style.css").write_text("", encoding=ENCODING)
        _ = (doc_dir / "style.css").write_text("", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(self._html_with_links("style.css"), encoding=ENCODING)

        result = update_stylesheet_links(f, css_dir)
        assert "style.css" in result

    def test_deletes_local_css_after_redirect(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        local_css = doc_dir / "style.css"
        _ = local_css.write_text("body {}", encoding=ENCODING)
        _ = (css_dir / "style.css").write_text("body {}", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(self._html_with_links("style.css"), encoding=ENCODING)

        _ = update_stylesheet_links(f, css_dir)

        assert not local_css.exists()

    def test_updates_multiple_stylesheet_links(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        for name in ("a.css", "b.css"):
            _ = (css_dir / name).write_text("", encoding=ENCODING)
            _ = (doc_dir / name).write_text("", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(self._html_with_links("a.css", "b.css"), encoding=ENCODING)

        result = update_stylesheet_links(f, css_dir)

        assert "a.css" in result
        assert "b.css" in result
        content = f.read_text(encoding=ENCODING)
        assert "../css/a.css" in content
        assert "../css/b.css" in content

    # ------------------------------------------------------------------
    # Dry-run
    # ------------------------------------------------------------------

    def test_dry_run_does_not_modify_html_file(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        _ = (css_dir / "style.css").write_text("", encoding=ENCODING)
        _ = (doc_dir / "style.css").write_text("", encoding=ENCODING)
        original = self._html_with_links("style.css")
        f = doc_dir / "index.html"
        _ = f.write_text(original, encoding=ENCODING)

        _ = update_stylesheet_links(f, css_dir, dry_run=True)

        assert f.read_text(encoding=ENCODING) == original

    def test_dry_run_does_not_delete_local_css(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        local_css = doc_dir / "style.css"
        _ = local_css.write_text("", encoding=ENCODING)
        _ = (css_dir / "style.css").write_text("", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(self._html_with_links("style.css"), encoding=ENCODING)

        _ = update_stylesheet_links(f, css_dir, dry_run=True)

        assert local_css.exists()

    def test_dry_run_still_returns_would_be_updated_filenames(self, tmp_path: Path):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        _ = (css_dir / "style.css").write_text("", encoding=ENCODING)
        _ = (doc_dir / "style.css").write_text("", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(self._html_with_links("style.css"), encoding=ENCODING)

        result = update_stylesheet_links(f, css_dir, dry_run=True)
        assert "style.css" in result

    def test_dry_run_prints_dry_run_prefix(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        doc_dir, css_dir = self._make_doc_dir(tmp_path)
        _ = (css_dir / "style.css").write_text("", encoding=ENCODING)
        f = doc_dir / "index.html"
        _ = f.write_text(self._html_with_links("style.css"), encoding=ENCODING)

        with caplog.at_level(logging.INFO, logger="latexport.main"):
            _ = update_stylesheet_links(f, css_dir, dry_run=True)
        assert "[DRY-RUN]" in caplog.text


# ---------------------------------------------------------------------------
# process_file
# ---------------------------------------------------------------------------


class TestProcessFile:
    def test_dry_run_returns_true(self):
        result = process_file("echo hello", dry_run=True)
        assert result is True

    def test_dry_run_prints_dry_run_prefix_and_command(self, caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.INFO, logger="latexport.main"):
            _ = process_file("echo hello world", dry_run=True)
        assert "[DRY-RUN]" in caplog.text
        assert "echo hello world" in caplog.text

    def test_dry_run_does_not_run_subprocess(self):
        with patch("subprocess.run") as mock_run:
            _ = process_file("echo hello", dry_run=True)
            mock_run.assert_not_called()

    def test_successful_command_returns_true(self):
        result = process_file("echo hello")
        assert result is True

    def test_failed_command_returns_false(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["failing_cmd", "--arg"], returncode=1, stdout="", stderr="something went wrong"
            )
            result = process_file("failing_cmd --arg")
        assert result is False

    def test_failed_command_prints_stderr_output(self, caplog: pytest.LogCaptureFixture):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["failing_cmd"], returncode=1, stdout="", stderr="detailed error text"
            )
            with caplog.at_level(logging.ERROR, logger="latexport.main"):
                _ = process_file("failing_cmd")
        assert "detailed error text" in caplog.text

    def test_missing_binary_returns_false(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = process_file("binary_that_does_not_exist --flag")
        assert result is False

    def test_missing_binary_prints_advisory_to_stderr(self, caplog: pytest.LogCaptureFixture):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with caplog.at_level(logging.ERROR, logger="latexport.main"):
                _ = process_file("binary_that_does_not_exist")
        assert "not found" in caplog.text

    def test_command_is_split_and_passed_to_subprocess(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["latexmlc", "--format=html5", "input.tex"], returncode=0, stdout="", stderr=""
            )
            _ = process_file("latexmlc --format=html5 input.tex")
            call_args, _ = mock_run.call_args  # pyright: ignore[reportAny]
            assert call_args[0] == ["latexmlc", "--format=html5", "input.tex"]


# ---------------------------------------------------------------------------
# _detect_bibliography
# ---------------------------------------------------------------------------

class TestDetectBibliography:
    def _tex(self, tmp_path: Path, content: str) -> Path:
        f = tmp_path / "doc.tex"
        f.write_text(content, encoding="utf-8")
        return f

    def test_returns_biber_for_biblatex_package(self, tmp_path):
        f = self._tex(tmp_path, r"\usepackage{biblatex}")
        assert _detect_bibliography(f) == "biber"

    def test_returns_biber_for_biblatex_with_options(self, tmp_path):
        f = self._tex(tmp_path, r"\usepackage[backend=biber]{biblatex}")
        assert _detect_bibliography(f) == "biber"

    def test_returns_biber_for_addbibresource(self, tmp_path):
        f = self._tex(tmp_path, r"\addbibresource{refs.bib}")
        assert _detect_bibliography(f) == "biber"

    def test_returns_bibtex_for_bibliography_command(self, tmp_path):
        f = self._tex(tmp_path, r"\bibliography{refs}")
        assert _detect_bibliography(f) == "bibtex"

    def test_returns_none_when_no_bibliography(self, tmp_path):
        f = self._tex(tmp_path, r"\section{Intro} No bibliography here.")
        assert _detect_bibliography(f) is None

    def test_returns_none_on_oserror(self, tmp_path):
        assert _detect_bibliography(tmp_path / "nonexistent.tex") is None

    def test_biblatex_takes_priority_over_bibliography(self, tmp_path):
        # Both \usepackage{biblatex} and \bibliography present — biber wins (first match)
        f = self._tex(tmp_path, "\\usepackage{biblatex}\n\\bibliography{refs}")
        assert _detect_bibliography(f) == "biber"


# ---------------------------------------------------------------------------
# _has_cite_commands
# ---------------------------------------------------------------------------

class TestHasCiteCommands:
    def _tex(self, tmp_path: Path, content: str) -> Path:
        f = tmp_path / "doc.tex"
        f.write_text(content, encoding="utf-8")
        return f

    def test_returns_true_for_cite(self, tmp_path):
        assert _has_cite_commands(self._tex(tmp_path, r"\cite{key}"))

    def test_returns_true_for_citep(self, tmp_path):
        assert _has_cite_commands(self._tex(tmp_path, r"\citep{key}"))

    def test_returns_true_for_parencite(self, tmp_path):
        assert _has_cite_commands(self._tex(tmp_path, r"\parencite{key}"))

    def test_returns_true_for_textcite(self, tmp_path):
        assert _has_cite_commands(self._tex(tmp_path, r"\textcite{key}"))

    def test_returns_true_for_footcite(self, tmp_path):
        assert _has_cite_commands(self._tex(tmp_path, r"\footcite{key}"))

    def test_returns_true_for_autocite(self, tmp_path):
        assert _has_cite_commands(self._tex(tmp_path, r"\autocite{key}"))

    def test_returns_true_for_cite_with_optional_arg(self, tmp_path):
        assert _has_cite_commands(self._tex(tmp_path, r"\cite[p.~5]{key}"))

    def test_returns_false_for_inline_bibliography(self, tmp_path):
        content = "\\begin{thebibliography}{99}\n\\bibitem{key} Author.\n\\end{thebibliography}"
        assert not _has_cite_commands(self._tex(tmp_path, content))

    def test_returns_false_when_no_cite_commands(self, tmp_path):
        assert not _has_cite_commands(self._tex(tmp_path, r"\section{Intro}"))

    def test_returns_false_on_oserror(self, tmp_path):
        assert not _has_cite_commands(tmp_path / "nonexistent.tex")

    def test_inline_bibliography_overrides_cite_commands(self, tmp_path):
        # \begin{thebibliography} present → always False even with \cite
        content = "\\cite{key}\n\\begin{thebibliography}{99}\\end{thebibliography}"
        assert not _has_cite_commands(self._tex(tmp_path, content))


# ---------------------------------------------------------------------------
# _create_include_subdirs
# ---------------------------------------------------------------------------

class TestCreateIncludeSubdirs:
    def _tex(self, tmp_path: Path, content: str) -> Path:
        f = tmp_path / "main.tex"
        f.write_text(content, encoding="utf-8")
        return f

    def test_creates_subdir_for_include_with_path(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        _create_include_subdirs(self._tex(tmp_path, r"\include{notes/chapter1}"), out)
        assert (out / "notes").is_dir()

    def test_does_not_create_dir_for_flat_include(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        _create_include_subdirs(self._tex(tmp_path, r"\include{chapter1}"), out)
        # No subdirectory should be created (parent is ".")
        assert not (out / "chapter1").exists()

    def test_creates_multiple_subdirs(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        content = "\\include{notes/ch1}\n\\include{appendix/a}"
        _create_include_subdirs(self._tex(tmp_path, content), out)
        assert (out / "notes").is_dir()
        assert (out / "appendix").is_dir()

    def test_handles_missing_tex_file_gracefully(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        # Should not raise
        _create_include_subdirs(tmp_path / "nonexistent.tex", out)

    def test_creates_nested_subdirs(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        _create_include_subdirs(self._tex(tmp_path, r"\include{part1/notes/ch1}"), out)
        assert (out / "part1" / "notes").is_dir()


# ---------------------------------------------------------------------------
# _remove_empty_subdirs
# ---------------------------------------------------------------------------

class TestRemoveEmptySubdirs:
    def test_removes_empty_subdirectory(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        _remove_empty_subdirs(tmp_path)
        assert not empty.exists()

    def test_does_not_remove_non_empty_subdir(self, tmp_path):
        non_empty = tmp_path / "non_empty"
        non_empty.mkdir()
        (non_empty / "file.txt").write_text("data")
        _remove_empty_subdirs(tmp_path)
        assert non_empty.exists()

    def test_removes_nested_empty_subdirs(self, tmp_path):
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        _remove_empty_subdirs(tmp_path)
        assert not (tmp_path / "a").exists()

    def test_does_not_remove_output_dir_itself(self, tmp_path):
        _remove_empty_subdirs(tmp_path)
        assert tmp_path.exists()

    def test_keeps_partially_populated_parent(self, tmp_path):
        parent = tmp_path / "parent"
        parent.mkdir()
        (parent / "file.txt").write_text("data")
        empty_child = parent / "empty"
        empty_child.mkdir()
        _remove_empty_subdirs(tmp_path)
        assert parent.exists()      # not removed — has a file
        assert not empty_child.exists()


# ---------------------------------------------------------------------------
# _seed_output_dir
# ---------------------------------------------------------------------------

class TestSeedOutputDir:
    def test_creates_output_dir_when_missing(self, tmp_path):
        static = tmp_path / "static"
        static.mkdir()
        out = tmp_path / "out"
        _seed_output_dir(out, static)
        assert out.is_dir()

    def test_copies_files_from_static_dir(self, tmp_path):
        static = tmp_path / "static"
        static.mkdir()
        (static / "style.css").write_text("body {}")
        out = tmp_path / "out"
        _seed_output_dir(out, static)
        assert (out / "style.css").read_text() == "body {}"

    def test_copies_subdirectory_structure(self, tmp_path):
        static = tmp_path / "static"
        css = static / "css"
        css.mkdir(parents=True)
        (css / "custom.css").write_text("*{}")
        out = tmp_path / "out"
        _seed_output_dir(out, static)
        assert (out / "css" / "custom.css").read_text() == "*{}"

    def test_does_nothing_when_static_dir_missing(self, tmp_path, caplog):
        out = tmp_path / "out"
        import logging
        with caplog.at_level(logging.WARNING, logger="latexport.main"):
            _seed_output_dir(out, tmp_path / "nonexistent")
        assert not out.exists()

    def test_overwrites_existing_files_on_reseed(self, tmp_path):
        static = tmp_path / "static"
        static.mkdir()
        (static / "style.css").write_text("new content")
        out = tmp_path / "out"
        out.mkdir()
        (out / "style.css").write_text("old content")
        _seed_output_dir(out, static)
        assert (out / "style.css").read_text() == "new content"
