"""Render the complete handheld stack as an exploded-view MP4."""

from pathlib import Path

from bracket.exploded_view import render_exploded_animation


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in render_exploded_animation(root):
        print(path)


if __name__ == "__main__":
    main()
