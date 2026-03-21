from pathlib import Path

# main.py configuration
OUTPUT_DIR = Path("./output")
STATIC_DIR = Path("./static")
LATEXML_DIR = Path(__file__).parent / "latexml"
SRC_QED_SYMBOL = "∎"
ENCODING = "utf-8"

# create_main_index.py configuration
ROOT_DIR = OUTPUT_DIR
PATTERN = "index.html"
TEMPLATE_PATH = Path("templates/main_index_template.html")
