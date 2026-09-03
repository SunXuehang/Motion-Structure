"""Build the UAV V3 board-cover CAD package and browser-review images."""

from pathlib import Path

from bracket.board_cover_package import build_board_cover_outputs
from bracket.board_cover_rendering import render_board_cover_images


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = build_board_cover_outputs(root)
    for path in render_board_cover_images(root):
        print(path)
    if not all(report["reimports"].values()):
        raise RuntimeError("one or more board-cover exports failed round-trip validation")


if __name__ == "__main__":
    main()
