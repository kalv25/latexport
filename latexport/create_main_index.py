import argparse
import html
import logging
from pathlib import Path

from bs4 import BeautifulSoup

from .config import ENCODING, PATTERN, ROOT_DIR, TEMPLATE_PATH

logger = logging.getLogger(__name__)


def read_file_content(file_path: Path | str) -> str | None:
    try:
        return Path(file_path).read_text(encoding=ENCODING)
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
        return None
    except Exception as e:
        logger.error("Error reading file: %s", e)
        return None


def get_link_to_pdf(directory: Path, root_dir: Path) -> str:
    """Generate PDF link if a PDF exists in directory."""
    pdf_files = list(directory.glob("*.pdf"))
    if pdf_files:
        pdf_relative_path = pdf_files[0].relative_to(root_dir)
        return f', <a href="{pdf_relative_path}">PDF</a>'
    return ""


def link_to_page(directory: Path, title: str, root_dir: Path) -> str:
    """Generate HTML list item for a page with optional PDF link."""
    relative_path = directory.relative_to(root_dir)
    pdf_link = get_link_to_pdf(directory, root_dir)
    return f'<li><a href="{relative_path}/">{html.escape(title)}</a>{pdf_link}</li>\n'


def discover_index_files(root_dir: Path) -> list[tuple[Path, str]]:
    """Discover index.html files and extract their titles."""
    results: list[tuple[Path, str]] = []
    logger.info(
        "Processing files matching '%s' recursively from %s", PATTERN, root_dir.resolve()
    )

    for file_path in root_dir.rglob(PATTERN):
        if file_path == root_dir.joinpath(PATTERN):
            continue  # Skip root index.html

        if file_path.is_file():
            logger.debug("Found: %s", file_path)
            html_content = file_path.read_text(encoding=ENCODING)
            soup = BeautifulSoup(html_content, "html.parser")
            title = soup.title.get_text() if soup.title else "No Title"
            results.append((file_path.parent, title))

    return results


def generate_links_html(index_files: list[tuple[Path, str]], root_dir: Path) -> str:
    """Generate HTML links from discovered index files."""
    links = [
        link_to_page(directory, title, root_dir) for directory, title in index_files
    ]
    return "".join(links)


def create_main_index_page(
    root_dir: Path = ROOT_DIR,
    template_path: Path = TEMPLATE_PATH,
    *,
    lang: str = "en",
    title: str = "Documents",
    description: str = "Document index",
    heading: str = "Documents",
    contents_label: str = "Contents",
) -> None:
    """Create the main index page from template and discovered pages."""
    template_content = read_file_content(template_path)
    if template_content is None:
        logger.error("Failed to load template from %s", template_path)
        return

    index_files = discover_index_files(root_dir)
    links_html = generate_links_html(index_files, root_dir)

    index_content = template_content.format(
        lang=lang,
        title=title,
        description=description,
        heading=heading,
        contents_label=contents_label,
        links=links_html,
    )
    index_path = root_dir / "index.html"
    _ = index_path.write_text(index_content, encoding=ENCODING)
    logger.info("Main index page created at: %s", index_path.resolve())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Generate a main index page for all documents in the output directory."
    )
    _ = parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT_DIR,
        metavar="DIR",
        help="Output directory to scan and write index into (default: %(default)s)",
    )
    args = parser.parse_args()
    root_dir: Path = args.output  # pyright: ignore[reportAny]
    create_main_index_page(root_dir=root_dir)


if __name__ == "__main__":
    main()
