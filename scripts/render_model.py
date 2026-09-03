"""Generate all R45 browser-review PNGs."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bracket.rendering import render_pivot_section_images, render_review_images


def main() -> None:
    for path in (*render_review_images(ROOT), *render_pivot_section_images(ROOT)):
        print(path)


if __name__ == "__main__":
    main()
