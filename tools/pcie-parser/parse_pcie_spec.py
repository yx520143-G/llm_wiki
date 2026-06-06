from __future__ import annotations

import sys
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_ROOT))

from pcie_parser.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
