#!/usr/bin/env python3
"""Avvia Label Anything dalla cartella del progetto."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labeling_tool.main import main

if __name__ == "__main__":
    raise SystemExit(main())
