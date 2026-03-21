"""Tests for create_main_index.py — index page generator."""

from pathlib import Path

from config import ENCODING
from create_main_index import (
    create_main_index_page,
    discover_index_files,
    generate_links_html,
    get_link_to_pdf,
    link_to_page,
    read_file_content,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_html(path: Path, title: str, body: str = "<p>Content</p>") -> None:
    """Write a minimal HTML file with the given title."""
    _ = path.write_text(
        f"<html><head><title>{title}</title></head><body>{body}</body></html>",
        encoding=ENCODING,
    )


def write_template(path: Path, content: str = "<ul>{links}</ul>") -> None:
    """Write an index template file."""
    _ = path.write_text(content, encoding=ENCODING)


# ---------------------------------------------------------------------------
# read_file_content
# ---------------------------------------------------------------------------


class TestReadFileContent:
    def test_reads_text_from_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.txt"
        _ = f.write_text("hello world", encoding=ENCODING)
        assert read_file_content(f) == "hello world"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.txt"
        _ = f.write_text("string path test", encoding=ENCODING)
        assert read_file_content(str(f)) == "string path test"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        result = read_file_content(tmp_path / "nonexistent.txt")
        assert result is None

    def test_returns_empty_string_for_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        _ = f.write_text("", encoding=ENCODING)
        assert read_file_content(f) == ""

    def test_preserves_multiline_content(self, tmp_path: Path) -> None:
        content = "line one\nline two\nline three"
        f = tmp_path / "multi.txt"
        _ = f.write_text(content, encoding=ENCODING)
        assert read_file_content(f) == content


# ---------------------------------------------------------------------------
# get_link_to_pdf
# ---------------------------------------------------------------------------


class TestGetLinkToPdf:
    def test_returns_pdf_anchor_when_pdf_exists(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "lecture1"
        doc_dir.mkdir()
        _ = (doc_dir / "lecture1.pdf").write_bytes(b"%PDF-1.4 fake")

        result = get_link_to_pdf(doc_dir, tmp_path)

        assert "PDF" in result
        assert "<a " in result
        assert "lecture1" in result

    def test_pdf_href_is_relative_to_root(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "lecture1"
        doc_dir.mkdir()
        _ = (doc_dir / "lecture1.pdf").write_bytes(b"%PDF-1.4 fake")

        result = get_link_to_pdf(doc_dir, tmp_path)

        # Must NOT be an absolute filesystem path
        assert str(tmp_path) not in result
        # Must contain the relative path components
        assert "lecture1/lecture1.pdf" in result or "lecture1" in result

    def test_returns_empty_string_when_no_pdf(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "lecture1"
        doc_dir.mkdir()

        result = get_link_to_pdf(doc_dir, tmp_path)

        assert result == ""

    def test_returns_link_for_any_pdf_in_directory(self, tmp_path: Path) -> None:
        """Any PDF in the directory is linked, regardless of filename."""
        doc_dir = tmp_path / "topology-notes"
        doc_dir.mkdir()
        _ = (doc_dir / "main.pdf").write_bytes(b"fake")

        result = get_link_to_pdf(doc_dir, tmp_path)

        assert "PDF" in result
        assert "main.pdf" in result

    def test_correct_pdf_name_is_found(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "topology-notes"
        doc_dir.mkdir()
        _ = (doc_dir / "topology-notes.pdf").write_bytes(b"fake")

        result = get_link_to_pdf(doc_dir, tmp_path)

        assert "PDF" in result


# ---------------------------------------------------------------------------
# link_to_page
# ---------------------------------------------------------------------------


class TestLinkToPage:
    def test_returns_li_element(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "lecture1"
        doc_dir.mkdir()

        result = link_to_page(doc_dir, "Lecture 1", tmp_path)

        assert result.strip().startswith("<li>")
        assert result.strip().endswith("</li>")

    def test_contains_relative_href(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "lecture1"
        doc_dir.mkdir()

        result = link_to_page(doc_dir, "Lecture 1", tmp_path)

        assert 'href="lecture1/"' in result

    def test_contains_title_text(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "lecture1"
        doc_dir.mkdir()

        result = link_to_page(doc_dir, "Introduction to Topology", tmp_path)

        assert "Introduction to Topology" in result

    def test_html_escapes_title(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()

        result = link_to_page(doc_dir, "<script>alert('xss')</script>", tmp_path)

        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_html_escapes_ampersand_in_title(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()

        result = link_to_page(doc_dir, "Cats & Dogs", tmp_path)

        assert "Cats & Dogs" not in result
        assert "Cats &amp; Dogs" in result

    def test_includes_pdf_link_when_pdf_exists(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "lecture1"
        doc_dir.mkdir()
        _ = (doc_dir / "lecture1.pdf").write_bytes(b"fake")

        result = link_to_page(doc_dir, "Lecture 1", tmp_path)

        assert "PDF" in result
        assert result.count("<a ") == 2  # one for page, one for PDF

    def test_no_pdf_link_when_pdf_absent(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "lecture1"
        doc_dir.mkdir()

        result = link_to_page(doc_dir, "Lecture 1", tmp_path)

        assert result.count("<a ") == 1  # only the page link

    def test_ends_with_newline(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()

        result = link_to_page(doc_dir, "Doc", tmp_path)

        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# discover_index_files
# ---------------------------------------------------------------------------


class TestDiscoverIndexFiles:
    def test_finds_index_html_in_subdirectory(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "doc1"
        doc_dir.mkdir()
        write_html(doc_dir / "index.html", "Doc One")

        results = discover_index_files(tmp_path)

        assert len(results) == 1
        directory, title = results[0]
        assert directory == doc_dir
        assert title == "Doc One"

    def test_skips_root_index_html(self, tmp_path: Path) -> None:
        """The main index.html at root should not appear in results."""
        write_html(tmp_path / "index.html", "Main Index")
        doc_dir = tmp_path / "doc1"
        doc_dir.mkdir()
        write_html(doc_dir / "index.html", "Doc One")

        results = discover_index_files(tmp_path)

        titles = [t for _, t in results]
        assert "Main Index" not in titles
        assert "Doc One" in titles

    def test_falls_back_to_no_title_when_title_absent(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "doc1"
        doc_dir.mkdir()
        _ = (doc_dir / "index.html").write_text(
            "<html><body><p>No title tag</p></body></html>",
            encoding=ENCODING,
        )

        results = discover_index_files(tmp_path)

        assert len(results) == 1
        assert results[0][1] == "No Title"

    def test_finds_multiple_documents(self, tmp_path: Path) -> None:
        for name in ("alpha", "beta", "gamma"):
            d = tmp_path / name
            d.mkdir()
            write_html(d / "index.html", name.capitalize())

        results = discover_index_files(tmp_path)

        assert len(results) == 3
        titles = {t for _, t in results}
        assert titles == {"Alpha", "Beta", "Gamma"}

    def test_returns_empty_list_when_no_documents(self, tmp_path: Path) -> None:
        results = discover_index_files(tmp_path)
        assert results == []

    def test_returns_list_of_tuples(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "doc1"
        doc_dir.mkdir()
        write_html(doc_dir / "index.html", "Doc")

        results = discover_index_files(tmp_path)

        assert isinstance(results, list)
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 2

    def test_directory_in_result_is_parent_of_index(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "my-doc"
        doc_dir.mkdir()
        write_html(doc_dir / "index.html", "My Doc")

        directory, _ = discover_index_files(tmp_path)[0]

        assert directory == doc_dir
        assert directory.is_dir()


# ---------------------------------------------------------------------------
# generate_links_html
# ---------------------------------------------------------------------------


class TestGenerateLinksHtml:
    def test_returns_empty_string_for_empty_input(self, tmp_path: Path) -> None:
        result = generate_links_html([], tmp_path)
        assert result == ""

    def test_returns_li_elements_for_each_document(self, tmp_path: Path) -> None:
        docs: list[tuple[Path, str]] = []
        for name in ("doc1", "doc2"):
            d = tmp_path / name
            d.mkdir()
            docs.append((d, name.upper()))

        result = generate_links_html(docs, tmp_path)

        assert result.count("<li>") == 2
        assert "DOC1" in result
        assert "DOC2" in result

    def test_concatenates_results_without_separator(self, tmp_path: Path) -> None:
        doc = tmp_path / "only"
        doc.mkdir()
        result = generate_links_html([(doc, "Only Doc")], tmp_path)

        # Should be a plain string of <li>...</li>, not wrapped in <ul>
        assert result.startswith("<li>")
        assert "</li>" in result


# ---------------------------------------------------------------------------
# create_main_index_page
# ---------------------------------------------------------------------------


class TestCreateMainIndexPage:
    def test_creates_index_html_at_root(self, tmp_path: Path) -> None:
        template = tmp_path / "template.html"
        write_template(template)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        create_main_index_page(output_dir, template)

        assert (output_dir / "index.html").exists()

    def test_index_contains_document_titles(self, tmp_path: Path) -> None:
        template = tmp_path / "template.html"
        write_template(template)
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        doc_dir = output_dir / "lecture1"
        doc_dir.mkdir()
        write_html(doc_dir / "index.html", "Lecture One")

        create_main_index_page(output_dir, template)

        content = (output_dir / "index.html").read_text(encoding=ENCODING)
        assert "Lecture One" in content

    def test_index_uses_template_structure(self, tmp_path: Path) -> None:
        template = tmp_path / "template.html"
        _ = template.write_text(
            "<!DOCTYPE html><html><body><nav>{links}</nav></body></html>",
            encoding=ENCODING,
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        create_main_index_page(output_dir, template)

        content = (output_dir / "index.html").read_text(encoding=ENCODING)
        assert "<nav>" in content

    def test_index_with_no_documents_is_still_created(self, tmp_path: Path) -> None:
        template = tmp_path / "template.html"
        write_template(template)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        create_main_index_page(output_dir, template)

        assert (output_dir / "index.html").exists()
        content = (output_dir / "index.html").read_text(encoding=ENCODING)
        assert "<ul></ul>" in content

    def test_aborts_gracefully_when_template_missing(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Should not raise; should log an error and return
        create_main_index_page(output_dir, tmp_path / "nonexistent_template.html")

        # No index.html should be created
        assert not (output_dir / "index.html").exists()

    def test_index_contains_pdf_links_when_pdfs_exist(self, tmp_path: Path) -> None:
        template = tmp_path / "template.html"
        write_template(template)
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        doc_dir = output_dir / "lecture1"
        doc_dir.mkdir()
        write_html(doc_dir / "index.html", "Lecture One")
        _ = (doc_dir / "lecture1.pdf").write_bytes(b"fake pdf")

        create_main_index_page(output_dir, template)

        content = (output_dir / "index.html").read_text(encoding=ENCODING)
        assert "PDF" in content

    def test_index_links_are_relative(self, tmp_path: Path) -> None:
        template = tmp_path / "template.html"
        write_template(template)
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        doc_dir = output_dir / "doc1"
        doc_dir.mkdir()
        write_html(doc_dir / "index.html", "Doc One")

        create_main_index_page(output_dir, template)

        content = (output_dir / "index.html").read_text(encoding=ENCODING)
        # Must NOT contain absolute filesystem paths
        assert str(output_dir) not in content

    def test_multiple_documents_all_appear_in_index(self, tmp_path: Path) -> None:
        template = tmp_path / "template.html"
        write_template(template)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        titles = ["Alpha Notes", "Beta Notes", "Gamma Notes"]
        for title in titles:
            slug = title.lower().replace(" ", "-")
            d = output_dir / slug
            d.mkdir()
            write_html(d / "index.html", title)

        create_main_index_page(output_dir, template)

        content = (output_dir / "index.html").read_text(encoding=ENCODING)
        for title in titles:
            assert title in content