"""Checks for the per-part STEP package and its combined handle-free file."""

from math import isclose
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_SRC = str(PROJECT_ROOT / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

from bracket.step_package import (
    COMBINED_PART_COUNT,
    COMBINED_STEP_NAME,
    _reimported_solid_count,
    build_step_package,
    printable_parts,
)

TOLERANCE = 1e-6
EXPECTED_STEMS = (
    "part_a_radar_plate",
    "part_b_tilt_base",
    "board_cover_upper",
    "board_cover_lower",
    "battery_grip_body",
    "battery_grip_bottom_cap",
)


def test_every_pla_part_is_present_print_side_down_and_centred() -> None:
    """Catch a missing part, a floating one, or one left off its print face."""

    parts = printable_parts()
    assert tuple(stem for stem, _label, _shape in parts) == EXPECTED_STEMS
    for stem, label, shape in parts:
        assert shape.isValid() and len(shape.Solids) == 1, stem
        assert label.strip() == label and label, stem
        bounds = shape.BoundBox
        # Seated on the bed and centred, so the file drops straight into a slicer.
        assert isclose(bounds.ZMin, 0.0, abs_tol=TOLERANCE), stem
        assert isclose(bounds.Center.x, 0.0, abs_tol=1e-6), stem
        assert isclose(bounds.Center.y, 0.0, abs_tol=1e-6), stem
        # A real first layer, not a knife edge resting on the bed.
        assert bounds.XLength > 5.0 and bounds.YLength > 5.0, stem


def test_package_writes_one_step_per_part_plus_the_handle_free_combination() -> None:
    """Catch a missing file, a fused export, or the grip leaking into the combo."""

    with TemporaryDirectory(prefix="mid360-step-package-") as temporary:
        destination = Path(temporary)
        paths = build_step_package(PROJECT_ROOT, destination)
        assert tuple(path.name for path in paths) == (
            *(f"{stem}.step" for stem in EXPECTED_STEMS),
            COMBINED_STEP_NAME,
        )
        for path in paths:
            assert path.is_file() and path.stat().st_size > 1000, path.name

        # One solid per part file; exactly the four board/bracket parts in the
        # combined file, which is how the grip is proven to stay out of it.
        for path in paths[:-1]:
            assert _reimported_solid_count(path) == 1, path.name
        assert _reimported_solid_count(paths[-1]) == COMBINED_PART_COUNT
        assert COMBINED_PART_COUNT == len(EXPECTED_STEMS) - 2

        # CAD only: no meshes alongside the STEP files.
        assert not list(destination.glob("*.stl"))


if __name__ == "__main__":
    tests = tuple(
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    )
    for test in tests:
        test()
    print(f"{len(tests)} STEP-package tests passed")
