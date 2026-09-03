"""Checks for the four-part 256 x 256 mm print-plate STEP package."""

from itertools import combinations
from math import isclose
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import FreeCAD as App
import Import
import Part

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_SRC = str(PROJECT_ROOT / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

try:
    from bracket.print_plate import build_print_plate, build_print_plate_outputs
except ImportError:
    build_print_plate = None
    build_print_plate_outputs = None


TOLERANCE = 1e-6
MIN_PART_CLEARANCE = 8.0


def test_four_parts_fit_the_256_mm_plate_without_touching() -> None:
    """Catch a missing part, wrong orientation, overlap, or out-of-bed placement."""

    assert build_print_plate is not None, "print-plate builder is missing"
    parts = build_print_plate()
    assert tuple(name for name, _shape in parts) == (
        "Part B tilt base",
        "Upper board cover",
        "Lower board cover",
        "Part A radar plate",
    )

    expected_bounds = {
        "Part B tilt base": (-124.0, -26.0, -14.0, 114.0),
        "Upper board cover": (-10.0, 118.0, 16.0, 94.0),
        "Lower board cover": (-10.0, 118.0, -84.0, -6.0),
        "Part A radar plate": (-109.5, -40.5, -107.5, -22.5),
    }
    for name, shape in parts:
        assert shape.isValid() and len(shape.Solids) == 1
        bounds = shape.BoundBox
        assert isclose(bounds.XMin, expected_bounds[name][0], abs_tol=TOLERANCE)
        assert isclose(bounds.XMax, expected_bounds[name][1], abs_tol=TOLERANCE)
        assert isclose(bounds.YMin, expected_bounds[name][2], abs_tol=TOLERANCE)
        assert isclose(bounds.YMax, expected_bounds[name][3], abs_tol=TOLERANCE)
        assert isclose(bounds.ZMin, 0.0, abs_tol=TOLERANCE)
        assert -128.0 <= bounds.XMin and bounds.XMax <= 128.0
        assert -128.0 <= bounds.YMin and bounds.YMax <= 128.0

    for (_left_name, left), (_right_name, right) in combinations(parts, 2):
        x_clearance = max(
            right.BoundBox.XMin - left.BoundBox.XMax,
            left.BoundBox.XMin - right.BoundBox.XMax,
            0.0,
        )
        y_clearance = max(
            right.BoundBox.YMin - left.BoundBox.YMax,
            left.BoundBox.YMin - right.BoundBox.YMax,
            0.0,
        )
        assert max(x_clearance, y_clearance) >= MIN_PART_CLEARANCE
        assert left.common(right).Volume < TOLERANCE


def test_every_part_has_a_broad_printing_face_on_z_zero() -> None:
    """Catch a cover being exported with its standoffs against the build plate."""

    assert build_print_plate is not None, "print-plate builder is missing"
    for _name, shape in build_print_plate():
        first_layer = shape.common(
            Part.makeBox(256.0, 256.0, 0.2, App.Vector(-128.0, -128.0, 0.0))
        )
        assert first_layer.Volume > 500.0


def test_print_plate_step_round_trip_keeps_four_independent_solids() -> None:
    """Catch a missing/corrupt STEP or accidental fusion of the four parts."""

    assert build_print_plate_outputs is not None, "print-plate exporter is missing"
    with TemporaryDirectory(prefix="mid360-print-plate-") as temporary:
        step_path = build_print_plate_outputs(PROJECT_ROOT, Path(temporary))
        assert step_path.is_file() and step_path.stat().st_size > 1000

        document = App.newDocument("PrintPlateStepRoundTrip")
        try:
            Import.insert(str(step_path), document.Name)
            document.recompute()
            imported_parts = tuple(
                obj
                for obj in document.Objects
                if obj.TypeId == "Part::Feature"
                and hasattr(obj, "Shape")
                and not obj.Shape.isNull()
            )
            assert len(imported_parts) == 4
            assert all(len(obj.Shape.Solids) == 1 for obj in imported_parts)
        finally:
            App.closeDocument(document.Name)


if __name__ == "__main__":
    test_four_parts_fit_the_256_mm_plate_without_touching()
    test_every_part_has_a_broad_printing_face_on_z_zero()
    test_print_plate_step_round_trip_keeps_four_independent_solids()
    print("3 print-plate tests passed")
