from __future__ import annotations

import sys
from pathlib import Path


SRC_PATH = Path(__file__).resolve().parent / "src"
if SRC_PATH.exists():
    src_as_str = str(SRC_PATH)
    if src_as_str not in sys.path:
        sys.path.insert(0, src_as_str)
