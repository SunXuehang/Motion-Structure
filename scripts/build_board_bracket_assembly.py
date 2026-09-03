"""Build the combined UAV V3 board, covers, and MID-360 bracket package."""

from pathlib import Path

from bracket.board_bracket_assembly import build_board_bracket_outputs


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in build_board_bracket_outputs(root):
        print(path)


if __name__ == "__main__":
    main()
