"""Tests for zip_project.py — archive exclusion rules and zip creation."""

import zipfile
from pathlib import Path

import pytest

from texport.zip_project import should_exclude, create_zip


# ---------------------------------------------------------------------------
# should_exclude
# ---------------------------------------------------------------------------


class TestShouldExclude:
    # --- dotfiles and dot-directories ---

    def test_excludes_dotfile_at_root(self):
        assert should_exclude(Path(".gitignore"))

    def test_excludes_dotfile_in_subdir(self):
        assert should_exclude(Path("subdir/.env"))

    def test_excludes_dot_directory(self):
        assert should_exclude(Path(".git/config"))

    def test_excludes_nested_under_dot_directory(self):
        assert should_exclude(Path(".venv/lib/python3.12/site.py"))

    def test_excludes_pycache_directory(self):
        assert should_exclude(Path("__pycache__/module.cpython-312.pyc"))

    def test_excludes_pycache_at_root(self):
        assert should_exclude(Path("__pycache__"))

    # --- specific excluded directories ---

    def test_excludes_build_dir(self):
        assert should_exclude(Path("build/main.aux"))

    def test_excludes_file_named_build(self):
        # A path component equal to "build" triggers exclusion
        assert should_exclude(Path("build"))

    def test_excludes_nested_under_build(self):
        assert should_exclude(Path("build/subdir/output.pdf"))

    # --- specific excluded files ---

    def test_excludes_uv_lock(self):
        assert should_exclude(Path("uv.lock"))

    def test_excludes_uv_lock_in_subdir(self):
        assert should_exclude(Path("subdir/uv.lock"))

    # --- excluded extensions ---

    def test_excludes_aux(self):
        assert should_exclude(Path("main.aux"))

    def test_excludes_log(self):
        assert should_exclude(Path("main.log"))

    def test_excludes_synctex_gz(self):
        assert should_exclude(Path("main.synctex.gz"))

    def test_excludes_cache(self):
        assert should_exclude(Path("data.cache"))

    def test_excludes_zip(self):
        assert should_exclude(Path("archive.zip"))

    def test_excludes_pyc(self):
        assert should_exclude(Path("module.pyc"))

    # --- files that must NOT be excluded ---

    def test_keeps_python_source(self):
        assert not should_exclude(Path("main.py"))

    def test_keeps_config(self):
        assert not should_exclude(Path("config.py"))

    def test_keeps_readme(self):
        assert not should_exclude(Path("README.md"))

    def test_keeps_specs(self):
        assert not should_exclude(Path("SPECS.md"))

    def test_keeps_license(self):
        assert not should_exclude(Path("LICENSE"))

    def test_keeps_pyproject(self):
        assert not should_exclude(Path("pyproject.toml"))

    def test_keeps_template_html(self):
        assert not should_exclude(Path("templates/main_index_template.html"))

    def test_keeps_output_html(self):
        assert not should_exclude(Path("output/doc/index.html"))

    def test_keeps_output_pdf(self):
        assert not should_exclude(Path("output/doc/lecture.pdf"))


# ---------------------------------------------------------------------------
# create_zip  (integration — actually writes into the project root)
# ---------------------------------------------------------------------------


@pytest.fixture()
def cleanup_zip():
    """Yield a list; any Path appended to it is deleted after the test."""
    paths: list[Path] = []
    yield paths
    for p in paths:
        p.unlink(missing_ok=True)


class TestCreateZip:
    def test_returns_path_object(self, cleanup_zip: list[Path]):
        result = create_zip("_test_texport_tmp.zip")
        cleanup_zip.append(result)
        assert isinstance(result, Path)

    def test_file_is_created_on_disk(self, cleanup_zip: list[Path]):
        result = create_zip("_test_texport_created.zip")
        cleanup_zip.append(result)
        assert result.exists()

    def test_custom_name_is_used(self, cleanup_zip: list[Path]):
        result = create_zip("_test_custom_name.zip")
        cleanup_zip.append(result)
        assert result.name == "_test_custom_name.zip"

    def test_default_name_starts_with_texport(self, cleanup_zip: list[Path]):
        result = create_zip()
        cleanup_zip.append(result)
        assert result.name.startswith("texport-")

    def test_default_name_ends_with_zip(self, cleanup_zip: list[Path]):
        result = create_zip()
        cleanup_zip.append(result)
        assert result.suffix == ".zip"

    def test_output_is_valid_zip(self, cleanup_zip: list[Path]):
        result = create_zip("_test_texport_valid.zip")
        cleanup_zip.append(result)
        assert zipfile.is_zipfile(result)

    def test_zip_contains_main_py(self, cleanup_zip: list[Path]):
        result = create_zip("_test_texport_contents.zip")
        cleanup_zip.append(result)
        with zipfile.ZipFile(result) as zf:
            assert "texport/main.py" in zf.namelist()

    def test_zip_contains_config_py(self, cleanup_zip: list[Path]):
        result = create_zip("_test_texport_config.zip")
        cleanup_zip.append(result)
        with zipfile.ZipFile(result) as zf:
            assert "texport/config.py" in zf.namelist()

    def test_zip_contains_pyproject_toml(self, cleanup_zip: list[Path]):
        result = create_zip("_test_texport_pyproject.zip")
        cleanup_zip.append(result)
        with zipfile.ZipFile(result) as zf:
            assert "pyproject.toml" in zf.namelist()

    def test_zip_excludes_dotfiles(self, cleanup_zip: list[Path]):
        result = create_zip("_test_texport_dotfiles.zip")
        cleanup_zip.append(result)
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
        # No archive entry should have a component that starts with "."
        for name in names:
            for part in Path(name).parts:
                assert not part.startswith("."), (
                    f"Dotfile/dir found in archive: {name!r}"
                )

    def test_zip_excludes_pycache(self, cleanup_zip: list[Path]):
        result = create_zip("_test_texport_pycache.zip")
        cleanup_zip.append(result)
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
        assert not any("__pycache__" in name for name in names)

    def test_zip_excludes_build_dir(self, cleanup_zip: list[Path]):
        result = create_zip("_test_texport_build.zip")
        cleanup_zip.append(result)
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
        assert not any(
            Path(name).parts[0] == "build" for name in names
        )

    def test_zip_does_not_include_itself(self, cleanup_zip: list[Path]):
        """The freshly created zip should not archive itself."""
        result = create_zip("_test_texport_noself.zip")
        cleanup_zip.append(result)
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
        assert result.name not in names

    def test_archive_entries_use_relative_paths(self, cleanup_zip: list[Path]):
        """All archive paths must be relative (no leading slash)."""
        result = create_zip("_test_texport_relpaths.zip")
        cleanup_zip.append(result)
        with zipfile.ZipFile(result) as zf:
            for name in zf.namelist():
                assert not Path(name).is_absolute(), (
                    f"Absolute path found in archive: {name!r}"
                )