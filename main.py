import argparse
import logging
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from bs4 import BeautifulSoup

from config import ENCODING, LATEXML_DIR, OUTPUT_DIR, STATIC_DIR, SRC_QED_SYMBOL

logger = logging.getLogger(__name__)


def replace_qed_symbol(html_content: str) -> str:
    """Replace TeX QED symbol with accessible HTML equivalent."""
    replacement = textwrap.dedent("""\
        <span aria-hidden="true" class="qed">∎</span>
        <span class="visually-hidden">End of proof</span>
    """)
    return html_content.replace(SRC_QED_SYMBOL, replacement)


def add_custom_css_and_js(file_path: str, dry_run: bool = False) -> bool:
    """Add custom CSS, JavaScript, and process QED symbols in HTML file.

    Args:
        file_path: Path to the HTML file to process.
        dry_run: If True, print what would be done without modifying the file.

    Returns:
        True if successful, False otherwise.
    """
    if dry_run:
        logger.info("[DRY-RUN] Would customize HTML at: %s", file_path)
        logger.info("[DRY-RUN]   - Replace QED symbols")
        logger.info("[DRY-RUN]   - Add proof element classes")
        logger.info("[DRY-RUN]   - Inject CSS and JavaScript resources")
        return True

    try:
        with open(file_path, "r", encoding=ENCODING) as f:
            html_content = f.read()
    except FileNotFoundError:
        logger.error("File '%s' not found.", file_path)
        return False
    except IOError as e:
        logger.error("Error reading '%s': %s", file_path, e)
        return False

    html_content = replace_qed_symbol(html_content)
    soup = BeautifulSoup(html_content, "html.parser")

    if not soup.head:
        logger.warning("No <head> tag found in '%s'.", file_path)
        return False

    _inject_resources(soup)

    try:
        with open(file_path, "w", encoding=ENCODING) as f:
            _ = f.write(str(soup))
        return True
    except IOError as e:
        logger.error("Error writing to '%s': %s", file_path, e)
        return False



def update_stylesheet_links(
    html_path: str | Path,
    css_folder: str | Path,
    dry_run: bool = False,
) -> list[str]:
    """Update local stylesheet links to use shared CSS folder and remove originals.

    Finds stylesheet links in the HTML file that reference local CSS files.
    If a matching file exists in css_folder, updates the link to point there
    and deletes the original local file.

    Args:
        html_path: Path to the HTML file to process.
        css_folder: Path to the shared CSS folder.
        dry_run: If True, print what would be done without modifying files.

    Returns:
        List of CSS files that were updated (or would be updated in dry_run mode).
    """
    html_path = Path(html_path)
    css_folder = Path(css_folder)
    html_dir = html_path.parent
    updated_files: list[str] = []

    try:
        with open(html_path, "r", encoding=ENCODING) as f:
            soup = BeautifulSoup(f.read(), "html.parser")
    except (FileNotFoundError, IOError) as e:
        logger.error("Error reading '%s': %s", html_path, e)
        return updated_files

    # Find all stylesheet links
    link_tags = soup.find_all("link", rel="stylesheet")

    for link in link_tags:
        href = link.get("href")
        if not isinstance(href, str) or not href:
            continue

        # Skip external URLs and already-redirected paths
        if href.startswith(("http://", "https://", "//")):
            continue
        if "../css/" in href or str(css_folder) in href:
            continue

        # Get the CSS filename
        css_filename = Path(href).name
        local_css_path = html_dir / href
        shared_css_path = css_folder / css_filename

        # Check if CSS exists in shared folder
        if not shared_css_path.exists():
            continue

        # Calculate relative path from HTML to shared CSS folder
        try:
            rel_path = Path("../css") / css_filename
        except ValueError:
            rel_path = shared_css_path

        if dry_run:
            logger.info("[DRY-RUN] Would update link: %s -> %s", href, rel_path)
            if local_css_path.exists():
                logger.info("[DRY-RUN] Would delete: %s", local_css_path)
            updated_files.append(css_filename)
        else:
            # Update the link
            link["href"] = str(rel_path)
            updated_files.append(css_filename)

            # Delete the original local file if it exists
            if local_css_path.exists():
                try:
                    local_css_path.unlink()
                    logger.info("Deleted local CSS: %s", local_css_path)
                except OSError as e:
                    logger.error("Error deleting '%s': %s", local_css_path, e)

    # Write updated HTML
    if updated_files and not dry_run:
        try:
            with open(html_path, "w", encoding=ENCODING) as f:
                _ = f.write(str(soup))
            logger.info("Updated stylesheet links in: %s", html_path)
        except IOError as e:
            logger.error("Error writing '%s': %s", html_path, e)

    return updated_files


def _inject_resources(soup: BeautifulSoup) -> None:
    """Inject CSS and JavaScript resources into the HTML head."""
    if soup.head is None:
        return

    resources: list[tuple[str, dict[str, str]]] = [
        # ("link", {"rel": "stylesheet", "id": "latexCss",
        # "href": "https://unpkg.com/latex.css/style.min.css"}),
        ("link", {"rel": "stylesheet", "href": "../css/custom.css"}),
        ("script", {"defer": "", "src": "../js/custom.js"}),
        ("script", {"defer": "", "src": "../js/mathjax-config.js"}),
        (
            "script",
            {
                "defer": "",
                "src": "https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js",
            },
        ),
    ]

    for tag_name, attrs in resources:
        if not soup.head.find(tag_name, attrs=attrs):  # pyright: ignore[reportCallIssue, reportArgumentType]
            new_tag = soup.new_tag(tag_name)
            for attr_name, attr_value in attrs.items():
                new_tag[attr_name] = attr_value
            _ = soup.head.append(new_tag)


def process_file(
    cmd: str,
    dry_run: bool = False,
    cwd: Path | None = None,
    max_exit_code: int = 0,
) -> bool:
    """Execute a shell command for file processing.

    Args:
        cmd: Shell command string to execute.
        dry_run: If True, print the command without executing it.
        cwd: Working directory for the command. Defaults to the current directory.
        max_exit_code: Highest exit code still considered success (default 0).
            For latexmlc, pass 1 to tolerate warnings (exit 1) as success.

    Returns:
        True if successful, False otherwise.
    """
    if dry_run:
        logger.info("[DRY-RUN] %s", cmd)
        return True

    command_args = shlex.split(cmd)
    logger.info("Running command: %s", cmd)

    try:
        result = subprocess.run(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
        )
    except FileNotFoundError:
        logger.error(
            "Command '%s' not found. Ensure it is installed and in your PATH.",
            command_args[0],
        )
        return False

    if result.returncode > max_exit_code:
        output = (result.stderr or result.stdout or "").strip()
        logger.error(
            "Error processing command (exit %d): %s",
            result.returncode,
            output or "(no output)",
        )
        return False

    logger.info("Successfully processed command")
    return True


def _seed_output_dir(output_dir: Path, static_dir: Path = STATIC_DIR) -> None:
    """Copy static assets into the output directory, skipping existing files."""
    if not static_dir.is_dir():
        logger.warning("Static directory not found: %s", static_dir)
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    _ = shutil.copytree(static_dir, output_dir, dirs_exist_ok=True)
    logger.info("Seeded output directory from %s", static_dir)


def _remove_empty_subdirs(output_dir: Path) -> None:
    """Remove empty subdirectories from output_dir (deepest first)."""
    for d in sorted(output_dir.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            try:
                d.rmdir()
                logger.info("Removed empty directory: %s", d)
            except OSError as e:
                logger.warning("Could not remove '%s': %s", d, e)


def _detect_bibliography(tex_file: Path) -> str | None:
    """Return the bibliography tool needed by tex_file, or None.

    Returns 'biber' if the document uses biblatex or \\addbibresource,
    'bibtex' if it uses \\bibliography{}, or None if no bibliography is found.
    """
    try:
        content = tex_file.read_text(encoding=ENCODING)
    except OSError:
        return None
    if re.search(r"\\usepackage(?:\[[^\]]*\])?\{biblatex\}", content):
        return "biber"
    if re.search(r"\\bibliography\{", content):
        return "bibtex"
    if re.search(r"\\addbibresource\{", content):
        return "biber"
    return None


def _has_cite_commands(tex_file: Path) -> bool:
    """Return True if tex_file contains \\cite variants with an external bibliography.

    Returns False when the only bibliography is inline (\\begin{thebibliography}),
    since that requires no pre-processing.
    """
    try:
        content = tex_file.read_text(encoding=ENCODING)
    except OSError:
        return False
    if re.search(r"\\begin\{thebibliography\}", content):
        return False
    return bool(
        re.search(
            r"\\(?:cite\w*|parencite\w*|textcite\w*|footcite\w*|autocite\w*)\s*[{\[]",
            content,
        )
    )


def _create_include_subdirs(tex_file: Path, output_dir: Path) -> None:
    """Create subdirectories in output_dir for any \\include{subdir/...} paths."""
    try:
        content = tex_file.read_text(encoding=ENCODING)
    except OSError:
        return
    for match in re.finditer(r"\\include\{([^}]+)\}", content):
        parent = Path(match.group(1)).parent
        if str(parent) != ".":
            (output_dir / parent).mkdir(parents=True, exist_ok=True)


def process_files() -> int:
    """Process LaTeX files using latexml and customize HTML output.

    Returns:
        0 if all files processed successfully, 1 if any failed.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Process LaTeX files using latexml and customize HTML output."
    )
    _ = parser.add_argument(
        "tex_files",
        nargs="+",
        help="One or more .tex files to process",
    )
    _ = parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print commands without executing them",
    )
    _ = parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        metavar="DIR",
        help="Root output directory (default: %(default)s)",
    )
    _ = parser.add_argument(
        "-N",
        "--name",
        metavar="NAME",
        default=None,
        help="Output subdirectory name (default: source file stem). Only valid with a single input file.",
    )

    args = parser.parse_args()
    tex_files: list[str] = args.tex_files  # pyright: ignore[reportAny]
    dry_run: bool = args.dry_run  # pyright: ignore[reportAny]
    output: Path = args.output  # pyright: ignore[reportAny]
    name: str | None = args.name  # pyright: ignore[reportAny]

    if name is not None and len(tex_files) > 1:
        parser.error("--name can only be used with a single input file")

    latexml_bindings = sorted(LATEXML_DIR.glob("*.ltxml")) if LATEXML_DIR.is_dir() else []
    if not latexml_bindings:
        logger.warning("No LaTeXML bindings found in: %s", LATEXML_DIR)
    preload_flags = " ".join(f"--preload='{b}'" for b in latexml_bindings)

    latexml_cmd = (
        "latexmlc --format=html5 --includestyles "
        f"{preload_flags} "
        "--sourcedirectory='{src_dir}' "
        "--svg "
        "--quiet --quiet "
        "--destination='{output_dir}/index.html' '{input_file}'"
    )

    pdflatex_cmd = (
        "pdflatex -synctex=1 -interaction=nonstopmode "
        "-output-directory='{output_dir}' '{input_name}'"
    )

    failed_files: list[str] = []

    if not dry_run:
        _seed_output_dir(output)
    else:
        logger.info("[DRY-RUN] Would seed output directory from %s", STATIC_DIR)

    for file_path in tex_files:
        logger.info("Processing file: %s", file_path)

        file_obj = Path(file_path)
        if not file_obj.exists():
            logger.warning("File '%s' not found.", file_path)
            failed_files.append(file_path)
            continue

        stem = name if name is not None else file_obj.stem
        output_dir = output / stem

        _create_include_subdirs(file_obj, output_dir)
        bib_tool = _detect_bibliography(file_obj)
        has_cites = _has_cite_commands(file_obj)
        pdf_cmd = pdflatex_cmd.format(
            output_dir=str(output_dir.resolve()),
            input_name=file_obj.name,
        )
        bib_stem = str((output_dir / file_obj.stem).resolve())
        bbl_in_src: Path | None = None

        if has_cites and bib_tool:
            # Generate .bbl before latexmlc so HTML citations resolve correctly.
            logger.info("Cite commands detected; generating bibliography first (%s)", bib_tool)
            # Pass 1: pdflatex → .aux with citation data
            if not process_file(pdf_cmd, dry_run, cwd=file_obj.parent):
                failed_files.append(file_path)
                continue
            # bibtex/biber → .bbl
            bib_cmd = f"{bib_tool} '{bib_stem}'"
            if not process_file(bib_cmd, dry_run, cwd=file_obj.parent):
                logger.warning("Bibliography step failed; citations may be unresolved in HTML")
            else:
                # Copy .bbl into the source directory so latexmlc finds it via --sourcedirectory
                bbl_src = output_dir / f"{file_obj.stem}.bbl"
                if dry_run:
                    logger.info("[DRY-RUN] Would copy %s to %s", bbl_src, file_obj.parent)
                elif bbl_src.exists():
                    bbl_in_src = file_obj.parent / bbl_src.name
                    shutil.copy2(bbl_src, bbl_in_src)

        cmd = latexml_cmd.format(
            output_dir=str(output_dir),
            input_file=file_path,
            src_dir=str(file_obj.parent),
        )
        latexml_ok = process_file(cmd, dry_run, max_exit_code=1)
        # Remove latexml.log written to the working directory by latexmlc
        latexml_log = Path("latexml.log")
        if dry_run:
            if latexml_log.exists():
                logger.info("[DRY-RUN] Would remove: %s", latexml_log)
        elif latexml_log.exists():
            try:
                latexml_log.unlink()
                logger.info("Removed %s", latexml_log)
            except OSError as e:
                logger.warning("Could not remove '%s': %s", latexml_log, e)
        # Clean up temporary .bbl copy from source dir regardless of latexml outcome
        if bbl_in_src and bbl_in_src.exists():
            bbl_in_src.unlink()
        if not latexml_ok:
            failed_files.append(file_path)
            continue

        if has_cites and bib_tool:
            # .bbl already generated above; just need the final pdflatex pass
            if not process_file(pdf_cmd, dry_run, cwd=file_obj.parent):
                failed_files.append(file_path)
                continue
        elif bib_tool:
            # Bibliography declared but no \cite detected; standard bib cycle for PDF
            if not process_file(pdf_cmd, dry_run, cwd=file_obj.parent):
                failed_files.append(file_path)
                continue
            bib_cmd = f"{bib_tool} '{bib_stem}'"
            if not process_file(bib_cmd, dry_run, cwd=file_obj.parent):
                logger.warning("Bibliography step failed; PDF may lack references")
            if not process_file(pdf_cmd, dry_run, cwd=file_obj.parent):
                failed_files.append(file_path)
                continue
        else:
            if not process_file(pdf_cmd, dry_run, cwd=file_obj.parent):
                failed_files.append(file_path)
                continue

        for aux_file in output_dir.rglob("*"):
            if aux_file.suffix in {".aux", ".log", ".out", ".bbl", ".blg", ".bcf"} or aux_file.name.endswith(".run.xml"):
                if dry_run:
                    logger.info("[DRY-RUN] Would remove auxiliary file: %s", aux_file)
                else:
                    try:
                        aux_file.unlink()
                    except OSError as e:
                        logger.warning("Could not remove '%s': %s", aux_file, e)

        if dry_run:
            logger.info("[DRY-RUN] Would remove empty subdirectories from: %s", output_dir)
        else:
            _remove_empty_subdirs(output_dir)

        html_file = output_dir / "index.html"
        if not add_custom_css_and_js(str(html_file), dry_run):
            failed_files.append(file_path)

        _ = update_stylesheet_links(html_file, css_folder=output / "css", dry_run=dry_run)

    if failed_files:
        files_list = "\n".join(f"  - {f}" for f in failed_files)
        logger.error("Failed to process %d file(s):\n%s", len(failed_files), files_list)
        return 1

    if dry_run:
        logger.info("[DRY-RUN] All commands would execute successfully.")
    else:
        logger.info("All files processed successfully.")
    return 0


def clean_logs() -> int:
    """Remove all latexml.log files from the current directory and output tree.

    Returns:
        0 always (clean-up errors are logged as warnings, not failures).
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    candidates: list[Path] = [Path("latexml.log")]
    if OUTPUT_DIR.is_dir():
        candidates.extend(OUTPUT_DIR.rglob("latexml.log"))

    removed = 0
    for log_file in candidates:
        if log_file.exists():
            try:
                log_file.unlink()
                logger.info("Removed: %s", log_file)
                removed += 1
            except OSError as e:
                logger.warning("Could not remove '%s': %s", log_file, e)

    if removed == 0:
        logger.info("No latexml.log files found.")
    else:
        logger.info("Removed %d latexml.log file(s).", removed)
    return 0


if __name__ == "__main__":
    sys.exit(process_files())

