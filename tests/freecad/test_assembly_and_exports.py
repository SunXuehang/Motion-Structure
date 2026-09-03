"""End-to-end checks for official sensor normalization and CAD deliverables."""

import json
from math import hypot, isclose
from pathlib import Path

import FreeCAD as App
import Import
import Mesh
import Part

from bracket.assembly import (
    _step_reimports_as_valid_shape,
    build_all_outputs,
    build_assembly,
    placement_for_angle,
    validate_assembly,
)
from bracket.official_sensor import load_normalized_mid360
from bracket.parameters import BracketParameters, derive


ROOT = Path(__file__).resolve().parents[2]
TOLERANCE = 1e-6
EXPECTED_PARAMETERS = (
    ("sensor_width", 65.0),
    ("sensor_mount_pitch_x", 36.0),
    ("sensor_mount_pitch_y", 48.0),
    ("sensor_mount_hole_diameter", 3.5),
    ("a_plate_width", 69.0),
    ("a_plate_depth", 85.0),
    ("a_plate_thickness", 6.0),
    ("a_b_pilot_hole_diameter", 2.9),
    ("side_thread_depth", 6.0),
    ("lock_thread_depth", 7.0),
    ("a_pivot_y", 38.0),
    ("a_pivot_z", -3.0),
    ("b_base_width", 128.0),
    ("b_base_depth", 78.0),
    ("b_base_thickness", 4.0),
    ("b_inner_width", 69.8),
    ("b_wall_thickness", 4.0),
    ("b_clearance_hole_diameter", 3.4),
    ("b_base_mount_hole_diameter", 3.4),
    ("b_pivot_y", 33.0),
    ("pivot_z_above_base", 10.0),
    ("lock_radius", 45.0),
    ("sector_outer_radius", 53.0),
    ("working_angle_deg", 40.0),
    ("slot_width", 3.4),
    ("slot_overrun_length", 1.5),
    ("sector_bridge_length", 4.0),
    ("sector_pivot_lobe_radius", 6.0),
    ("track_recess_depth", 1.0),
    ("root_rib_extension", 10.0),
    ("root_rib_depth", 8.0),
    ("root_rib_height", 6.0),
    ("root_rib_y_center", 16.0),
    ("m25_screw_length", 10.0),
    ("m3_screw_length", 8.0),
    ("d435i_shelf_width", 92.0),
    ("d435i_shelf_depth", 20.0),
    ("d435i_mount_clearance_diameter", 6.8),
    ("d435i_screw_shaft_diameter", 6.35),
    ("d435i_screw_head_diameter", 12.0),
    ("d435i_screw_head_height", 7.0),
)


def _load_raw_official_shape() -> Part.Shape:
    """Read the top-level official shape independently of production normalization."""

    document = App.newDocument("OfficialHoleEvidence")
    try:
        Import.insert(str(ROOT / "vendor/livox/mid-360-asm.stp"), document.Name)
        document.recompute()
        candidates = [
            obj.Shape
            for obj in document.Objects
            if hasattr(obj, "Shape")
            and not obj.Shape.isNull()
            and len(obj.Shape.Solids) > 0
        ]
        return max(
            candidates, key=lambda shape: (len(shape.Solids), shape.Volume)
        ).copy()
    finally:
        App.closeDocument(document.Name)


def _circle_centers(
    shape: Part.Shape,
    radius: float,
    axis_name: str,
    coordinate_names: tuple[str, str],
) -> set[tuple[float, float]]:
    """Extract unique circular-edge centers without production parameters."""

    centers: set[tuple[float, float]] = set()
    for edge in shape.Edges:
        try:
            curve = edge.Curve
        except TypeError:
            continue
        if not all(
            hasattr(curve, attribute) for attribute in ("Axis", "Center", "Radius")
        ):
            continue
        if not isclose(curve.Radius, radius, abs_tol=TOLERANCE):
            continue
        if not isclose(abs(getattr(curve.Axis, axis_name)), 1.0, abs_tol=TOLERANCE):
            continue
        centers.add(
            tuple(round(getattr(curve.Center, name), 6) for name in coordinate_names)
        )
    return centers


def _cylindrical_faces(
    shape: Part.Shape, axis_name: str
) -> list[tuple[object, App.BoundBox]]:
    """Return real cylindrical surfaces parallel to one literal global axis."""

    cylinders: list[tuple[object, App.BoundBox]] = []
    for face in shape.Faces:
        try:
            surface = face.Surface
        except TypeError:
            continue
        if not all(hasattr(surface, attribute) for attribute in ("Axis", "Radius")):
            continue
        if not isclose(abs(getattr(surface.Axis, axis_name)), 1.0, abs_tol=TOLERANCE):
            continue
        cylinders.append((surface, face.BoundBox))
    return cylinders


def _ensure_outputs(*relative_paths: str) -> None:
    """Generate required ignored artifacts when a focused test starts clean."""

    if any(not (ROOT / relative).is_file() for relative in relative_paths):
        build_all_outputs(ROOT)


def _reimport_step_shape(relative_path: str) -> Part.Shape:
    document = App.newDocument(f"TestSTEP_{Path(relative_path).stem}")
    try:
        Import.insert(str(ROOT / relative_path), document.Name)
        document.recompute()
        candidates = [
            obj.Shape
            for obj in document.Objects
            if hasattr(obj, "Shape")
            and not obj.Shape.isNull()
            and len(obj.Shape.Faces) > 0
        ]
        return max(candidates, key=lambda shape: shape.Volume).copy()
    finally:
        App.closeDocument(document.Name)


def _reimport_stl_shape(relative_path: str) -> Part.Shape:
    document = App.newDocument(f"TestSTL_{Path(relative_path).stem}")
    try:
        Mesh.insert(str(ROOT / relative_path), document.Name)
        document.recompute()
        mesh = next(
            obj.Mesh
            for obj in document.Objects
            if hasattr(obj, "Mesh") and obj.Mesh.CountFacets > 0
        )
        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh.Topology, 0.05)
        return shape
    finally:
        App.closeDocument(document.Name)


def _assert_bounds(
    shape: Part.Shape,
    minimum: tuple[float, float, float],
    maximum: tuple[float, float, float],
    tolerance: float = TOLERANCE,
) -> None:
    actual = shape.BoundBox
    for got, expected in zip(
        (actual.XMin, actual.YMin, actual.ZMin, actual.XMax, actual.YMax, actual.ZMax),
        (*minimum, *maximum),
    ):
        assert isclose(got, expected, abs_tol=tolerance)


def test_official_sensor_has_observable_normalized_orientation() -> None:
    """Catch a mirrored connector, wrong bottom plane, or shifted mount pattern."""

    sensor = load_normalized_mid360(ROOT / "vendor/livox/mid-360-asm.stp")
    bounds = sensor.BoundBox

    assert sensor.isValid()
    assert len(sensor.Solids) == 7
    assert isclose(sensor.Volume, 141854.316287708, abs_tol=1e-6)
    assert isclose(bounds.XMin, -33.398330127, abs_tol=1e-6)
    assert isclose(bounds.XMax, 33.396763479, abs_tol=1e-6)
    assert isclose(bounds.YMin, -40.3, abs_tol=1e-6)
    assert isclose(bounds.YMax, 32.439188993, abs_tol=1e-6)
    assert isclose(bounds.ZMin, 0.0, abs_tol=1e-6)
    assert isclose(bounds.ZMax, 61.3971, abs_tol=1e-6)
    assert -bounds.YMin > bounds.YMax
    assert bounds.XLength < 75.0
    assert bounds.YLength < 75.0
    assert bounds.ZLength < 70.0


def test_official_a_and_m3_mount_axes_are_coaxial() -> None:
    """Catch any XY normalization offset or stale 90-degree M3 screw pattern."""

    raw_sensor = _load_raw_official_shape()
    raw_hole_centers = _circle_centers(raw_sensor, 1.45, "y", ("x", "z"))
    assert raw_hole_centers == {
        (-24.0, -18.0),
        (-24.0, 18.0),
        (24.0, -18.0),
        (24.0, 18.0),
    }

    expected_assembly_centers = {
        (-18.0, -29.0),
        (-18.0, 19.0),
        (18.0, -29.0),
        (18.0, 19.0),
    }
    p = BracketParameters()
    sensor = load_normalized_mid360(ROOT / "vendor/livox/mid-360-asm.stp")
    shapes = build_assembly(p, sensor, 0.0)
    official_centers = _circle_centers(shapes.sensor, 1.45, "z", ("x", "y"))
    part_a_centers = _circle_centers(shapes.part_a, 1.75, "z", ("x", "y"))
    screw_centers = set().union(
        *(_circle_centers(screw, 1.5, "z", ("x", "y")) for screw in shapes.m3_screws)
    )

    assert official_centers == expected_assembly_centers
    assert part_a_centers == expected_assembly_centers
    assert screw_centers == expected_assembly_centers

    legacy_sensor = shapes.sensor.copy()
    legacy_offset = App.Placement(
        App.Vector(0.000783324, 0.060811007, 0.0), App.Rotation()
    )
    legacy_sensor.Placement = legacy_offset * legacy_sensor.Placement
    legacy_centers = _circle_centers(legacy_sensor, 1.45, "z", ("x", "y"))
    assert legacy_centers != expected_assembly_centers
    assert all(
        min(
            hypot(x - expected_x, y - expected_y)
            for expected_x, expected_y in expected_assembly_centers
        )
        > 0.05
        for x, y in legacy_centers
    )


def test_r45_placement_keeps_front_pivot_fixed_and_raises_rear() -> None:
    """Catch a wrong pivot mapping or the old front-up rotation sign."""

    p = BracketParameters()
    placement = placement_for_angle(p, 40.0)
    local_pivot = App.Vector(0.0, 38.0, -3.0)
    global_pivot = placement.multVec(local_pivot)
    rear = placement.multVec(App.Vector(0.0, -42.5, 0.0))

    assert (global_pivot - App.Vector(0.0, 33.0, 14.0)).Length < TOLERANCE
    assert isclose(rear.z, 68.0425359091, abs_tol=TOLERANCE)
    assert rear.z > global_pivot.z


def test_assembly_preserves_official_sensor_and_all_eight_screws() -> None:
    """Catch replacing the rigid STEP model or omitting required fasteners."""

    p = BracketParameters()
    sensor = load_normalized_mid360(ROOT / "vendor/livox/mid-360-asm.stp")
    shapes = build_assembly(p, sensor, 15.0)

    assert len(shapes.sensor.Solids) == 7
    assert isclose(shapes.sensor.Volume, sensor.Volume, abs_tol=TOLERANCE)
    assert len(shapes.m25_screws) == 4
    assert len(shapes.m3_screws) == 4
    assert all(screw.isValid() and screw.Volume > 1.0 for screw in shapes.m25_screws)
    assert all(screw.isValid() and screw.Volume > 1.0 for screw in shapes.m3_screws)


def test_m25_screws_have_exact_real_geometry_directions_and_locations() -> None:
    """Catch wrong M2.5 diameters, lengths, heads, sides, or lock-axis positions."""

    p = BracketParameters()
    sensor = load_normalized_mid360(ROOT / "vendor/livox/mid-360-asm.stp")

    for angle, expected_axes in {
        0.0: {
            (1, 33.0, 14.0, -38.9, -28.9, -41.4, -38.9),
            (-1, 33.0, 14.0, 28.9, 38.9, 38.9, 41.4),
            (1, -12.0, 14.0, -37.9, -27.9, -40.4, -37.9),
            (-1, -12.0, 14.0, 27.9, 37.9, 37.9, 40.4),
        },
        40.0: {
            (1, 33.0, 14.0, -38.9, -28.9, -41.4, -38.9),
            (-1, 33.0, 14.0, 28.9, 38.9, 38.9, 41.4),
            (1, -1.472, 42.925442, -37.9, -27.9, -40.4, -37.9),
            (-1, -1.472, 42.925442, 27.9, 37.9, 37.9, 40.4),
        },
    }.items():
        screws = build_assembly(p, sensor, angle).m25_screws
        assert len(screws) == 4
        actual: set[tuple[float, ...]] = set()
        for screw in screws:
            cylinders = _cylindrical_faces(screw, "x")
            assert sorted(round(surface.Radius, 6) for surface, _ in cylinders) == [
                1.25,
                4.0,
            ]
            shaft_surface, shaft_box = next(
                item for item in cylinders if isclose(item[0].Radius, 1.25)
            )
            _, head_box = next(
                item for item in cylinders if isclose(item[0].Radius, 4.0)
            )
            assert isclose(shaft_box.XLength, 10.0, abs_tol=TOLERANCE)
            assert isclose(shaft_box.YLength, 2.5, abs_tol=TOLERANCE)
            assert isclose(shaft_box.ZLength, 2.5, abs_tol=TOLERANCE)
            assert isclose(head_box.YLength, 8.0, abs_tol=TOLERANCE)
            assert isclose(head_box.ZLength, 8.0, abs_tol=TOLERANCE)
            actual.add(
                (
                    round(shaft_surface.Axis.x),
                    round((shaft_box.YMin + shaft_box.YMax) / 2.0, 6),
                    round((shaft_box.ZMin + shaft_box.ZMax) / 2.0, 6),
                    round(shaft_box.XMin, 6),
                    round(shaft_box.XMax, 6),
                    round(head_box.XMin, 6),
                    round(head_box.XMax, 6),
                )
            )
        assert actual == expected_axes


def test_m3_screw_shafts_are_coaxial_and_eight_mm_long() -> None:
    """Catch changing an M3 shaft diameter, mounting axis, or 8 mm length."""

    p = BracketParameters()
    sensor = load_normalized_mid360(ROOT / "vendor/livox/mid-360-asm.stp")
    screws = build_assembly(p, sensor, 0.0).m3_screws
    actual_centers: set[tuple[float, float]] = set()
    for screw in screws:
        cylinders = _cylindrical_faces(screw, "z")
        assert sorted(round(surface.Radius, 6) for surface, _ in cylinders) == [
            1.5,
            3.0,
        ]
        _, shaft_box = next(item for item in cylinders if isclose(item[0].Radius, 1.5))
        assert isclose(shaft_box.ZLength, 8.0, abs_tol=TOLERANCE)
        assert isclose(shaft_box.XLength, 3.0, abs_tol=TOLERANCE)
        assert isclose(shaft_box.YLength, 3.0, abs_tol=TOLERANCE)
        actual_centers.add(
            (
                round((shaft_box.XMin + shaft_box.XMax) / 2.0, 6),
                round((shaft_box.YMin + shaft_box.YMax) / 2.0, 6),
            )
        )
    assert actual_centers == {
        (-18.0, -29.0),
        (-18.0, 19.0),
        (18.0, -29.0),
        (18.0, 19.0),
    }


def test_required_angles_have_no_sensor_a_collision() -> None:
    """Catch omitting official rigid sensor-versus-A collision validation."""

    p = BracketParameters()
    sensor = load_normalized_mid360(ROOT / "vendor/livox/mid-360-asm.stp")
    for angle in (0.0, 20.0, 40.0):
        result = validate_assembly(build_assembly(p, sensor, angle))
        assert result["sensor_a_common_volume_mm3"] < TOLERANCE


def test_zero_degree_flat_plate_has_seven_mm_base_clearance() -> None:
    p = BracketParameters()
    sensor = load_normalized_mid360(ROOT / "vendor/livox/mid-360-asm.stp")
    shapes = build_assembly(p, sensor, 0.0)

    assert isclose(
        shapes.part_a.BoundBox.ZMin - p.b_base_thickness,
        7.0,
        abs_tol=TOLERANCE,
    )


def test_build_all_outputs_validates_collisions_and_reimports() -> None:
    """Catch collisions, wrong review angle, incomplete files, or broken exports."""

    report = build_all_outputs(ROOT)

    assert report["angles"] == [0.0, 20.0, 40.0]
    assert report["visible_angle_deg"] == 0.0
    assert report["parameter_count"] == 47
    assert report["official_model"]["sha256"] == (
        "b93e9b51282ed319b6aa755e76a132c0eb03306da5f3b9676bcabf2e2ae25f02"
    )
    assert report["official_model"]["raw_bbox_mm"] == {
        "min": [-32.439188993, -25.9171, -33.396763479],
        "max": [40.3, 35.48, 33.398330127],
        "size": [72.739188993, 61.3971, 66.795093606],
    }
    assert report["official_model"]["normalized_bbox_mm"] == {
        "min": [-33.398330127, -40.3, 0.0],
        "max": [33.396763479, 32.439188993, 61.3971],
        "size": [66.795093606, 72.739188993, 61.3971],
    }
    assert report["official_model"]["transform"]["translation_mm"] == [
        0.0,
        0.0,
        25.9171,
    ]
    assert report["official_model"]["connector_direction"] == "-Y"

    for result in report["assemblies"]:
        assert result["a_b_common_volume_mm3"] < TOLERANCE
        assert result["sensor_a_common_volume_mm3"] < TOLERANCE
        assert result["sensor_b_common_volume_mm3"] < TOLERANCE
        assert result["a_valid"]
        assert result["b_valid"]
        assert result["sensor_valid"]

    persisted_report = json.loads(
        (ROOT / "reports/geometry_validation.json").read_text(encoding="utf-8")
    )
    assert persisted_report["assemblies"] == report["assemblies"]
    assert [
        result["sensor_a_common_volume_mm3"]
        for result in persisted_report["assemblies"]
    ] == [0.0, 0.0, 0.0]

    expected = (
        "models/mid360_tilt_bracket.FCStd",
        "exports/A_mid360_mount.step",
        "exports/A_mid360_mount.stl",
        "exports/B_tilt_base.step",
        "exports/B_tilt_base.stl",
        "exports/mid360_tilt_bracket_assembly.step",
    )
    assert set(report["reimports"]) == set(expected[1:])
    assert all(report["reimports"].values())
    for relative in expected:
        assert (ROOT / relative).stat().st_size > 1024


def test_part_exports_reimport_in_exact_design_and_print_coordinates() -> None:
    """Catch shifted STEP origins, an unflipped A STL, or raised print bottoms."""

    build_all_outputs(ROOT)
    required = (
        "exports/A_mid360_mount.step",
        "exports/A_mid360_mount.stl",
        "exports/B_tilt_base.step",
        "exports/B_tilt_base.stl",
    )
    _ensure_outputs(*required)
    a_step = _reimport_step_shape(required[0])
    a_stl = _reimport_stl_shape(required[1])
    b_step = _reimport_step_shape(required[2])
    b_stl = _reimport_stl_shape(required[3])

    assert all(
        shape.isValid() and len(shape.Faces) > 0
        for shape in (a_step, a_stl, b_step, b_stl)
    )
    _assert_bounds(a_step, (-34.5, -42.5, -6.0), (34.5, 42.5, 0.0))
    _assert_bounds(
        a_stl,
        (-34.5, -42.5, 0.0),
        (34.5, 42.5, 6.0),
        tolerance=1e-4,
    )
    design_contact_probe = Part.Vertex(App.Vector(30.0, 30.0, 0.0))
    print_contact_probe = Part.Vertex(App.Vector(30.0, -30.0, 0.0))
    assert a_step.distToShape(design_contact_probe)[0] < TOLERANCE
    assert a_stl.distToShape(print_contact_probe)[0] < 1e-4
    b_top = BracketParameters().b_base_thickness + derive(
        BracketParameters()
    ).sector_top_above_base
    _assert_bounds(b_step, (-64.0, -39.0, 0.0), (64.0, 59.0, b_top))
    _assert_bounds(
        b_stl,
        (-64.0, -39.0, 0.0),
        (64.0, 59.0, b_top),
        tolerance=1e-4,
    )
    for x in (-59.0, 59.0):
        for y in (-35.0, 35.0):
            hole_probe = Part.makeCylinder(1.44, 4.0, App.Vector(x, y, 0.0))
            assert b_step.common(hole_probe).Volume < TOLERANCE


def test_fcstd_contains_all_parameter_aliases_and_exact_group_members() -> None:
    """Catch missing spreadsheet fields, wrong values, or incomplete named groups."""

    relative = "models/mid360_tilt_bracket.FCStd"
    artifact = ROOT / relative
    artifact.unlink(missing_ok=True)
    report = build_all_outputs(ROOT)
    assert report["parameter_count"] == 47
    assert artifact.is_file()
    document = App.openDocument(str(artifact))
    try:
        spreadsheet = document.getObject("Parameters")
        assert spreadsheet is not None
        assert len(EXPECTED_PARAMETERS) == 41
        for row, (name, expected_value) in enumerate(EXPECTED_PARAMETERS, start=2):
            cell = f"B{row}"
            assert spreadsheet.getAlias(cell) == name
            assert isclose(
                float(spreadsheet.getContents(cell)),
                expected_value,
                abs_tol=TOLERANCE,
            )
        assert spreadsheet.getAlias("B43") is None

        expected_groups = {
            "PartB": ["PartBShape"],
            "PartA": ["PartAShape"],
            "Sensor": ["OfficialMID360"],
            "Screws": [
                "M25Screw1",
                "M25Screw2",
                "M25Screw3",
                "M25Screw4",
                "M3Screw1",
                "M3Screw2",
                "M3Screw3",
                "M3Screw4",
            ],
        }
        for group_name, expected_members in expected_groups.items():
            group = document.getObject(group_name)
            assert group is not None
            assert [member.Name for member in group.Group] == expected_members
    finally:
        App.closeDocument(document.Name)


def test_assembly_step_reimports_as_valid_shape() -> None:
    """Catch a non-standalone focused test or invalid multi-object STEP."""

    relative = "exports/mid360_tilt_bracket_assembly.step"
    _ensure_outputs(relative)
    assert _step_reimports_as_valid_shape(ROOT / relative)


TESTS = (
    test_official_sensor_has_observable_normalized_orientation,
    test_official_a_and_m3_mount_axes_are_coaxial,
    test_r45_placement_keeps_front_pivot_fixed_and_raises_rear,
    test_assembly_preserves_official_sensor_and_all_eight_screws,
    test_m25_screws_have_exact_real_geometry_directions_and_locations,
    test_m3_screw_shafts_are_coaxial_and_eight_mm_long,
    test_required_angles_have_no_sensor_a_collision,
    test_zero_degree_flat_plate_has_seven_mm_base_clearance,
    test_build_all_outputs_validates_collisions_and_reimports,
    test_part_exports_reimport_in_exact_design_and_print_coordinates,
    test_fcstd_contains_all_parameter_aliases_and_exact_group_members,
    test_assembly_step_reimports_as_valid_shape,
)


if __name__ == "__main__":
    requested = set(__import__("sys").argv[1:])
    selected = tuple(
        test for test in TESTS if not requested or test.__name__ in requested
    )
    unknown = requested - {test.__name__ for test in TESTS}
    if unknown:
        raise SystemExit(f"unknown test names: {sorted(unknown)}")
    for test in selected:
        test()
    print(f"{len(selected)} FreeCAD assembly/export tests passed")
