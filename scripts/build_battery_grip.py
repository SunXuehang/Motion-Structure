"""Build the hollow battery grip and its lower-cover assembly (CAD only, no STL)."""

from pathlib import Path

from bracket.battery_grip import build_battery_grip_outputs


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in build_battery_grip_outputs(root):
        print(path)


if __name__ == "__main__":
    main()
