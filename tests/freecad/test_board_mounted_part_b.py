"""Geometry checks for the board-cover-mounted Part B variant."""

from math import isclose, pi
from pathlib import Path
import sys

import FreeCAD as App
import Part

PROJECT_SRC = str(Path(__file__).resolve().parents[2] / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

from bracket import freecad_geometry
from bracket.parameters import BracketParameters


TOLERANCE = 1e-6


def test_board_mounted_part_b_has_sixteen_holes_matching_the_top_cover() -> None:
    """Catch a missing/misaligned hole in either eight-hole mounting column."""

    shape = freecad_geometry.make_board_mounted_part_b()
    assert shape.isValid()
    assert len(shape.Solids) == 1
    assert isclose(shape.BoundBox.XLength, 128.0, abs_tol=TOLERANCE)
    assert isclose(shape.BoundBox.YMin, -39.0, abs_tol=TOLERANCE)
    assert isclose(shape.BoundBox.YMax, 59.0, abs_tol=TOLERANCE)
    assert isclose(shape.BoundBox.YLength, 98.0, abs_tol=TOLERANCE)

    low_section = Part.makeBox(
        128.0,
        78.0,
        0.5,
        App.Vector(-64.0, -39.0, 1.75),
    )
    p = BracketParameters()
    fan_area = (
        p.b_fan_opening_length * p.b_fan_opening_width
        - (4.0 - pi) * p.b_fan_opening_corner_radius**2
    )
    expected_area = (
        128.0 * 78.0
        - (4.0 - pi) * 4.0**2
        - 16.0 * pi * 1.70**2
        - fan_area
    )
    assert isclose(
        shape.common(low_section).Volume,
        expected_area * 0.5,
        rel_tol=1e-9,
        abs_tol=TOLERANCE,
    )
    original_body = shape.common(
        Part.makeBox(128.0, 78.0, 4.0, App.Vector(-64.0, -39.0, 0.0))
    )
    assert isclose(original_body.BoundBox.XMin, -64.0, abs_tol=TOLERANCE)
    assert isclose(original_body.BoundBox.XMax, 64.0, abs_tol=TOLERANCE)
    assert isclose(original_body.BoundBox.YMin, -39.0, abs_tol=TOLERANCE)
    assert isclose(original_body.BoundBox.YMax, 39.0, abs_tol=TOLERANCE)

    for x in (-59.0, 59.0):
        for y in (-35.0, -25.0, -15.0, -5.0, 5.0, 15.0, 25.0, 35.0):
            hole_probe = Part.makeCylinder(
                1.69,
                4.0,
                App.Vector(x, y, 0.0),
            )
            assert shape.common(hole_probe).Volume < TOLERANCE
            rim_probe = Part.makeCylinder(
                0.04,
                3.8,
                App.Vector(x + 1.75, y, 0.1),
            )
            assert isclose(
                shape.common(rim_probe).Volume,
                rim_probe.Volume,
                rel_tol=1e-9,
                abs_tol=TOLERANCE,
            )


def test_board_mounted_part_b_keeps_standoff_tool_envelopes_clear() -> None:
    """Catch a root rib blocking any Ø5.6 corner standoff envelope."""

    shape = freecad_geometry.make_board_mounted_part_b()
    for x in (-59.0, 59.0):
        for y in (-35.0, 35.0):
            tool_envelope_above_plate = Part.makeCylinder(
                2.8,
                12.0,
                App.Vector(x, y, 4.0),
            )
            assert shape.common(tool_envelope_above_plate).Volume < TOLERANCE


def test_board_mounted_part_b_moves_both_root_ribs_onto_the_ear_footprint() -> None:
    """Catch leaving the rear rib tangent to the sector wall at Y=-20 mm."""

    shape = freecad_geometry.make_board_mounted_part_b()
    for x in (-42.0, 42.0):
        for y in (-16.0, 16.0):
            probe = Part.makeSphere(0.15, App.Vector(x, y, 7.0))
            assert isclose(shape.common(probe).Volume, probe.Volume, abs_tol=TOLERANCE)
        for y in (-24.0, 24.0):
            probe = Part.makeSphere(0.15, App.Vector(x, y, 7.0))
            assert shape.common(probe).Volume < TOLERANCE


def test_r45_sector_ears_stay_inside_the_78_mm_top_cover_width() -> None:
    """Catch sector or rib material extending beyond either top-cover side."""

    shape = freecad_geometry.make_board_mounted_part_b()
    above_base = shape.common(
        Part.makeBox(200.0, 200.0, 120.0, App.Vector(-100.0, -100.0, 4.01))
    )

    assert above_base.BoundBox.YMin >= -39.0 - TOLERANCE
    assert above_base.BoundBox.YMax <= 39.0 + TOLERANCE


if __name__ == "__main__":
    test_board_mounted_part_b_has_sixteen_holes_matching_the_top_cover()
    test_board_mounted_part_b_keeps_standoff_tool_envelopes_clear()
    test_board_mounted_part_b_moves_both_root_ribs_onto_the_ear_footprint()
    test_r45_sector_ears_stay_inside_the_78_mm_top_cover_width()
    print("4 board-mounted Part B tests passed")
