"""Build all review CAD artifacts from repository source."""

import json
from pathlib import Path

from bracket.assembly import build_all_outputs


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(build_all_outputs(root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
