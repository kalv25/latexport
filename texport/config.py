import tomllib
from pathlib import Path

_PKG = Path(__file__).parent


def _load_user_config() -> dict[str, str]:
    """Read [tool.texport] from pyproject.toml in the current working directory."""
    try:
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        raw = data.get("tool", {}).get("texport", {})
        return {k: str(v) for k, v in raw.items()}
    except Exception:
        return {}


_cfg = _load_user_config()

# ── main.py configuration ─────────────────────────────────────────────
OUTPUT_DIR  = Path(_cfg.get("output_dir",  "./output"))
STATIC_DIR  = Path(_cfg["static_dir"]) if "static_dir" in _cfg else (
    Path("./static") if Path("./static").is_dir() else _PKG / "static"
)
LATEXML_DIR = _PKG / "latexml"
SRC_QED_SYMBOL = _cfg.get("src_qed_symbol", "∎")
ENCODING = "utf-8"

# ── create_main_index.py configuration ───────────────────────────────
ROOT_DIR      = OUTPUT_DIR
PATTERN       = "index.html"
TEMPLATE_PATH = (
    Path("templates/main_index_template.html")
    if Path("templates/main_index_template.html").is_file()
    else _PKG / "templates" / "main_index_template.html"
)
