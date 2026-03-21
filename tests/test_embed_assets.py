"""Tests for embed_assets.py — asset embedder."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup, Tag

from texport.embed_assets import (
    _charset_from_content_type,  # pyright: ignore[reportPrivateUsage]
    _tag_remote_assets,  # pyright: ignore[reportPrivateUsage]
    build_parser,
    embed_scripts,
    embed_stylesheets,
    fetch_asset,
    is_remote,
    resolve_local,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# is_remote
# ---------------------------------------------------------------------------


class TestIsRemote:
    def test_http_url_is_remote(self):
        assert is_remote("http://example.com/style.css") is True

    def test_https_url_is_remote(self):
        assert is_remote("https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js") is True

    def test_relative_path_is_not_remote(self):
        assert is_remote("../css/custom.css") is False

    def test_absolute_local_path_is_not_remote(self):
        assert is_remote("/usr/local/share/style.css") is False

    def test_protocol_relative_url_is_not_remote(self):
        # // URLs do not match http:// or https://, so is_remote returns False
        assert is_remote("//cdn.example.com/style.css") is False

    def test_empty_string_is_not_remote(self):
        assert is_remote("") is False


# ---------------------------------------------------------------------------
# _charset_from_content_type
# ---------------------------------------------------------------------------


class TestCharsetFromContentType:
    def test_returns_charset_from_content_type(self):
        assert _charset_from_content_type("text/css; charset=utf-8") == "utf-8"

    def test_returns_none_when_no_charset(self):
        assert _charset_from_content_type("text/css") is None

    def test_handles_quoted_charset(self):
        assert _charset_from_content_type('text/html; charset="iso-8859-1"') == "iso-8859-1"

    def test_handles_uppercase_charset_key(self):
        # The code lowercases before comparing, so CHARSET= should be handled
        assert _charset_from_content_type("text/css; CHARSET=utf-16") == "utf-16"

    def test_returns_none_for_empty_content_type(self):
        assert _charset_from_content_type("") is None

    def test_handles_extra_whitespace(self):
        # The implementation strips whitespace around the whole "charset=value"
        # token but does NOT support spaces around the "=" sign itself.
        assert _charset_from_content_type("text/css;  charset=utf-8 ") == "utf-8"


# ---------------------------------------------------------------------------
# resolve_local
# ---------------------------------------------------------------------------


class TestResolveLocal:
    def test_relative_href_resolved_against_html_dir(self, tmp_path: Path):
        result = resolve_local("style.css", tmp_path)
        assert result == (tmp_path / "style.css").resolve()

    def test_relative_href_with_subdirectory(self, tmp_path: Path):
        result = resolve_local("../css/custom.css", tmp_path / "doc")
        assert result == (tmp_path / "css" / "custom.css").resolve()

    def test_absolute_href_returned_as_is(self):
        absolute = "/usr/share/css/style.css"
        result = resolve_local(absolute, Path("/some/html/dir"))
        assert result == Path(absolute)


# ---------------------------------------------------------------------------
# fetch_asset
# ---------------------------------------------------------------------------


class TestFetchAsset:
    def test_dispatches_to_read_local_for_relative_path(self, tmp_path: Path):
        css = tmp_path / "style.css"
        _ = css.write_text("body { margin: 0; }", encoding="utf-8")

        result = fetch_asset("style.css", tmp_path)

        assert "margin: 0" in result

    def test_raises_file_not_found_for_missing_local(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            _ = fetch_asset("does_not_exist.css", tmp_path)

    @patch("texport.embed_assets.fetch_remote")
    def test_dispatches_to_fetch_remote_for_http(self, mock_fetch_remote: MagicMock):
        mock_fetch_remote.return_value = "/* remote css */"

        result = fetch_asset("http://example.com/style.css", Path("/irrelevant"))

        mock_fetch_remote.assert_called_once_with("http://example.com/style.css")
        assert result == "/* remote css */"

    @patch("texport.embed_assets.fetch_remote")
    def test_dispatches_to_fetch_remote_for_https(self, mock_fetch_remote: MagicMock):
        mock_fetch_remote.return_value = "var x = 1;"

        _ = fetch_asset("https://cdn.example.com/app.js", Path("/irrelevant"))

        mock_fetch_remote.assert_called_once_with("https://cdn.example.com/app.js")


# ---------------------------------------------------------------------------
# embed_stylesheets
# ---------------------------------------------------------------------------


class TestEmbedStylesheets:
    def test_replaces_link_tag_with_style_tag(self, tmp_path: Path):
        _ = (tmp_path / "style.css").write_text("body { color: red; }", encoding="utf-8")
        soup = make_soup(
            '<html><head><link rel="stylesheet" href="style.css"></head><body></body></html>'
        )

        count = embed_stylesheets(soup, tmp_path)

        assert count == 1
        assert soup.find("link") is None
        style = soup.find("style")
        assert isinstance(style, Tag)
        assert "color: red" in (style.string or "")

    def test_preserves_media_attribute(self, tmp_path: Path):
        _ = (tmp_path / "print.css").write_text("body { color: black; }", encoding="utf-8")
        soup = make_soup(
            "<html><head>"
            + '<link rel="stylesheet" href="print.css" media="print">'
            + "</head><body></body></html>"
        )

        _ = embed_stylesheets(soup, tmp_path)

        style = soup.find("style")
        assert isinstance(style, Tag)
        assert style.get("media") == "print"

    def test_skips_and_warns_on_missing_local_asset(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        soup = make_soup(
            '<html><head><link rel="stylesheet" href="missing.css"></head><body></body></html>'
        )

        count = embed_stylesheets(soup, tmp_path)

        assert count == 0
        # Original <link> tag must remain untouched
        assert soup.find("link") is not None
        assert "WARNING" in capsys.readouterr().out

    def test_skips_tag_with_empty_href(self, tmp_path: Path):
        soup = make_soup(
            '<html><head><link rel="stylesheet" href=""></head><body></body></html>'
        )

        count = embed_stylesheets(soup, tmp_path)

        assert count == 0

    def test_embeds_multiple_stylesheets(self, tmp_path: Path):
        for name in ("a.css", "b.css"):
            _ = (tmp_path / name).write_text(f"/* {name} */", encoding="utf-8")
        soup = make_soup(
            "<html><head>"
            + '<link rel="stylesheet" href="a.css">'
            + '<link rel="stylesheet" href="b.css">'
            + "</head><body></body></html>"
        )

        count = embed_stylesheets(soup, tmp_path)

        assert count == 2
        assert soup.find("link") is None
        assert len(soup.find_all("style")) == 2

    def test_does_not_embed_non_stylesheet_link(self, tmp_path: Path):
        soup = make_soup(
            '<html><head><link rel="icon" href="favicon.ico"></head><body></body></html>'
        )

        count = embed_stylesheets(soup, tmp_path)

        assert count == 0
        assert soup.find("link") is not None


# ---------------------------------------------------------------------------
# embed_scripts
# ---------------------------------------------------------------------------


class TestEmbedScripts:
    def test_replaces_script_src_with_inline_content(self, tmp_path: Path):
        _ = (tmp_path / "app.js").write_text("console.log('hello');", encoding="utf-8")
        soup = make_soup(
            "<html><head>"
            + '<script src="app.js"></script>'
            + "</head><body></body></html>"
        )

        count = embed_scripts(soup, tmp_path)

        assert count == 1
        script = soup.find("script")
        assert isinstance(script, Tag)
        assert script.get("src") is None
        assert "console.log" in (script.string or "")

    def test_copies_type_attribute_to_new_tag(self, tmp_path: Path):
        _ = (tmp_path / "module.js").write_text("export default {};", encoding="utf-8")
        soup = make_soup(
            "<html><head>"
            + '<script src="module.js" type="module"></script>'
            + "</head><body></body></html>"
        )

        _ = embed_scripts(soup, tmp_path)

        script = soup.find("script")
        assert isinstance(script, Tag)
        assert script.get("type") == "module"

    def test_does_not_copy_src_or_defer_attributes(self, tmp_path: Path):
        _ = (tmp_path / "app.js").write_text("var x = 1;", encoding="utf-8")
        soup = make_soup(
            "<html><head>"
            + '<script src="app.js" defer></script>'
            + "</head><body></body></html>"
        )

        _ = embed_scripts(soup, tmp_path)

        script = soup.find("script")
        assert isinstance(script, Tag)
        assert script.get("src") is None
        assert script.get("defer") is None

    def test_skips_and_warns_on_missing_local_asset(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        soup = make_soup(
            "<html><head>"
            + '<script src="missing.js"></script>'
            + "</head><body></body></html>"
        )

        count = embed_scripts(soup, tmp_path)

        assert count == 0
        # Original tag must remain with its src attribute
        original_tag = soup.find("script")
        assert isinstance(original_tag, Tag)
        assert original_tag.get("src") == "missing.js"
        assert "WARNING" in capsys.readouterr().out

    def test_embeds_multiple_scripts(self, tmp_path: Path):
        for name in ("a.js", "b.js"):
            _ = (tmp_path / name).write_text(f"var {name[0]} = 1;", encoding="utf-8")
        soup = make_soup(
            "<html><head>"
            + '<script src="a.js"></script>'
            + '<script src="b.js"></script>'
            + "</head><body></body></html>"
        )

        count = embed_scripts(soup, tmp_path)

        assert count == 2
        scripts = soup.find_all("script")
        assert all(s.get("src") is None for s in scripts)

    def test_skips_inline_scripts_without_src(self, tmp_path: Path):
        soup = make_soup(
            "<html><head>"
            + "<script>var inline = true;</script>"
            + "</head><body></body></html>"
        )

        count = embed_scripts(soup, tmp_path)

        assert count == 0
        # The existing inline script must be untouched
        script = soup.find("script")
        assert isinstance(script, Tag)
        assert "inline" in (script.string or "")


# ---------------------------------------------------------------------------
# build_parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_input_defaults_to_none(self):
        parser = build_parser()
        args = parser.parse_args([])
        input_val: str | None = args.input  # pyright: ignore[reportAny]
        assert input_val is None

    def test_accepts_positional_input_and_output(self):
        parser = build_parser()
        args = parser.parse_args(["input.html", "output.html"])
        input_val: str | None = args.input  # pyright: ignore[reportAny]
        output_val: str | None = args.output  # pyright: ignore[reportAny]
        assert input_val == "input.html"
        assert output_val == "output.html"

    def test_encoding_defaults_to_utf8(self):
        parser = build_parser()
        args = parser.parse_args([])
        encoding_val: str = args.encoding  # pyright: ignore[reportAny]
        assert encoding_val == "utf-8"

    def test_custom_encoding(self):
        parser = build_parser()
        args = parser.parse_args(["--encoding", "latin-1"])
        encoding_val: str = args.encoding  # pyright: ignore[reportAny]
        assert encoding_val == "latin-1"

    def test_skip_remote_flag_defaults_false(self):
        parser = build_parser()
        args = parser.parse_args([])
        skip_remote_val: bool = args.skip_remote  # pyright: ignore[reportAny]
        assert skip_remote_val is False

    def test_skip_remote_flag_set(self):
        parser = build_parser()
        args = parser.parse_args(["--skip-remote"])
        skip_remote_val: bool = args.skip_remote  # pyright: ignore[reportAny]
        assert skip_remote_val is True

    def test_skip_js_flag_defaults_false(self):
        parser = build_parser()
        args = parser.parse_args([])
        skip_js_val: bool = args.skip_js  # pyright: ignore[reportAny]
        assert skip_js_val is False

    def test_skip_js_flag_set(self):
        parser = build_parser()
        args = parser.parse_args(["--skip-js"])
        skip_js_val: bool = args.skip_js  # pyright: ignore[reportAny]
        assert skip_js_val is True

    def test_output_defaults_to_none(self):
        parser = build_parser()
        args = parser.parse_args([])
        output_val: str | None = args.output  # pyright: ignore[reportAny]
        assert output_val is None


# ---------------------------------------------------------------------------
# _tag_remote_assets
# ---------------------------------------------------------------------------


class TestTagRemoteAssets:
    def test_logs_remote_stylesheet_url(self, capsys: pytest.CaptureFixture[str]):
        soup = make_soup(
            "<html><head>"
            + '<link rel="stylesheet" href="https://example.com/style.css">'
            + "</head></html>"
        )

        _tag_remote_assets(soup)

        assert "https://example.com/style.css" in capsys.readouterr().out

    def test_does_not_modify_remote_stylesheet_tag(self):
        soup = make_soup(
            "<html><head>"
            + '<link rel="stylesheet" href="https://example.com/style.css">'
            + "</head></html>"
        )

        _tag_remote_assets(soup)

        link = soup.find("link")
        assert isinstance(link, Tag)
        assert link.get("href") == "https://example.com/style.css"

    def test_logs_remote_script_url(self, capsys: pytest.CaptureFixture[str]):
        soup = make_soup(
            "<html><head>"
            + '<script src="https://cdn.example.com/app.js"></script>'
            + "</head></html>"
        )

        _tag_remote_assets(soup)

        assert "https://cdn.example.com/app.js" in capsys.readouterr().out

    def test_does_not_modify_remote_script_tag(self):
        soup = make_soup(
            "<html><head>"
            + '<script src="https://cdn.example.com/app.js"></script>'
            + "</head></html>"
        )

        _tag_remote_assets(soup)

        script = soup.find("script")
        assert isinstance(script, Tag)
        assert script.get("src") == "https://cdn.example.com/app.js"

    def test_local_assets_are_not_logged(self, capsys: pytest.CaptureFixture[str]):
        soup = make_soup(
            "<html><head>"
            + '<link rel="stylesheet" href="../css/local.css">'
            + '<script src="../js/local.js"></script>'
            + "</head></html>"
        )

        _tag_remote_assets(soup)

        out = capsys.readouterr().out
        assert "local.css" not in out
        assert "local.js" not in out

    def test_local_assets_are_not_modified(self):
        soup = make_soup(
            "<html><head>"
            + '<link rel="stylesheet" href="../css/local.css">'
            + "</head></html>"
        )

        _tag_remote_assets(soup)

        link = soup.find("link")
        assert isinstance(link, Tag)
        assert link.get("href") == "../css/local.css"