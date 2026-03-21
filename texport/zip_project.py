#!/usr/bin/env python3
"""Create a zip archive of the project, excluding build artifacts and dotfiles."""

import zipfile
from datetime import datetime
from pathlib import Path


def should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from the archive."""
    exclude_dirs = {"build", "__pycache__"}
    exclude_files = {"uv.lock"}
    exclude_extensions = {".aux", ".log", ".synctex.gz", ".cache", ".zip", ".pyc"}

    # Exclude dotfiles and dot directories
    for part in path.parts:
        if part.startswith("."):
            return True

    # Exclude specific directories
    for part in path.parts:
        if part in exclude_dirs:
            return True

    # Exclude specific files
    if path.name in exclude_files:
        return True

    # Exclude by extension
    if path.suffix in exclude_extensions:
        return True

    # Exclude multi-part extensions
    if path.name.endswith(".synctex.gz"):
        return True

    return False


def create_zip(output_name: str | None = None) -> Path:
    """Create a zip archive of the project.

    Args:
        output_name: Optional name for the zip file. If not provided,
                     uses 'texport-YYYYMMDD-HHMMSS.zip'.

    Returns:
        Path to the created zip file.
    """
    project_root = Path(__file__).parent.parent

    if output_name is None:
        timestamp = datetime.now().strftime("%Y-%b-%d_%H%M%S")
        output_name = f"texport-{timestamp}.zip"

    output_path = project_root / output_name

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in project_root.rglob("*"):
            if file_path.is_file() and not should_exclude(
                file_path.relative_to(project_root)
            ):
                arcname = file_path.relative_to(project_root)
                zf.write(file_path, arcname)
                print(f"Added: {arcname}")

    print(f"\nCreated: {output_path}")
    return output_path


if __name__ == "__main__":
    _ = create_zip()
