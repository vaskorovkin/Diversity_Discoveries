#!/usr/bin/env python3
"""Download global public BOLD mollusk records."""

from __future__ import annotations

import sys

from download_bold_fungi import main


def add_default_arg(flag: str, value: str) -> None:
    if flag not in sys.argv:
        sys.argv.extend([flag, value])


if __name__ == "__main__":
    add_default_arg("--query", "tax:phylum:Mollusca")
    add_default_arg("--stem", "bold_global_mollusca")
    raise SystemExit(main())
