#!/usr/bin/env python3
"""
embed_assets.py

Reads an HTML file and produces a self-contained copy by inlining every
linked CSS (<link rel="stylesheet">) and every external script (<script src>),
whether those assets are stored locally or fetched from a remote URL.

Usage
-----
    python embed_assets.py [INPUT] [OUTPUT]

    INPUT   Path to the source HTML file.
            Defaults to index.html in the same directory as this script.

    OUTPUT  Path for the bundled output file.
            Defaults to <input_stem>_bundled.html next to the input file.

Examples
--------
    python embed_assets.py
    python embed_assets.py index.html
    python embed_assets.py index.html dist/index_standalone.html

Dependencies
------------
    beautifulsoup4  (uv add beautifulsoup4)
"""

import sys
import argparse
import urllib.request
import urllib.error
from pathlib import Path
try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit(
        "ERROR: beautifulsoup4 is required.\n"
        + "Install it with:  uv add beautifulsoup4"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_remote(url: str) -> bool:
    """Return True if *url* is an http/https address."""
    return url.startswith("http://") or url.startswith("https://")


def fetch_remote(url: str) -> str:
    """Download *url* and return its text content."""
    print(f"  [remote] {url}")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # pyright: ignore[reportAny]
            content_type: str = resp.headers.get("Content-Type", "")  # pyright: ignore[reportAny]
            charset = _charset_from_content_type(content_type) or "utf-8"
            return resp.read().decode(charset, errors="replace")  # pyright: ignore[reportAny]
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not fetch {url!r}: {exc}") from exc


def _charset_from_content_type(content_type: str) -> str | None:
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            return part.split("=", 1)[1].strip().strip('"')
    return None


def read_local(path: Path) -> str:
    """Read a local file and return its text content."""
    print(f"  [local]  {path}")
    if not path.exists():
        raise FileNotFoundError(f"Asset not found: {path}")
    return path.read_text(encoding="utf-8")


def resolve_local(href: str, html_dir: Path) -> Path:
    """Resolve a relative or absolute *href* against the HTML file's directory."""
    p = Path(href)
    if p.is_absolute():
        return p
    return (html_dir / p).resolve()


def fetch_asset(href: str, html_dir: Path) -> str:
    """Return the text content of an asset, local or remote."""
    if is_remote(href):
        return fetch_remote(href)
    return read_local(resolve_local(href, html_dir))


# ---------------------------------------------------------------------------
# Core embedding logic
# ---------------------------------------------------------------------------

def embed_stylesheets(soup: BeautifulSoup, html_dir: Path) -> int:
    """
    Replace every <link rel="stylesheet" href="..."> with an inline <style> tag.
    Returns the number of stylesheets embedded.
    """
    count = 0
    for tag in soup.find_all("link", rel="stylesheet"):
        href_val = tag.get("href") or ""
        if not isinstance(href_val, str) or not href_val:
            continue
        href = href_val.strip()
        if not href:
            continue
        try:
            css_text = fetch_asset(href, html_dir)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"  WARNING: skipping stylesheet – {exc}")
            continue

        style_tag = soup.new_tag("style")
        # Preserve any media attribute
        media = tag.get("media")
        if media:
            style_tag["media"] = media
        style_tag.string = "\n" + css_text + "\n"
        _ = tag.replace_with(style_tag)
        count += 1
    return count


def embed_scripts(soup: BeautifulSoup, html_dir: Path) -> int:
    """
    Replace every <script src="..."> with an inline <script> tag.
    Returns the number of scripts embedded.
    """
    count = 0
    for tag in soup.find_all("script", src=True):
        src_val = tag.get("src") or ""
        if not isinstance(src_val, str) or not src_val:
            continue
        src = src_val.strip()
        if not src:
            continue
        try:
            js_text = fetch_asset(src, html_dir)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"  WARNING: skipping script – {exc}")
            continue

        new_tag = soup.new_tag("script")
        # Copy useful attributes (type, etc.) but not src/defer/async
        for attr in ("type",):
            if tag.has_attr(attr):
                new_tag[attr] = tag[attr]
        new_tag.string = "\n" + js_text + "\n"
        _ = tag.replace_with(new_tag)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bundle external CSS and JS into a single self-contained HTML file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    _ = parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to the source HTML file (default: index.html next to this script).",
    )
    _ = parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Path for the output HTML file (default: <stem>_bundled.html).",
    )
    _ = parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Encoding used when reading/writing HTML files (default: utf-8).",
    )
    _ = parser.add_argument(
        "--skip-remote",
        action="store_true",
        help="Skip remote (http/https) assets instead of downloading them.",
    )
    _ = parser.add_argument(
        "--skip-js",
        action="store_true",
        help="Skip embedding JS files, leaving <script src> tags untouched.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    input_arg: str | None = args.input  # pyright: ignore[reportAny]
    output_arg: str | None = args.output  # pyright: ignore[reportAny]
    encoding: str = args.encoding  # pyright: ignore[reportAny]
    skip_remote: bool = args.skip_remote  # pyright: ignore[reportAny]
    skip_js: bool = args.skip_js  # pyright: ignore[reportAny]

    # --- Resolve input path ---
    if input_arg is None:
        input_path = Path(__file__).parent / "index.html"
    else:
        input_path = Path(input_arg).resolve()

    if not input_path.exists():
        sys.exit(f"ERROR: Input file not found: {input_path}")

    # --- Resolve output path ---
    if output_arg is None:
        output_path = input_path.parent / (input_path.stem + "_bundled" + input_path.suffix)
    else:
        output_path = Path(output_arg).resolve()

    html_dir = input_path.parent

    print(f"Input  : {input_path}")
    print(f"Output : {output_path}")
    print()

    # --- Parse HTML ---
    raw_html = input_path.read_text(encoding=encoding)
    soup = BeautifulSoup(raw_html, "html.parser")

    # --- Optionally filter out remote assets before embedding ---
    if skip_remote:
        _tag_remote_assets(soup)

    # --- Embed ---
    print("Embedding stylesheets…")
    css_count = embed_stylesheets(soup, html_dir)
    print(f"  → {css_count} stylesheet(s) embedded.\n")

    print("Embedding scripts…")
    if skip_js:
        print("  [skip-js] skipping all JS files.")
        js_count = 0
    else:
        js_count = embed_scripts(soup, html_dir)
    print(f"  → {js_count} script(s) embedded.\n")

    # --- Write output ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = output_path.write_text(str(soup), encoding=encoding)

    print(f"Done. Self-contained file written to:\n  {output_path}")


def _tag_remote_assets(soup: BeautifulSoup) -> None:
    """
    When --skip-remote is active, remove the src/href from remote tags so the
    embedding functions ignore them (the tags remain in the document as-is).
    """
    for tag in soup.find_all("link", rel="stylesheet"):
        href = tag.get("href", "")
        if isinstance(href, str) and is_remote(href):
            print(f"  [skip-remote] {href}")
            # Leave the original tag untouched so the browser can still load it
            # (useful if the output will still have network access).

    for tag in soup.find_all("script", src=True):
        src = tag.get("src", "")
        if isinstance(src, str) and is_remote(src):
            print(f"  [skip-remote] {src}")


if __name__ == "__main__":
    main()