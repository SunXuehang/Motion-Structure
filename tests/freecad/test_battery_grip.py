"""FreeCAD geometry checks for the cylindrical three-cell battery grip."""

from math import cos, isclose, pi, radians, sin
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import FreeCAD as App
import Part

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_SRC = str(PROJECT_ROOT / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

from bracket.battery_grip import (
    INTERFERENCE_FIELDS,
    PRINT_BED_MM,
    PRINT_PART_CLEARANCE_MM,
    BatteryGripParameters,
    board_screw_centers,
    build_battery_grip_outputs,
    build_battery_grip_print_plate,
    build_grip_cover_assembly,
    cap_screw_centers,
    cell_centers,
    make_bottom_cap,
    make_cell_reference,
    make_grip_body,
    mount_pilot_centers,
    pilot_axes_match_cover_holes,
    validate_grip_cover_assembly,
    validate_print_plate,
)

TOLERANCE = 1e-6
P = BatteryGripParameters()
BODY = make_grip_body(P)
CAP = make_bottom_cap(P)
CELLS = make_cell_reference(P)


def _post_envelopes(extra: float = 0.2) -> Part.Shape:
    """Fuse the three cap-screw posts, slightly grown, for use as probe masks."""

    shapes = [
        Part.makeCylinder(
            P.post_diameter / 2.0 + extra,
            P.post_height + extra,
            App.Vector(x, y, P.grip_z0 - extra / 2.0),
        )
        for x, y in cap_screw_centers(P)
    ]
    fused = shapes[0]
    for shape in shapes[1:]:
        fused = fused.fuse(shape)
    return fused


def test_grip_body_is_one_valid_solid_on_the_cover_footprint() -> None:
    """Catch a lost flange, a broken cone, or a grip off the cover outline."""

    assert BODY.isValid() and len(BODY.Solids) == 1
    bounds = BODY.BoundBox
    assert isclose(bounds.XMin, -P.flange_length / 2.0, abs_tol=1e-6)
    assert isclose(bounds.XMax, P.flange_length / 2.0, abs_tol=1e-6)
    assert isclose(bounds.YMin, -P.flange_width / 2.0, abs_tol=1e-6)
    assert isclose(bounds.YMax, P.flange_width / 2.0, abs_tol=1e-6)
    assert isclose(bounds.ZMax, P.cover_underside_z, abs_tol=1e-6)
    assert isclose(bounds.ZMin, P.grip_z0, abs_tol=1e-6)


def test_bore_funnels_through_a_hollow_root_with_no_top_lid() -> None:
    """Catch a top lid, a solid conical root, or a bore that stops flaring."""

    # A full-depth Ø33 column must be empty apart from the cap posts, right up
    # to the cover underside: no lid, and the root is hollow all the way.
    column = Part.makeCylinder(
        P.bore_diameter / 2.0 - 0.1,
        P.cover_underside_z - P.grip_z0 - 0.2,
        App.Vector(0.0, 0.0, P.grip_z0 + 0.1),
    ).cut(_post_envelopes())
    assert BODY.common(column).Volume < TOLERANCE
    # The plain tube wall around it must be solid.
    ring = Part.makeCylinder(
        P.tube_outer_diameter / 2.0 - 0.2,
        P.tube_height - 0.2,
        App.Vector(0.0, 0.0, P.grip_z0 + 0.1),
    ).cut(
        Part.makeCylinder(
            P.bore_diameter / 2.0 + 0.1,
            P.tube_height,
            App.Vector(0.0, 0.0, P.grip_z0),
        )
    )
    assert BODY.common(ring).Volume > 0.9 * ring.Volume
    # The mouth at the flange is the widened root bore, not Ø33.
    mouth = Part.makeCylinder(
        P.root_bore_top_diameter / 2.0 - 0.2,
        P.flange_thickness - 0.2,
        App.Vector(0.0, 0.0, P.flange_z0 + 0.1),
    )
    assert BODY.common(mouth).Volume < TOLERANCE
    # ...and the flange still keeps a solid ring just outside that mouth.
    collar = Part.makeCylinder(
        P.root_bore_top_diameter / 2.0 + 3.0,
        P.flange_thickness - 0.2,
        App.Vector(0.0, 0.0, P.flange_z0 + 0.1),
    ).cut(
        Part.makeCylinder(
            P.root_bore_top_diameter / 2.0 + 0.2,
            P.flange_thickness,
            App.Vector(0.0, 0.0, P.flange_z0),
        )
    )
    assert BODY.common(collar).Volume > 0.9 * collar.Volume
    # Half way up the root the wall must still be about wall_thickness thick.
    mid_z = (P.root_z0 + P.flange_z0) / 2.0
    mid_outer = (P.tube_outer_diameter + P.root_top_diameter) / 2.0
    mid_bore = (P.bore_diameter + P.root_bore_top_diameter) / 2.0
    assert BODY.common(
        Part.makeCylinder(
            mid_bore / 2.0 - 0.3, 0.4, App.Vector(0.0, 0.0, mid_z - 0.2)
        )
    ).Volume < TOLERANCE
    wall_ring = Part.makeCylinder(
        mid_outer / 2.0 - 0.3, 0.4, App.Vector(0.0, 0.0, mid_z - 0.2)
    ).cut(
        Part.makeCylinder(
            mid_bore / 2.0 + 0.3, 0.6, App.Vector(0.0, 0.0, mid_z - 0.3)
        )
    )
    assert BODY.common(wall_ring).Volume > 0.9 * wall_ring.Volume


def test_sixteen_m3_pilots_are_tapped_through_a_uniform_flange() -> None:
    """Catch missing pilots, a wrong depth, or re-introduced flange thickening."""

    assert pilot_axes_match_cover_holes(P)
    assert len(mount_pilot_centers(P)) == 16
    down = App.Vector(0.0, 0.0, -1.0)
    for x, y in mount_pilot_centers(P):
        pilot = Part.makeCylinder(
            P.pilot_diameter / 2.0 - 0.05,
            P.pilot_depth - 0.1,
            App.Vector(x, y, P.cover_underside_z - 0.05),
            down,
        )
        assert BODY.common(pilot).Volume < TOLERANCE
        collar = Part.makeCylinder(
            P.pilot_diameter / 2.0 + 1.2,
            P.pilot_depth - 0.1,
            App.Vector(x, y, P.cover_underside_z - 0.05),
            down,
        ).cut(
            Part.makeCylinder(
                P.pilot_diameter / 2.0 + 0.05,
                P.pilot_depth,
                App.Vector(x, y, P.cover_underside_z),
                down,
            )
        )
        assert BODY.common(collar).Volume > 0.9 * collar.Volume
        # The flange has no local thickening, so nothing may hang below it
        # at the screw columns: the pilot is tapped clean through 6 mm.
        below = Part.makeCylinder(
            P.pilot_diameter / 2.0 + 1.2,
            1.0,
            App.Vector(x, y, P.flange_z0 - 1.0),
        )
        assert BODY.common(below).Volume < TOLERANCE


def test_board_mounting_screw_heads_pass_through_the_flange() -> None:
    """Catch a flange that traps the four cover-to-carrier screws."""

    for x, y in board_screw_centers(P):
        head = Part.makeCylinder(
            P.board_screw_clearance_diameter / 2.0 - 0.05,
            P.flange_thickness + 0.2,
            App.Vector(x, y, P.flange_z0 - 0.1),
        )
        assert BODY.common(head).Volume < TOLERANCE


def test_three_cells_load_as_an_equilateral_triangle_without_touching_pla() -> None:
    """Catch a bore or post that the triangular lithium pack cannot clear."""

    assert len(CELLS.Solids) == P.cell_count
    assert CELLS.common(BODY).Volume < TOLERANCE
    assert CELLS.common(CAP).Volume < TOLERANCE
    bounds = CELLS.BoundBox
    assert isclose(bounds.ZMin, P.grip_z0, abs_tol=1e-6)
    assert isclose(bounds.ZMax, P.cell_z1, abs_tol=1e-6)
    # The pack's enclosing circle is centred on the bore axis.
    for x, y in cell_centers(P):
        assert isclose(
            (x * x + y * y) ** 0.5 + P.cell_diameter / 2.0,
            P.pack_circumdiameter / 2.0,
            abs_tol=1e-6,
        )
    # The bore is open at the bottom so the pack can be loaded.
    mouth = Part.makeCylinder(
        P.bore_diameter / 2.0 - 0.5,
        1.0,
        App.Vector(0.0, 0.0, P.grip_z0),
    ).cut(_post_envelopes())
    assert BODY.common(mouth).Volume < TOLERANCE


def test_rear_window_passes_the_dc_leads_through_the_tube_wall() -> None:
    """Catch a missing, mislocated, or blind DC-lead window."""

    y_outer = -P.tube_outer_diameter / 2.0
    bore_radius = P.bore_diameter / 2.0
    half = P.window_length / 2.0
    # The window must break clean through the curved wall at its very edges,
    # where the wall is radially deepest.
    for x in (-half + 1.0, 0.0, half - 1.0):
        y_bore = -(bore_radius**2 - x * x) ** 0.5
        depth = Part.makeBox(
            0.4,
            (y_bore + 1.0) - (y_outer - 1.0),
            P.window_height - 1.6,
            App.Vector(
                x - 0.2,
                y_outer - 1.0,
                P.window_center_z - (P.window_height - 1.6) / 2.0,
            ),
        )
        assert BODY.common(depth).Volume < TOLERANCE, x
    # The wall must remain closed just outside the window's azimuth span.
    mid_radius = (bore_radius + P.tube_outer_diameter / 2.0) / 2.0
    for angle in (-50.0, -130.0):
        probe = Part.makeCylinder(
            1.0,
            P.window_height,
            App.Vector(
                mid_radius * cos(radians(angle)),
                mid_radius * sin(radians(angle)),
                P.window_center_z - P.window_height / 2.0,
            ),
        )
        assert BODY.common(probe).Volume > 0.5 * probe.Volume, angle
    # The window sits in the plain wall, above the cells and below the cone.
    assert P.window_center_z - P.window_height / 2.0 > P.cell_z1
    assert P.window_center_z + P.window_height / 2.0 < P.root_z0


def test_bottom_cap_screws_into_three_posts_inside_the_bore() -> None:
    """Catch a cap that misses its posts, its screws, or its counterbores."""

    assert CAP.isValid() and len(CAP.Solids) == 1
    bounds = CAP.BoundBox
    assert isclose(bounds.ZMin, P.cap_z0, abs_tol=1e-6)
    assert isclose(bounds.ZMax, P.grip_z0, abs_tol=1e-6)
    assert isclose(bounds.XLength, P.tube_outer_diameter, abs_tol=1e-6)
    assert isclose(bounds.YLength, P.tube_outer_diameter, abs_tol=1e-6)
    assert CAP.common(BODY).Volume < TOLERANCE
    assert len(cap_screw_centers(P)) == 3
    for x, y in cap_screw_centers(P):
        assert CAP.common(
            Part.makeCylinder(
                P.cap_hole_diameter / 2.0 - 0.05,
                P.cap_thickness + 0.2,
                App.Vector(x, y, P.cap_z0 - 0.1),
            )
        ).Volume < TOLERANCE
        assert BODY.common(
            Part.makeCylinder(
                P.pilot_diameter / 2.0 - 0.05,
                P.cap_pilot_depth - 0.1,
                App.Vector(x, y, P.grip_z0 + 0.05),
            )
        ).Volume < TOLERANCE
        collar = Part.makeCylinder(
            P.post_diameter / 2.0 - 0.1,
            P.cap_pilot_depth - 0.1,
            App.Vector(x, y, P.grip_z0 + 0.05),
        ).cut(
            Part.makeCylinder(
                P.pilot_diameter / 2.0 + 0.05,
                P.cap_pilot_depth,
                App.Vector(x, y, P.grip_z0),
            )
        )
        assert BODY.common(collar).Volume > 0.85 * collar.Volume


def test_grip_seats_flat_on_the_lower_cover_and_the_fan_reaches_the_bore() -> None:
    """Catch a floating or overlapping handle, and record the fan's open path."""

    assembly = build_grip_cover_assembly(P)
    results = validate_grip_cover_assembly(assembly, P)
    assert results["grip_body_valid"] and results["bottom_cap_valid"]
    for field in INTERFERENCE_FIELDS:
        assert results[field] < TOLERANCE, field
    assert isclose(
        results["flange_top_z"], assembly.lower_cover.BoundBox.ZMin, abs_tol=1e-6
    )
    assert isclose(results["flange_length_mm"], P.flange_length, abs_tol=1e-6)
    assert isclose(results["flange_width_mm"], P.flange_width, abs_tol=1e-6)
    assert isclose(results["handle_bottom_z"], P.cap_z0, abs_tol=1e-6)
    # The flange keeps no fan cut-out by design, so a real part of the fan
    # opening must still land inside the bore for the exhaust to get out.
    assert results["fan_opening_open_fraction"] > 0.3
    assert results["imu_opening_open_fraction"] >= 0.0


def test_package_writes_cad_only_and_round_trips_every_step() -> None:
    """Catch a missing export, a bad STEP, or an STL slipping back in."""

    with TemporaryDirectory(prefix="mid360-battery-grip-") as temporary:
        destination = Path(temporary)
        paths = build_battery_grip_outputs(PROJECT_ROOT, destination)
        assert tuple(path.name for path in paths) == (
            "battery_grip_cover_assembly.FCStd",
            "battery_grip_body.step",
            "battery_grip_bottom_cap.step",
            "battery_grip_cover_assembly.step",
            "battery_grip_256x256_print_plate.step",
            "battery_grip_validation.json",
        )
        for path in paths:
            assert path.is_file() and path.stat().st_size > 500
        assert not list(destination.glob("*.stl"))
        assert not list(destination.glob("*.STL"))


def test_print_plate_seats_both_parts_print_side_down_on_the_bed() -> None:
    """Catch a print layout that overlaps, floats, or leaves the 256 mm bed."""

    plate = build_battery_grip_print_plate(P)
    assert tuple(label for label, _shape in plate) == (
        "Battery grip body",
        "Battery grip bottom cap",
    )
    results = validate_print_plate(plate)
    assert results["all_single_solids"]
    assert results["all_seated_on_bed"]
    assert results["within_bed"]
    assert results["parts_disjoint"]
    assert results["min_part_clearance_mm"] >= PRINT_PART_CLEARANCE_MM

    (_body_label, body), (_cap_label, cap) = plate
    # The body prints flange-down: its first layer is the full 128 x 78 flange.
    assert isclose(body.BoundBox.ZLength, P.cover_underside_z - P.grip_z0, abs_tol=1e-6)
    first_layer = body.common(
        Part.makeBox(
            PRINT_BED_MM,
            PRINT_BED_MM,
            0.2,
            App.Vector(-PRINT_BED_MM / 2.0, -PRINT_BED_MM / 2.0, 0.0),
        )
    )
    assert isclose(first_layer.BoundBox.XLength, P.flange_length, abs_tol=1e-6)
    assert isclose(first_layer.BoundBox.YLength, P.flange_width, abs_tol=1e-6)
    # The cap prints outer-face-down, so its counterbores open upward.
    assert isclose(cap.BoundBox.ZLength, P.cap_thickness, abs_tol=1e-6)
    cap_first_layer = cap.common(
        Part.makeBox(
            PRINT_BED_MM,
            PRINT_BED_MM,
            0.2,
            App.Vector(-PRINT_BED_MM / 2.0, -PRINT_BED_MM / 2.0, 0.0),
        )
    )
    counterbore_area = 3.0 * pi * (P.cap_counterbore_diameter / 2.0) ** 2
    assert cap_first_layer.Volume / 0.2 > (
        pi * (P.tube_outer_diameter / 2.0) ** 2 - counterbore_area - 1.0
    )


if __name__ == "__main__":
    tests = tuple(
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    )
    for test in tests:
        test()
    print(f"{len(tests)} battery-grip tests passed")
