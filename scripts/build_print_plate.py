#!/usr/bin/env python3
"""Build the combined four-part 256 x 256 mm print-plate STEP."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_SRC = str(PROJECT_ROOT / "src")
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from bracket.print_plate import build_print_plate_outputs


if __name__ == "__main__":
    print(build_print_plate_outputs(PROJECT_ROOT))
