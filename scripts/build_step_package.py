"""Export one STEP per printable part plus the combined handle-free STEP."""

from pathlib import Path

from bracket.step_package import build_step_package


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in build_step_package(root):
        print(path)


if __name__ == "__main__":
    main()
