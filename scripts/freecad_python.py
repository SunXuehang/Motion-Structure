"""Run a Python file inside FreeCAD while preserving normal exit semantics."""

from pathlib import Path
import runpy
import sys
import traceback


def main() -> None:
    """Execute arguments after FreeCAD's ``--pass`` marker as a Python script."""

    try:
        marker = sys.argv.index("--pass")
        script, *arguments = sys.argv[marker + 1 :]
    except (ValueError, IndexError):
        raise SystemExit("usage: freecad_python.py --pass <script> [args...]")

    script_path = Path(script).resolve()
    sys.argv = [str(script_path), *arguments]
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


# FreeCAD executes positional Python files with its console module globals rather
# than Python's conventional ``__main__`` module name.
main()
