#!/usr/bin/env python3
"""Download global public BOLD chordate records."""


from __future__ import annotations


from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
for _path in (SCRIPTS_ROOT / "_shared", SCRIPTS_ROOT / "download"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import sys

from download_bold_fungi import main


def add_default_arg(flag: str, value: str) -> None:
    if flag not in sys.argv:
        sys.argv.extend([flag, value])


if __name__ == "__main__":
    add_default_arg("--query", "tax:phylum:Chordata")
    add_default_arg("--stem", "bold_global_chordata")
    raise SystemExit(main())
