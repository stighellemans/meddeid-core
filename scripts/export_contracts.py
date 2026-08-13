#!/usr/bin/env python3
"""Export language-neutral MedDeID contracts from the Python authority."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meddeid_core.export_contracts import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["--output", str(ROOT / "contracts" / "taxonomy.json"), *sys.argv[1:]]))
