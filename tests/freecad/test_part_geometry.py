"""Mutation-sensitive FreeCAD integration checks for both printable solids."""

from math import cos, isclose, pi, radians, sin
from pathlib import Path
import sys

import FreeCAD as App
import Part

PROJECT_SRC = str(Path(__file__).resolve().parents[2] / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

from bracket import freecad_geometry as freecad_geometry_module
from bracket.freecad_geometry import (
    make_arc_slot_cutter,
    make_board_mounted_part_b,
    make_part_a,
    make_part_b,
)
from bracket.assembly import placement_for_angle
from bracket.kinematics import arc_point_yz
from bracket.parameters import BracketParameters, derive


TOLERANCE = 1e-6


def assert_single_valid_solid(shape: Part.Shape) -> None:
    """Assert the export boundary shared by both printable parts."""

    assert shape.isValid()
    assert len(shape.Solids) == 1
    assert shape.Volume > 1.0


def assert_fully_void(shape: Part.Shape, probe: Part.Shape) -> None:
    """Assert that none of a literal probe intersects the built solid."""

    assert shape.common(probe).Volume < TOLERANCE


def assert_fully_solid(shape: Part.Shape, probe: Part.Shape) -> None:
    """Assert that all of a literal probe is occupied by the built solid."""

    assert isclose(
        shape.common(probe).Volume,
        probe.Volume,
        rel_tol=1e-9,
        abs_tol=TOLERANCE,
    )


def x_cylinder(
    x0: float, length: float, y: float, z: float, radius: float
) -> Part.Shape:
    """Return a literal X-axis feature probe."""

    return Part.makeCylinder(
        radius,
        length,
        App.Vector(x0, y, z),
        App.Vector(1.0, 0.0, 0.0),
    )


def test_part_a_is_a_six_mm_flat_plate_without_ears_or_bosses() -> None:
    """Catch retained side bosses/ears or a plate other than 6 mm thick."""

    a = make_part_a(BracketParameters())

    assert_single_valid_solid(a)
    assert isclose(a.BoundBox.XLength, 69.0, abs_tol=TOLERANCE)
    assert isclose(a.BoundBox.YLength, 85.0, abs_tol=TOLERANCE)
    assert isclose(a.BoundBox.ZMin, -6.0, abs_tol=TOLERANCE)
    assert isclose(a.BoundBox.ZMax, 0.0, abs_tol=TOLERANCE)


def test_part_a_has_central_vent() -> None:
    """Catch filling the required 32 x 20 mm through-vent."""

    vent_probe = Part.makeCylinder(3.0, 4.0, App.Vector(0.0, 0.0, -4.0))

    assert_fully_void(make_part_a(BracketParameters()), vent_probe)


def test_part_a_preserves_all_four_mid360_mounting_holes_at_3_5_mm() -> None:
    """Catch missing, rotated, or resized MID-360 mounting holes."""

    a = make_part_a(BracketParameters())
    bracket_centers = (
        (-18.0, -24.0),
        (-18.0, 24.0),
        (18.0, -24.0),
        (18.0, 24.0),
    )
    for x, y in bracket_centers:
        probe = Part.makeCylinder(1.74, 6.0, App.Vector(x, y, -6.0))
        assert_fully_void(a, probe)
        material_probe = Part.makeCylinder(
            0.04,
            5.8,
            App.Vector(x + 1.80, y, -5.9),
        )
        assert_fully_solid(a, material_probe)

    old_rotated_centers = (
        (-24.0, -18.0),
        (-24.0, 18.0),
        (24.0, -18.0),
        (24.0, 18.0),
    )
    for x, y in old_rotated_centers:
        probe = Part.makeCylinder(0.5, 3.0, App.Vector(x, y, -3.5))
        assert_fully_solid(a, probe)


def test_part_a_has_six_mm_deep_pivot_side_pilot_holes() -> None:
    """Catch a missing pivot pilot, wrong axis height, or excessive depth."""

    a = make_part_a(BracketParameters())
    assert_fully_void(a, x_cylinder(-34.5, 6.0, 38.0, -3.0, 1.44))
    assert_fully_void(a, x_cylinder(28.5, 6.0, 38.0, -3.0, 1.44))
    assert_fully_solid(a, x_cylinder(-34.4, 5.8, 38.0, -1.49, 0.04))
    assert_fully_solid(a, x_cylinder(28.6, 5.8, 38.0, -1.49, 0.04))
    assert_fully_solid(a, x_cylinder(-27.5, 0.5, 38.0, -3.0, 0.3))
    assert_fully_solid(a, x_cylinder(27.0, 0.5, 38.0, -3.0, 0.3))


def test_part_a_has_seven_mm_deep_lock_side_pilot_holes() -> None:
    """Catch lock holes too shallow for the outer-face rail recess."""

    a = make_part_a(BracketParameters())
    assert_fully_void(a, x_cylinder(-34.5, 7.0, -7.0, -3.0, 1.44))
    assert_fully_void(a, x_cylinder(27.5, 7.0, -7.0, -3.0, 1.44))
    assert_fully_solid(a, x_cylinder(-34.4, 6.8, -7.0, -1.49, 0.04))
    assert_fully_solid(a, x_cylinder(27.6, 6.8, -7.0, -1.49, 0.04))
    assert_fully_solid(a, x_cylinder(-26.5, 0.5, -7.0, -3.0, 0.3))
    assert_fully_solid(a, x_cylinder(26.0, 0.5, -7.0, -3.0, 0.3))


def test_part_a_has_rear_relief() -> None:
    """Catch filling the 34 x 12 mm rear cable relief."""

    relief_probe = Part.makeCylinder(2.0, 4.0, App.Vector(0.0, -37.0, -4.0))

    assert_fully_void(make_part_a(BracketParameters()), relief_probe)


def test_part_b_bounds_match_the_board_top_cover() -> None:
    """Catch detached sectors or a Part B envelope other than 128 x 98 mm."""

    p = BracketParameters()
    b = make_part_b(p)

    assert_single_valid_solid(b)
    assert isclose(b.BoundBox.XLength, 128.0, abs_tol=TOLERANCE)
    assert isclose(b.BoundBox.YMin, -39.0, abs_tol=TOLERANCE)
    assert isclose(b.BoundBox.YMax, 59.0, abs_tol=TOLERANCE)
    assert isclose(b.BoundBox.YLength, 98.0, abs_tol=TOLERANCE)
    assert isclose(
        b.BoundBox.ZLength,
        p.b_base_thickness + derive(p).sector_top_above_base,
        abs_tol=TOLERANCE,
    )
    section = Part.makeBox(128.0, 78.0, 0.5, App.Vector(-64.0, -39.0, 2.0))
    fan_area = (
        p.b_fan_opening_length * p.b_fan_opening_width
        - (4.0 - pi) * p.b_fan_opening_corner_radius**2
    )
    expected_rounded_area = 128.0 * 78.0 - (4.0 - pi) * 4.0**2 - fan_area

    assert isclose(
        b.common(section).Volume,
        expected_rounded_area * 0.5,
        rel_tol=1e-9,
        abs_tol=TOLERANCE,
    )


def test_part_b_fan_opening_matches_the_cover_and_clears_both_ears() -> None:
    """Catch a B opening that drifts off the cover fan or reaches a sector ear."""

    from bracket.board_covers import BoardCoverParameters

    p = BracketParameters()
    cover = BoardCoverParameters()
    # parameters.py cannot import board_covers (it would pull in FreeCAD), so
    # the two coordinate sets are pinned together here instead.
    assert (p.b_fan_center_x, p.b_fan_center_y) == (
        cover.top_fan_center_x,
        cover.top_fan_center_y,
    )
    assert (p.b_fan_opening_length, p.b_fan_opening_width) == (
        cover.top_fan_opening_length,
        cover.top_fan_opening_width,
    )

    b = make_part_b(p)
    half_x = p.b_fan_opening_length / 2.0
    half_y = p.b_fan_opening_width / 2.0
    # The opening is cut clean through the 4 mm plate...
    through = Part.makeBox(
        p.b_fan_opening_length - 2.0 * p.b_fan_opening_corner_radius,
        p.b_fan_opening_width - 2.0 * p.b_fan_opening_corner_radius,
        p.b_base_thickness + 0.4,
        App.Vector(
            p.b_fan_center_x - half_x + p.b_fan_opening_corner_radius,
            p.b_fan_center_y - half_y + p.b_fan_opening_corner_radius,
            -0.2,
        ),
    )
    assert b.common(through).Volume < TOLERANCE
    # ...and a strip of plate survives between the opening and each ear.
    for sign in (-1.0, 1.0):
        inner_ear_x = sign * p.b_inner_width / 2.0
        strip = Part.makeBox(
            2.0,
            10.0,
            p.b_base_thickness - 0.4,
            App.Vector(
                inner_ear_x - (2.0 if sign > 0.0 else 0.0),
                p.b_fan_center_y - 5.0,
                0.2,
            ),
        )
        assert isclose(
            b.common(strip).Volume, strip.Volume, rel_tol=1e-6, abs_tol=TOLERANCE
        )


def test_part_b_keeps_the_d435i_shelf_and_blends_its_rear_reentrant_corners() -> None:
    """Catch a shifted shelf, wrong-direction rear round, square fill, or chamfer.

    This fails if the rear transition stops retaining the reentrant-corner
    material, fills the quarter-circle void, or moves either R4 tangency.
    """

    b = make_part_b(BracketParameters())

    assert_single_valid_solid(b)
    assert isclose(b.BoundBox.YMin, -39.0, abs_tol=TOLERANCE)
    assert isclose(b.BoundBox.YMax, 59.0, abs_tol=TOLERANCE)

    # Literal probes lie inside/outside the real front R4 arc, rejecting square,
    # chamfered, and realistically wrong-radius corners.
    for x in (-44.35, 44.35):
        assert_fully_solid(
            b, Part.makeCylinder(0.01, 3.8, App.Vector(x, 58.20, 0.1))
        )
    for x in (-44.42, 44.42):
        assert_fully_void(
            b, Part.makeCylinder(0.01, 3.8, App.Vector(x, 58.20, 0.1))
        )

    # Each rear transition adds the 4 x 4 mm connection square less a
    # quarter circle R4 centred at (±50, 43).  The first probe is material at
    # the old reentrant corner; the following probes span the concave arc at
    # both tangent ends.  A former exterior R4 has no added material here, a
    # full square fills the voids, and a triangle fills the near-tangent voids.
    for side in (-1.0, 1.0):
        sign = side
        assert_fully_solid(
            b,
            Part.makeCylinder(0.02, 3.8, App.Vector(sign * 46.10, 39.10, 0.1)),
        )
        assert_fully_void(
            b,
            Part.makeCylinder(0.02, 3.8, App.Vector(sign * 49.75, 39.03, 0.1)),
        )
        assert_fully_solid(
            b,
            Part.makeCylinder(0.02, 3.8, App.Vector(sign * 49.30, 39.03, 0.1)),
        )
        assert_fully_void(
            b,
            Part.makeCylinder(0.02, 3.8, App.Vector(sign * 46.03, 42.75, 0.1)),
        )
        assert_fully_solid(
            b,
            Part.makeCylinder(0.02, 3.8, App.Vector(sign * 46.03, 42.30, 0.1)),
        )

    clearance_probe = Part.makeCylinder(3.39, 3.8, App.Vector(0.0, 49.0, 0.1))
    assert_fully_void(b, clearance_probe)
    assert_fully_solid(
        b,
        Part.makeCylinder(0.01, 3.8, App.Vector(3.41, 49.0, 0.1)),
    )


def test_part_b_d435i_reliefs_preserve_wall_outside_measured_collision_band() -> None:
    """Keep D435i reliefs to measured mesh contact plus a stated small allowance."""

    b = make_part_b(BracketParameters())
    tolerance = getattr(
        freecad_geometry_module,
        "D435I_CAMERA_RELIEF_MESH_AND_MANUFACTURING_TOLERANCE_MM",
        None,
    )
    envelopes = getattr(
        freecad_geometry_module,
        "D435I_CAMERA_COLLISION_ENVELOPES_LOCAL_MM",
        None,
    )

    outward_y_tolerance = getattr(
        freecad_geometry_module,
        "D435I_CAMERA_RELIEF_OUTWARD_Y_TERMINATION_TOLERANCE_MM",
        None,
    )
    assert tolerance == 0.05
    assert outward_y_tolerance == 0.15
    assert envelopes is not None and len(envelopes) == 2
    # The actual mesh collisions are thin surface sections.  The named
    # allowance must not turn them back into the old 6 x 1.2 x 26 mm boxes.
    assert all(
        x_max - x_min + 2.0 * tolerance < 4.3
        and y_max - y_min + tolerance + outward_y_tolerance < 0.4
        and z_max - z_min + 2.0 * tolerance < 3.0
        for x_min, x_max, y_min, y_max, z_min, z_max in envelopes
    )

    # Real probes retain wall material 0.25 mm ahead of the measured mesh
    # surface, while the collision band at z=14 mm stays open.
    for x in (-37.0, 35.2):
        assert_fully_solid(b, Part.makeSphere(0.04, App.Vector(x, 38.6, 14.0)))

    # The actual camera-contact band remains open, and the subtraction must
    # not split the printable Part B into disconnected solids.
    assert_fully_void(b, Part.makeSphere(0.04, App.Vector(-37.0, 38.9, 14.0)))
    assert_single_valid_solid(b)


def test_d435i_screw_envelope_clears_part_b_and_part_a_at_all_working_angles() -> None:
    """Catch a shelf hole or A pose that clips the conservative 1/4-20 envelope."""

    p = BracketParameters()
    shaft = Part.makeCylinder(
        p.d435i_screw_shaft_diameter / 2.0,
        p.b_base_thickness,
        App.Vector(0.0, 49.0, 0.0),
    )
    head = Part.makeCylinder(
        p.d435i_screw_head_diameter / 2.0,
        p.d435i_screw_head_height,
        App.Vector(0.0, 49.0, -p.d435i_screw_head_height),
    )
    envelope = shaft.fuse(head)

    assert make_part_b(p).common(envelope).Volume < TOLERANCE
    for angle in (0.0, 20.0, 40.0):
        part_a = make_part_a(p).copy()
        part_a.Placement = placement_for_angle(p, angle)
        assert part_a.common(envelope).Volume < TOLERANCE


def test_part_b_has_four_reduced_ten_by_eight_by_six_root_ribs() -> None:
    """Catch restoring oversized ribs or deleting the compact root support."""

    b = make_part_b(BracketParameters())
    for x in (-42.0, 42.0):
        for y in (-16.0, 16.0):
            assert_fully_solid(b, Part.makeSphere(0.15, App.Vector(x, y, 7.0)))
    for x in (-50.0, 50.0):
        for y in (-16.0, 16.0):
            assert_fully_void(b, Part.makeSphere(0.15, App.Vector(x, y, 5.0)))
    for x in (-42.0, 42.0):
        for y in (-24.0, 24.0):
            assert_fully_void(b, Part.makeSphere(0.15, App.Vector(x, y, 7.0)))
        for y in (-29.0, 29.0):
            assert_fully_void(b, Part.makeSphere(0.15, App.Vector(x, y, 7.0)))
        for y in (-16.0, 16.0):
            assert_fully_void(b, Part.makeSphere(0.15, App.Vector(x, y, 11.0)))


def test_r45_part_b_has_both_pivot_holes() -> None:
    """Catch either pivot opening being missing, undersized, or oversized."""

    b = make_part_b(BracketParameters())
    assert_fully_void(b, x_cylinder(-38.8, 3.8, 33.0, 14.0, 1.69))
    assert_fully_void(b, x_cylinder(35.0, 3.8, 33.0, 14.0, 1.69))
    assert_fully_solid(b, x_cylinder(-38.8, 3.8, 34.75, 14.0, 0.04))
    assert_fully_solid(b, x_cylinder(35.0, 3.8, 34.75, 14.0, 0.04))


def test_r45_part_b_has_slot_void_at_all_working_angles_on_both_walls() -> None:
    """Catch filling either arc slot or truncating its 0°–40° working path."""

    p = BracketParameters()
    b = make_part_b(p)
    for angle in (0.0, 20.0, 40.0):
        y, z_above_base = arc_point_yz(p, angle)
        z = p.b_base_thickness + z_above_base
        assert_fully_void(b, x_cylinder(-38.8, 3.8, y, z, 1.3))
        assert_fully_void(b, x_cylinder(35.0, 3.8, y, z, 1.3))


def test_r45_part_b_slot_accepts_a_3_39_mm_midpoint_gauge() -> None:
    """Catch a lock slot narrower or wider than the 3.4 mm M3 clearance."""

    p = BracketParameters()
    b = make_part_b(p)
    midpoint_angle = radians(20.0)
    y, z_above_base = arc_point_yz(p, 20.0)
    z = p.b_base_thickness + z_above_base

    for x0 in (-38.8, 35.0):
        gauge = x_cylinder(x0, 3.8, y, z, 3.39 / 2.0)
        assert_fully_void(b, gauge)

    outside_y = y - 1.75 * cos(midpoint_angle)
    outside_z = z + 1.75 * sin(midpoint_angle)
    assert_fully_solid(
        b,
        x_cylinder(-37.8, 2.8, outside_y, outside_z, 0.04),
    )
    assert_fully_solid(
        b,
        x_cylinder(35.0, 2.8, outside_y, outside_z, 0.04),
    )


def test_board_mounted_part_b_has_sixteen_3_4_mm_base_holes() -> None:
    """Catch a missing, undersized, or oversized M3 base mounting hole."""

    b = make_board_mounted_part_b()
    for x in (-59.0, 59.0):
        for y in (-35.0, -25.0, -15.0, -5.0, 5.0, 15.0, 25.0, 35.0):
            assert_fully_void(
                b,
                Part.makeCylinder(1.69, 4.0, App.Vector(x, y, 0.0)),
            )
            assert_fully_solid(
                b,
                Part.makeCylinder(0.04, 3.8, App.Vector(x + 1.75, y, 0.1)),
            )


def test_part_b_ears_are_solid_around_the_functional_holes() -> None:
    """Catch reintroducing the rejected central relief window."""

    b = make_part_b(BracketParameters())
    y, z = 4.8092213764, 24.2606042998
    assert_fully_solid(b, x_cylinder(-38.8, 3.8, y, z, 0.5))
    assert_fully_solid(b, x_cylinder(35.0, 3.8, y, z, 0.5))


def test_part_b_arc_rail_is_one_mm_thinner_from_the_outer_faces() -> None:
    """Catch thinning the inner clamping faces instead of the outer faces."""

    b = make_part_b(BracketParameters())
    y, z = -13.9846310393, 31.1010071663
    assert_fully_void(b, x_cylinder(-38.85, 0.7, y, z, 0.15))
    assert_fully_solid(b, x_cylinder(-37.7, 2.5, y, z, 0.15))
    assert_fully_solid(b, x_cylinder(35.1, 2.5, y, z, 0.15))
    assert_fully_void(b, x_cylinder(37.95, 0.7, y, z, 0.15))


def test_part_b_arc_slot_has_a_connected_full_thickness_top_bridge() -> None:
    """Catch splitting the slot through the top edge or thinning its bridge."""

    b = make_part_b(BracketParameters())
    y, z = 1.7403733293, 46.3702910152
    assert_fully_solid(b, x_cylinder(-38.8, 3.8, y, z, 0.25))
    assert_fully_solid(b, x_cylinder(35.0, 3.8, y, z, 0.25))


def test_part_b_pivot_is_inset_inside_a_six_mm_forward_lobe() -> None:
    """Catch returning the pivot to the sharp tip of the ear silhouette."""

    b = make_part_b(BracketParameters())
    assert_fully_solid(b, x_cylinder(-38.8, 3.8, 38.5, 14.0, 0.25))
    assert_fully_solid(b, x_cylinder(35.0, 3.8, 38.5, 14.0, 0.25))


def test_r45_arc_slot_cutter_has_exact_r45_by_3_4_area_and_volume() -> None:
    """Catch a wrong radius, width, angle, cap size, or extra cutter material."""

    p = BracketParameters()
    cutter = make_arc_slot_cutter(p)
    physical_sweep_radians = radians(
        p.working_angle_deg + 2.0 * derive(p).slot_overrun_deg
    )
    expected_area = p.slot_width * p.lock_radius * physical_sweep_radians + pi * 1.7**2

    assert cutter.isValid()
    assert len(cutter.Solids) == 1
    assert cutter.BoundBox.XMin < -38.9
    assert cutter.BoundBox.XMax > 38.9
    assert isclose(
        cutter.Volume,
        expected_area * cutter.BoundBox.XLength,
        rel_tol=1e-9,
        abs_tol=TOLERANCE,
    )


def test_r45_arc_slot_cutter_obeys_both_radial_boundaries() -> None:
    """Catch inner/outer radii other than 43.3/46.7 mm at mid-sweep."""

    p = BracketParameters()
    cutter = make_arc_slot_cutter(p)
    x0 = cutter.BoundBox.XMin + 0.1
    length = cutter.BoundBox.XLength - 0.2
    angle = radians(25.5)

    def point(radius: float) -> tuple[float, float]:
        return (
            p.b_pivot_y - radius * cos(angle),
            p.b_base_thickness + p.pivot_z_above_base + radius * sin(angle),
        )

    for radius in (43.35, 46.65):
        y, z = point(radius)
        assert_fully_solid(cutter, x_cylinder(x0, length, y, z, 0.04))
    for radius in (43.2, 46.8):
        y, z = point(radius)
        assert_fully_void(cutter, x_cylinder(x0, length, y, z, 0.04))


TESTS = (
    test_part_a_is_a_six_mm_flat_plate_without_ears_or_bosses,
    test_part_a_has_central_vent,
    test_part_a_preserves_all_four_mid360_mounting_holes_at_3_5_mm,
    test_part_a_has_six_mm_deep_pivot_side_pilot_holes,
    test_part_a_has_seven_mm_deep_lock_side_pilot_holes,
    test_part_a_has_rear_relief,
    test_part_b_bounds_match_the_board_top_cover,
    test_part_b_fan_opening_matches_the_cover_and_clears_both_ears,
    test_part_b_keeps_the_d435i_shelf_and_blends_its_rear_reentrant_corners,
    test_part_b_d435i_reliefs_preserve_wall_outside_measured_collision_band,
    test_d435i_screw_envelope_clears_part_b_and_part_a_at_all_working_angles,
    test_part_b_has_four_reduced_ten_by_eight_by_six_root_ribs,
    test_r45_part_b_has_both_pivot_holes,
    test_r45_part_b_has_slot_void_at_all_working_angles_on_both_walls,
    test_r45_part_b_slot_accepts_a_3_39_mm_midpoint_gauge,
    test_board_mounted_part_b_has_sixteen_3_4_mm_base_holes,
    test_part_b_ears_are_solid_around_the_functional_holes,
    test_part_b_arc_rail_is_one_mm_thinner_from_the_outer_faces,
    test_part_b_arc_slot_has_a_connected_full_thickness_top_bridge,
    test_part_b_pivot_is_inset_inside_a_six_mm_forward_lobe,
    test_r45_arc_slot_cutter_has_exact_r45_by_3_4_area_and_volume,
    test_r45_arc_slot_cutter_obeys_both_radial_boundaries,
)


if __name__ == "__main__":
    requested = set(sys.argv[1:])
    selected = tuple(
        test for test in TESTS if not requested or test.__name__ in requested
    )
    unknown = requested - {test.__name__ for test in TESTS}
    if unknown:
        raise SystemExit(f"unknown test names: {sorted(unknown)}")
    for test in selected:
        test()
    print(f"{len(selected)} FreeCAD geometry tests passed")
