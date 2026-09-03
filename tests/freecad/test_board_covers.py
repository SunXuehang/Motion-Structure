"""FreeCAD checks for the UAV V3 compute-carrier cover plates."""

from math import isclose
from pathlib import Path
import sys

import FreeCAD as App
import Part

PROJECT_SRC = str(Path(__file__).resolve().parents[2] / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

from bracket.board_covers import (
    BoardCoverParameters,
    make_bottom_cover,
    make_top_cover,
    place_in_reference_coordinates,
)


TOLERANCE = 1e-6


def assert_void(shape: Part.Shape, probe: Part.Shape) -> None:
    """Assert that a literal probe does not intersect the cover."""

    assert shape.common(probe).Volume < TOLERANCE


def assert_cover_shape(
    shape: Part.Shape,
    x_length: float,
    z_min: float,
    z_max: float,
) -> None:
    """Catch an invalid, non-flat, oversized, or undersized cover."""

    assert shape.isValid()
    assert len(shape.Solids) == 1
    assert isclose(shape.BoundBox.XLength, x_length, abs_tol=TOLERANCE)
    assert isclose(shape.BoundBox.YLength, 78.0, abs_tol=TOLERANCE)
    assert isclose(shape.BoundBox.ZMin, z_min, abs_tol=TOLERANCE)
    assert isclose(shape.BoundBox.ZMax, z_max, abs_tol=TOLERANCE)


def top_plate_z0(p: BoardCoverParameters) -> float:
    """Underside of the upper cover plate, i.e. the top rim's root plane."""

    return p.board_mounting_z_max + p.top_standoff_height


def bottom_plate_z1(p: BoardCoverParameters) -> float:
    """Top face of the lower cover plate, i.e. the bottom rim's root plane."""

    return p.board_mounting_z_min - p.bottom_standoff_height


def test_m3_cover_parameters_match_the_approved_revision() -> None:
    """Catch a regression to the superseded M2.5 cover dimensions."""

    p = BoardCoverParameters()
    assert p.mounting_hole_diameter == 3.4
    assert p.standoff_outer_diameter == 6.0
    # This is the one place approved values are pinned; every other check in
    # this file derives its probes from the parameters so a sanctioned change
    # cannot leave stale magic numbers behind.
    assert (p.top_standoff_height, p.bottom_standoff_height) == (10.0, 13.0)
    assert (p.rim_thickness, p.top_rim_height, p.bottom_rim_height) == (
        1.5,
        4.0,
        5.5,
    )


def test_revised_cover_envelopes_preserve_the_outer_faces() -> None:
    """Catch a rim or taller lower standoff that changes the approved envelope."""

    top = make_top_cover(BoardCoverParameters())
    bottom = make_bottom_cover(BoardCoverParameters())
    p = BoardCoverParameters()
    assert_cover_shape(
        top,
        128.0,
        p.board_mounting_z_max,
        top_plate_z0(p) + p.plate_thickness,
    )
    assert_cover_shape(
        bottom,
        128.0,
        bottom_plate_z1(p) - p.plate_thickness,
        p.board_mounting_z_min,
    )


def test_both_covers_have_sixteen_m3_holes_aligned_to_mounting_rows() -> None:
    """Catch absent, misplaced, or wrongly sized extension holes."""

    p = BoardCoverParameters()
    covers_and_plate_z = (
        (make_top_cover(p), top_plate_z0(p)),
        (make_bottom_cover(p), bottom_plate_z1(p) - p.plate_thickness),
    )
    for cover, plate_z in covers_and_plate_z:
        cutter_z = plate_z - 0.1
        material_z = plate_z + 0.1
        for x in (-59.0, 59.0):
            for y in (-35.0, -25.0, -15.0, -5.0, 5.0, 15.0, 25.0, 35.0):
                hole_probe = Part.makeCylinder(
                    1.69,
                    3.2,
                    App.Vector(x, y, cutter_z),
                )
                assert_void(cover, hole_probe)

                material_probe = Part.makeCylinder(
                    0.08,
                    2.8,
                    App.Vector(
                        x + (1.78 if x > 0.0 else -1.78),
                        y,
                        material_z,
                    ),
                )
                assert isclose(
                    cover.common(material_probe).Volume,
                    material_probe.Volume,
                    rel_tol=1e-8,
                    abs_tol=TOLERANCE,
                )


def test_both_covers_use_the_literal_m3_mounting_pattern() -> None:
    """Catch a wrong M3 clearance or a rotated/shifted 100 x 70 mm pattern."""

    p = BoardCoverParameters()
    covers = (make_top_cover(p), make_bottom_cover(p))
    for cover in covers:
        z0 = cover.BoundBox.ZMin - 0.1
        for x in (-50.0, 50.0):
            for y in (-35.0, 35.0):
                assert_void(
                    cover,
                    Part.makeCylinder(
                        1.69,
                        cover.BoundBox.ZLength + 0.2,
                        App.Vector(x, y, z0),
                    ),
                )
        # Material immediately outside a Ø3.4 mm opening must remain present.
        material_probe = Part.makeCylinder(
            0.08,
            2.8,
            App.Vector(51.78, 35.0, cover.BoundBox.ZMin + 0.1),
        )
        assert isclose(
            cover.common(material_probe).Volume,
            material_probe.Volume,
            rel_tol=1e-8,
            abs_tol=TOLERANCE,
        )


def test_top_cover_uses_a_60_by_41_mm_r2_rectangular_opening() -> None:
    """Catch a square, sharp-cornered, undersized, or shifted top opening."""

    p = BoardCoverParameters()
    cover = make_top_cover(p)
    plate_z0 = top_plate_z0(p)
    z0 = plate_z0 - 0.1
    center_x = -0.153
    center_y = 6.830

    # The long axis must expose the full 57.8 mm heatsink projection.
    assert_void(
        cover,
        Part.makeCylinder(
            0.08,
            3.2,
            App.Vector(
                center_x + 29.5,
                center_y,
                z0,
            ),
        ),
    )

    # Material removed by the old 52 mm square must be restored on the short axis.
    restored_short_axis_material = Part.makeCylinder(
        0.08,
        2.8,
        App.Vector(center_x, center_y + 22.0, plate_z0 + 0.1),
    )
    assert isclose(
        cover.common(restored_short_axis_material).Volume,
        restored_short_axis_material.Volume,
        rel_tol=1e-8,
        abs_tol=TOLERANCE,
    )

    # R2 leaves material at the extreme 60 x 41 mm bounding-box corner.
    rounded_corner_material = Part.makeCylinder(
        0.08,
        2.8,
        App.Vector(
            center_x + 29.7,
            center_y + 20.2,
            plate_z0 + 0.1,
        ),
    )
    assert isclose(
        cover.common(rounded_corner_material).Volume,
        rounded_corner_material.Volume,
        rel_tol=1e-8,
        abs_tol=TOLERANCE,
    )


def test_bottom_cover_uses_the_24_mm_r3_small_fan_opening() -> None:
    """Catch a copied top opening or a shifted/undersized bottom opening."""

    cover = make_bottom_cover(BoardCoverParameters())
    z0 = cover.BoundBox.ZMin - 0.1
    # A point near the small fan opening's straight +X edge must be void.
    assert_void(
        cover,
        Part.makeCylinder(
            0.08,
            3.2,
            App.Vector(-11.3610 + 11.5, -2.3275, z0),
        ),
    )
    # The former 52 mm opening's +X region must be restored as solid plate.
    restored_material = Part.makeCylinder(
        0.08,
        2.8,
        App.Vector(
            10.0,
            20.0,
            cover.BoundBox.ZMin + 0.1,
        ),
    )
    assert isclose(
        cover.common(restored_material).Volume,
        restored_material.Volume,
        rel_tol=1e-8,
        abs_tol=TOLERANCE,
    )


def test_14_by_18_mm_r1_imu_opening_is_cut_only_in_the_bottom_cover() -> None:
    """Catch an absent, sharp-cornered, shifted, or top-cover IMU opening."""

    p = BoardCoverParameters()
    bottom = make_bottom_cover(p)
    top = make_top_cover(p)
    center_x = 33.6671
    center_y = -2.5159

    imu_center_probe = Part.makeCylinder(
        0.08,
        3.2,
        App.Vector(center_x, center_y, bottom.BoundBox.ZMin - 0.1),
    )
    assert_void(bottom, imu_center_probe)

    # Both axes must extend one millimetre past the old 12 x 16 mm opening.
    for x, y in (
        (center_x + 6.5, center_y),
        (center_x, center_y + 8.5),
    ):
        expanded_opening_probe = Part.makeCylinder(
            0.08,
            3.2,
            App.Vector(x, y, bottom.BoundBox.ZMin - 0.1),
        )
        assert_void(bottom, expanded_opening_probe)

    # Material immediately beyond the new opening must remain present.
    for x, y in (
        (center_x + 7.5, center_y),
        (center_x, center_y + 9.5),
    ):
        restored_edge_material = Part.makeCylinder(
            0.08,
            2.8,
            App.Vector(x, y, bottom.BoundBox.ZMin + 0.1),
        )
        assert isclose(
            bottom.common(restored_edge_material).Volume,
            restored_edge_material.Volume,
            rel_tol=1e-8,
            abs_tol=TOLERANCE,
        )

    # R1 leaves material at the extreme 14 x 18 mm bounding-box corner.
    rounded_corner_material = Part.makeCylinder(
        0.08,
        2.8,
        App.Vector(
            center_x + 6.8,
            center_y + 8.8,
            bottom.BoundBox.ZMin + 0.1,
        ),
    )
    assert isclose(
        bottom.common(rounded_corner_material).Volume,
        rounded_corner_material.Volume,
        rel_tol=1e-8,
        abs_tol=TOLERANCE,
    )

    top_center_probe = Part.makeCylinder(
        0.08,
        2.8,
        App.Vector(center_x, center_y, top_plate_z0(BoardCoverParameters()) + 0.1),
    )
    assert isclose(
        top.common(top_center_probe).Volume,
        top_center_probe.Volume,
        rel_tol=1e-8,
        abs_tol=TOLERANCE,
    )


def test_both_covers_have_od6_standoffs_and_m3_clearance() -> None:
    """Catch a non-M3 hole or a standoff other than an OD6 hollow cylinder."""

    p = BoardCoverParameters()
    cases = (
        (
            make_top_cover(p),
            p.board_mounting_z_max,
            p.top_standoff_height,
            p.board_mounting_z_max + 0.1,
        ),
        (
            make_bottom_cover(p),
            bottom_plate_z1(p) - p.plate_thickness + p.plate_thickness,
            p.bottom_standoff_height,
            5.0,
        ),
    )
    for cover, z0, height, free_standoff_z0 in cases:
        for x in (-50.0, 50.0):
            for y in (-35.0, 35.0):
                assert_void(
                    cover,
                    Part.makeCylinder(
                        1.69,
                        height + 0.2,
                        App.Vector(x, y, z0 - 0.1),
                    ),
                )
                wall = Part.makeCylinder(
                    0.04,
                    height - 0.2,
                    App.Vector(x + 2.90, y, z0 + 0.1),
                )
                assert isclose(
                    cover.common(wall).Volume, wall.Volume, abs_tol=TOLERANCE
                )
                assert_void(
                    cover,
                    Part.makeCylinder(
                        0.04,
                        2.0,
                        App.Vector(
                            x + (3.10 if x > 0.0 else -3.10),
                            y,
                            free_standoff_z0,
                        ),
                    ),
                )


def test_board_facing_rims_enclose_corner_standoffs_with_square_roots() -> None:
    """Verify literal rectangular rims, square roots, and corner fusion."""

    p = BoardCoverParameters()
    cases = (
        (make_top_cover(p), top_plate_z0(p), p.top_rim_height, -1.0),
        (make_bottom_cover(p), bottom_plate_z1(p), p.bottom_rim_height, 1.0),
    )
    for cover, root_z, rim_height, height_direction in cases:
        assert cover.isValid() and len(cover.Solids) == 1
        rim_slice_z0 = (
            root_z - rim_height + 0.2
            if height_direction < 0.0
            else root_z + 1.2
        )

        # Cropping away all four standoffs exposes literal rim-only envelopes:
        # the old centreline rim measures 101.5 x 71.5 mm here.
        horizontal_rim = cover.common(
            Part.makeBox(
                80.0,
                90.0,
                0.2,
                App.Vector(-40.0, -45.0, rim_slice_z0),
            )
        )
        vertical_rim = cover.common(
            Part.makeBox(
                120.0,
                50.0,
                0.2,
                App.Vector(-60.0, -25.0, rim_slice_z0),
            )
        )
        assert isclose(horizontal_rim.BoundBox.YLength, 76.0, abs_tol=TOLERANCE)
        assert isclose(vertical_rim.BoundBox.XLength, 106.0, abs_tol=TOLERANCE)

        # A real wall-centre probe fixes the literal rim height, independently
        # of the nearby corner standoffs.
        wall_top = App.Vector(
            0.0, 37.0, root_z + height_direction * (rim_height - 0.2)
        )
        wall_above = App.Vector(
            0.0, 37.0, root_z + height_direction * (rim_height + 0.2)
        )
        at_height = Part.makeSphere(0.01, wall_top)
        above_height = Part.makeSphere(0.01, wall_above)
        assert isclose(
            cover.common(at_height).Volume, at_height.Volume, abs_tol=TOLERANCE
        )
        assert isclose(cover.common(above_height).Volume, 0.0, abs_tol=TOLERANCE)

        # Literal mid-height cuts verify the 103 x 73 inner boundary through
        # its 1.5 mm sidewalls, without deriving the expectation from p.
        for probe in (
            Part.makeBox(
                0.2,
                5.0,
                0.2,
                App.Vector(-0.1, 34.0, rim_slice_z0),
            ),
            Part.makeBox(
                5.0,
                0.2,
                0.2,
                App.Vector(49.0, -0.1, rim_slice_z0),
            ),
        ):
            wall = cover.common(probe)
            assert isclose(
                wall.Volume,
                1.5 * 0.2 * 0.2,
                abs_tol=TOLERANCE,
            )

        # The rim is now a direct 90-degree plate/wall connection: no root R1
        # cylindrical surface is permitted.
        r1_root_faces = [
            face
            for face in cover.Faces
            if hasattr(face.Surface, "Radius")
            and isclose(face.Surface.Radius, 1.0, abs_tol=TOLERANCE)
            and face.Area > 30.0
        ]
        assert not r1_root_faces

        # Both outer and inner wall roots remain literal 90-degree B-rep
        # lines, rather than an arc replacement.
        outer_sharp_edges = []
        inner_sharp_edges = []
        for edge in cover.Edges:
            bounds = edge.BoundBox
            at_root = (
                isclose(bounds.ZMin, root_z, abs_tol=TOLERANCE)
                and isclose(bounds.ZMax, root_z, abs_tol=TOLERANCE)
            )
            outer_x = bounds.XLength <= TOLERANCE and isclose(
                abs(bounds.XMin), 53.0, abs_tol=TOLERANCE
            )
            outer_y = bounds.YLength <= TOLERANCE and isclose(
                abs(bounds.YMin), 38.0, abs_tol=TOLERANCE
            )
            inner_x = bounds.XLength <= TOLERANCE and isclose(
                abs(bounds.XMin), 51.5, abs_tol=TOLERANCE
            )
            inner_y = bounds.YLength <= TOLERANCE and isclose(
                abs(bounds.YMin), 36.5, abs_tol=TOLERANCE
            )
            if at_root and (outer_x or outer_y):
                outer_sharp_edges.append(edge)
            if at_root and (inner_x or inner_y):
                inner_sharp_edges.append(edge)
        assert len(outer_sharp_edges) == 4
        assert len(inner_sharp_edges) == 4

        # Each Ø6 corner standoff overlaps the outward rim faces and is part
        # of the same printable solid, rather than merely touching it.  The
        # probe stays strictly inside the rim's own height band -- it used to
        # straddle the rim/plate joint, which only held while the rim was 2 mm.
        bridge_z0 = (
            root_z - rim_height + 0.2 if height_direction < 0.0 else root_z + 0.2
        )
        # Rim wall centreline, i.e. where wall and standoff quadrant overlap.
        wall_offset = (
            p.mount_pitch_y / 2.0
            + p.standoff_outer_diameter / 2.0
            - p.rim_thickness / 2.0
        )
        for x in (-50.0, 50.0):
            for y in (-35.0, 35.0):
                bridge = Part.makeBox(
                    0.2,
                    0.2,
                    rim_height - 0.4,
                    App.Vector(
                        x - 0.1,
                        (wall_offset if y > 0.0 else -wall_offset) - 0.1,
                        bridge_z0,
                    ),
                )
                assert isclose(
                    cover.common(bridge).Volume, bridge.Volume, abs_tol=TOLERANCE
                )


def test_reference_placement_matches_the_four_cad_standoffs() -> None:
    """Catch a wrong board centre, handedness, or 80-degree CAD rotation."""

    placed = place_in_reference_coordinates(
        make_top_cover(BoardCoverParameters()),
        BoardCoverParameters(),
    )
    assert isclose(placed.BoundBox.Center.x, 47.7845, abs_tol=1e-4)
    assert isclose(placed.BoundBox.Center.y, 60.6035, abs_tol=1e-4)

    standoff_centres = (
        (73.5705, 5.2855),
        (90.9353, 103.7663),
        (4.6339, 17.4409),
        (21.9988, 115.9217),
    )
    for x, y in standoff_centres:
        assert_void(
            placed,
            Part.makeCylinder(
                1.69,
                3.2,
                App.Vector(x, y, placed.BoundBox.ZMin - 0.1),
            ),
        )


TESTS = (
    test_m3_cover_parameters_match_the_approved_revision,
    test_revised_cover_envelopes_preserve_the_outer_faces,
    test_both_covers_have_sixteen_m3_holes_aligned_to_mounting_rows,
    test_both_covers_use_the_literal_m3_mounting_pattern,
    test_top_cover_uses_a_60_by_41_mm_r2_rectangular_opening,
    test_bottom_cover_uses_the_24_mm_r3_small_fan_opening,
    test_14_by_18_mm_r1_imu_opening_is_cut_only_in_the_bottom_cover,
    test_both_covers_have_od6_standoffs_and_m3_clearance,
    test_board_facing_rims_enclose_corner_standoffs_with_square_roots,
    test_reference_placement_matches_the_four_cad_standoffs,
)


if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"{len(TESTS)} board-cover geometry tests passed")
