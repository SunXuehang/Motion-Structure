"""Checks for the compute-carrier, covers, and MID-360 bracket assembly."""

from math import isclose, isfinite
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import FreeCAD as App
import Import
import Mesh
import MeshPart
import Part

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_SRC = str(PROJECT_ROOT / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

try:
    from bracket import board_bracket_assembly as board_bracket_assembly_module
    from bracket.board_bracket_assembly import (
        _in_reference_coordinates,
        build_board_bracket_assembly,
        build_board_bracket_outputs,
    )
    from bracket.board_covers import BoardCoverParameters
    from bracket.parameters import BracketParameters
    _classify_cover_reference_sections = getattr(
        board_bracket_assembly_module,
        "_classify_cover_reference_sections",
        None,
    )
    _d435i_reference_interference_sections = getattr(
        board_bracket_assembly_module,
        "_d435i_reference_interference_sections",
        None,
    )
    _d435i_reference_report_fields = getattr(
        board_bracket_assembly_module,
        "_d435i_reference_report_fields",
        None,
    )
    _named_local_shapes = getattr(
        board_bracket_assembly_module,
        "_named_local_shapes",
        None,
    )
except ImportError:
    _classify_cover_reference_sections = None
    _d435i_reference_interference_sections = None
    _d435i_reference_report_fields = None
    _named_local_shapes = None
    build_board_bracket_assembly = None
    build_board_bracket_outputs = None


TOLERANCE = 1e-6


def test_cover_reference_intersection_classification_is_load_bearing() -> None:
    """Catch accepting out-of-zone or deeper-than-tolerance mesh intersections."""

    assert _classify_cover_reference_sections is not None
    parameters = BoardCoverParameters()
    mounting_contact = [
        App.Vector(-50.0, -35.0, parameters.board_mounting_z_min - 0.04),
        App.Vector(-49.0, -35.0, parameters.board_mounting_z_min),
    ]
    # Derive the rim crest instead of hard-coding it: this test used to assume
    # the 6 mm rim from an intermediate revision and silently went stale when
    # the lower rim was restored to 8 mm.
    rim_top = (
        parameters.board_mounting_z_min
        - parameters.bottom_standoff_height
        + parameters.bottom_rim_height
    )
    tolerance = board_bracket_assembly_module.COVER_CARRIER_SECTION_TOLERANCE_MM
    rim_near_contact = [
        App.Vector(-52.0, 0.0, rim_top - tolerance * 0.8),
        App.Vector(-52.0, 1.0, rim_top),
    ]
    out_of_zone = [
        App.Vector(0.0, 0.0, rim_top - tolerance * 0.2),
        App.Vector(1.0, 0.0, rim_top),
    ]
    deep_rim_cut = [
        App.Vector(-52.0, 0.0, rim_top - tolerance * 1.2),
        App.Vector(-52.0, 1.0, rim_top),
    ]

    accepted = _classify_cover_reference_sections(
        (mounting_contact, rim_near_contact), parameters, is_bottom_cover=True
    )
    assert accepted == {
        "raw_intersection_count": 2,
        "expected_mounting_contact_count": 1,
        "tolerance_near_contact_count": 1,
        "unexpected_intersection_count": 0,
    }
    assert _classify_cover_reference_sections(
        (out_of_zone,), parameters, is_bottom_cover=True
    )["unexpected_intersection_count"] == 1
    assert _classify_cover_reference_sections(
        (deep_rim_cut,), parameters, is_bottom_cover=True
    )["unexpected_intersection_count"] == 1
    assert _classify_cover_reference_sections(
        (rim_near_contact, rim_near_contact), parameters, is_bottom_cover=True
    )["unexpected_intersection_count"] == 1


def test_revised_bottom_cover_and_upper_bracket_preserve_clearances() -> None:
    """Catch losing the gap or shifting any hole in the two eight-hole columns."""

    assert build_board_bracket_assembly is not None, "assembly builder is missing"
    assembly = build_board_bracket_assembly(PROJECT_ROOT)

    assert assembly.part_b.isValid() and assembly.top_cover.isValid()
    assert isclose(assembly.bottom_cover.BoundBox.ZMin, -5.5, abs_tol=TOLERANCE)
    assert isclose(assembly.part_b.BoundBox.XLength, 128.0, abs_tol=TOLERANCE)
    assert isclose(assembly.part_b.BoundBox.YLength, 98.0, abs_tol=TOLERANCE)
    assert isclose(
        assembly.part_b.BoundBox.ZMin - assembly.top_cover.BoundBox.ZMax,
        20.0,
        abs_tol=TOLERANCE,
    )
    assert assembly.part_b.common(assembly.top_cover).Volume < TOLERANCE

    for x in (-59.0, 59.0):
        for y in (-35.0, -25.0, -15.0, -5.0, 5.0, 15.0, 25.0, 35.0):
            axis_probe = Part.makeCylinder(
                1.69,
                27.2,
                App.Vector(x, y, assembly.top_cover.BoundBox.ZMax - 3.1),
            )
            assert assembly.top_cover.common(axis_probe).Volume < TOLERANCE
            assert assembly.part_b.common(axis_probe).Volume < TOLERANCE

    original_body = assembly.part_b.common(
        Part.makeBox(
            128.0,
            78.0,
            4.0,
            App.Vector(-64.0, -39.0, assembly.part_b.BoundBox.ZMin),
        )
    )
    assert isclose(original_body.BoundBox.XMin, -64.0, abs_tol=TOLERANCE)
    assert isclose(original_body.BoundBox.XMax, 64.0, abs_tol=TOLERANCE)
    assert isclose(original_body.BoundBox.YMin, -39.0, abs_tol=TOLERANCE)
    assert isclose(original_body.BoundBox.YMax, 39.0, abs_tol=TOLERANCE)


def test_d435i_screw_envelope_clears_the_combined_board_assembly() -> None:
    """Catch D435i 1/4-20 interference above the shelf or reference mesh surface."""

    assembly = build_board_bracket_assembly(PROJECT_ROOT)
    p = BracketParameters()
    shelf_center_y = p.b_base_depth / 2.0 + p.d435i_shelf_depth / 2.0
    shaft = Part.makeCylinder(
        p.d435i_screw_shaft_diameter / 2.0,
        p.b_base_thickness,
        App.Vector(0.0, shelf_center_y, 0.0),
    )
    head = Part.makeCylinder(
        p.d435i_screw_head_diameter / 2.0,
        p.d435i_screw_head_height,
        App.Vector(0.0, shelf_center_y, -p.d435i_screw_head_height),
    )
    envelope = shaft.fuse(head)
    envelope.Placement = App.Placement(
        App.Vector(0.0, 0.0, assembly.part_b.BoundBox.ZMin), App.Rotation()
    )

    assert envelope.common(assembly.part_a).Volume < TOLERANCE
    assert envelope.common(assembly.sensor).Volume < TOLERANCE
    assert envelope.common(assembly.top_cover).Volume < TOLERANCE
    assert isclose(
        envelope.BoundBox.ZMin - assembly.top_cover.BoundBox.ZMax,
        13.0,
        abs_tol=TOLERANCE,
    )

    reference_mesh = Mesh.Mesh(
        str(PROJECT_ROOT / "renders/UAV_V3_compute_carrier_reference_clean.stl")
    )
    reference_envelope = _in_reference_coordinates(
        envelope, BoardCoverParameters()
    )
    assert not reference_mesh.isSolid()
    envelope_mesh = MeshPart.meshFromShape(
        Shape=reference_envelope,
        LinearDeflection=0.5,
        AngularDeflection=0.5,
        Relative=False,
    )
    assert not reference_mesh.section(envelope_mesh)


def test_d435i_reference_is_seated_aligned_and_clear_of_the_assembly() -> None:
    """Catch a missing, mis-mounted, or intersecting D435i reference.

    Moving the camera mount off the shelf hole or lifting it off the shelf
    makes this fail.
    """

    assembly = build_board_bracket_assembly(PROJECT_ROOT)
    camera = assembly.d435i_reference
    p = BracketParameters()
    shelf_top = assembly.part_b.BoundBox.ZMin + p.b_base_thickness

    assert not camera.isNull()
    assert len(camera.Faces) > 0 and camera.Area > 0.0
    assert isclose(assembly.d435i_mount_axis.x, 0.0, abs_tol=TOLERANCE)
    assert isclose(assembly.d435i_mount_axis.y, 49.0, abs_tol=TOLERANCE)
    assert isclose(assembly.d435i_mount_axis.z, shelf_top, abs_tol=TOLERANCE)
    assert isclose(camera.BoundBox.ZMin, shelf_top, abs_tol=TOLERANCE)

    # Support contact is allowed only at the shelf top: no volumetric overlap.
    assert camera.common(assembly.part_b).Volume < TOLERANCE
    assert camera.common(assembly.part_a).Volume < TOLERANCE
    assert camera.common(assembly.sensor).Volume < TOLERANCE
    assert camera.common(assembly.top_cover).Volume < TOLERANCE

    assert _d435i_reference_interference_sections is not None
    assert _d435i_reference_interference_sections(assembly) == {
        "part_b": 0,
        "part_a": 0,
        "sensor": 0,
        "top_cover": 0,
    }

    mount_probe = Part.makeCylinder(
        p.d435i_mount_clearance_diameter / 2.0,
        0.2,
        App.Vector(0.0, 49.0, shelf_top),
    )
    assert camera.common(mount_probe).Volume < TOLERANCE


def test_d435i_export_membership_and_report_fields() -> None:
    """Keep the D435i in both shared export inputs and delivery report fields."""

    assert _d435i_reference_report_fields is not None
    assert _named_local_shapes is not None
    assembly = build_board_bracket_assembly(PROJECT_ROOT)

    # _named_local_shapes is the single input used by the FCStd and STEP
    # writers, so this fast check protects both exports without a 300 MB STEP
    # regeneration.
    export_labels = {label for _, label, _ in _named_local_shapes(assembly)}
    assert "Official RealSense D435i reference" in export_labels
    assert "Official RealSense D435i reference" in board_bracket_assembly_module.REQUIRED_STEP_LABEL_PREFIXES

    report_fields = _d435i_reference_report_fields(
        assembly,
        {"part_b": 0, "part_a": 0, "sensor": 0, "top_cover": 0},
    )
    assert report_fields["d435i_reference_included"] is True
    assert report_fields["d435i_reference_part_b_mesh_section_count"] == 0
    assert report_fields["d435i_reference_part_a_mesh_section_count"] == 0
    assert report_fields["d435i_reference_sensor_mesh_section_count"] == 0
    assert report_fields["d435i_reference_top_cover_mesh_section_count"] == 0


def test_board_bracket_uses_r45_geometry_in_the_zero_degree_pose() -> None:
    """Catch reuse of a larger-radius or tilted bracket in the board assembly."""

    assert build_board_bracket_assembly is not None, "assembly builder is missing"
    assembly = build_board_bracket_assembly(PROJECT_ROOT)

    cover_top = assembly.top_cover.BoundBox.ZMax
    assert isclose(assembly.part_a.BoundBox.ZMin - cover_top, 31.0, abs_tol=TOLERANCE)
    assert isclose(assembly.part_a.BoundBox.ZMax - cover_top, 37.0, abs_tol=TOLERANCE)
    assert assembly.part_a.common(assembly.part_b).Volume < TOLERANCE


def test_board_assembly_omits_all_tilt_bracket_screw_models() -> None:
    """Catch reintroducing M2.5 or M3 screw solids into the combined assembly."""

    assembly = build_board_bracket_assembly(PROJECT_ROOT)

    assert assembly.screws == ()


def test_complete_assembly_carries_the_battery_grip() -> None:
    """Catch the battery grip going missing from the delivered assembly."""

    assembly = build_board_bracket_assembly(PROJECT_ROOT)

    # The cylindrical battery grip is now part of the delivered assembly and
    # hangs entirely below the lower cover underside at Z = -5.5.
    assert len(assembly.grip_body.Solids) == 1
    assert len(assembly.grip_bottom_cap.Solids) == 1
    assert len(assembly.cell_pack.Solids) == 3
    assert assembly.grip_body.BoundBox.ZMax <= -5.5 + 1e-6
    assert assembly.grip_body.common(assembly.bottom_cover).Volume < 1e-6
    assert assembly.grip_body.common(assembly.grip_bottom_cap).Volume < 1e-6

    export_labels = {label for _, label, _ in _named_local_shapes(assembly)}
    for required in (
        "Battery grip body",
        "Battery grip bottom cap",
        "Battery pack reference · 3 x AA",
    ):
        assert required in export_labels


def test_board_bracket_package_writes_viewable_fcstd_and_step() -> None:
    """Catch a missing/corrupt combined CAD package or omitted main component."""

    assert build_board_bracket_outputs is not None, "assembly exporter is missing"
    with TemporaryDirectory(prefix="board-mid360-assembly-") as temporary:
        paths = build_board_bracket_outputs(PROJECT_ROOT, Path(temporary))
        assert len(paths) == 3
        assert all(path.is_file() for path in paths)
        assert paths[0].stat().st_size > 500
        assert paths[1].stat().st_size > 500
        report = json.loads(paths[2].read_text(encoding="utf-8"))
        assert report["step_reimport_valid"] is True
        assert report["part_b_size_mm"] == [128.0, 78.0, 4.0]
        assert report["mount_hole_pitch_mm"] == [118.0, 70.0]
        assert report["bracket_angle_deg"] == 0.0
        assert report["lock_radius_mm"] == 45.0
        assert report["working_angle_deg"] == 40.0
        assert report["standoff_height_mm"] == 20.0
        assert report["tilt_screw_models_included"] is False
        assert report["cover_mounting_hole_diameter_mm"] == 3.4
        assert report["tilt_clearance_hole_diameter_mm"] == 3.4
        assert report["tilt_pilot_hole_diameter_mm"] == 2.9
        assert report["bottom_standoff_height_mm"] == 13.0
        assert report["part_b_body_size_mm"] == [128.0, 78.0, 4.0]
        assert report["part_b_plan_envelope_mm"] == [128.0, 98.0]
        assert report["d435i_shelf_size_mm"] == [92.0, 20.0, 4.0]
        assert report["d435i_mount_clearance_diameter_mm"] == 6.8
        assert report["d435i_screw_models_included"] is False
        assert report["d435i_screw_head_clearance_mm"] == 13.0
        assert report["cover_carrier_section_tolerance_mm"] == 0.05
        assert report["top_cover_carrier_raw_intersection_count"] == 0
        assert report["top_cover_carrier_unexpected_intersection_count"] == 0
        # The four standoffs each cut the carrier mesh twice.  With the lower
        # rim restored to 8 mm its crest also grazes the mesh, which the
        # classifier accepts as one sub-tolerance near-contact; what must stay
        # zero is the unexpected count, and the buckets must add up.
        assert (
            report["bottom_cover_carrier_expected_mounting_contact_count"] == 8
        )
        assert report["bottom_cover_carrier_tolerance_near_contact_count"] <= 1
        assert report["bottom_cover_carrier_unexpected_intersection_count"] == 0
        assert report["bottom_cover_carrier_raw_intersection_count"] == (
            report["bottom_cover_carrier_expected_mounting_contact_count"]
            + report["bottom_cover_carrier_tolerance_near_contact_count"]
            + report["bottom_cover_carrier_unexpected_intersection_count"]
        )
        assert report["compute_carrier_step_decimation_max_error_mm"] == 0.05
        assert report["compute_carrier_step_decimation_reduction"] == 0.82
        assert report["compute_carrier_step_face_count"] > 0
        assert report["compute_carrier_step_reference_contract_valid"] is True
        assert report["step_existing_cad_products_valid"] is True
        assert report["step_forbidden_products_absent"] is True
        interference_fields = {
            "part_b_top_cover_common_volume_mm3",
            "part_a_top_cover_common_volume_mm3",
            "sensor_top_cover_common_volume_mm3",
            "sensor_part_b_common_volume_mm3",
            "grip_bottom_cover_common_volume_mm3",
            "grip_part_b_common_volume_mm3",
            "grip_cap_common_volume_mm3",
            "cells_grip_common_volume_mm3",
        }
        assert interference_fields <= report.keys()
        assert all(report[field] < TOLERANCE for field in interference_fields)
        assert report["battery_grip_included"] is True
        assert report["grip_carrier_reference_z_gap_mm"] > 0.0
        assert report["step_required_member_count"] == len(
            board_bracket_assembly_module.REQUIRED_STEP_LABEL_PREFIXES
        )
        assert report["part_b_top_cover_common_volume_mm3"] < TOLERANCE
        assert report["part_a_top_cover_common_volume_mm3"] < TOLERANCE
        assert report["sensor_top_cover_common_volume_mm3"] < TOLERANCE
        assert report["sensor_part_b_common_volume_mm3"] < TOLERANCE
        assert report["d435i_reference_included"] is True
        # Derived: the shelf rides 20 mm above the upper cover, so raising the
        # top standoffs moves this axis with them.
        cover = BoardCoverParameters()
        bracket = BracketParameters()
        expected_axis_z = (
            cover.board_mounting_z_max
            + cover.top_standoff_height
            + cover.plate_thickness
            + board_bracket_assembly_module.BRACKET_STANDOFF_HEIGHT_MM
            + bracket.b_base_thickness
        )
        assert report["d435i_reference_mount_axis_mm"] == [0.0, 49.0, expected_axis_z]
        assert report["d435i_reference_lens_direction"] == [0.0, 1.0, 0.0]
        assert report["d435i_reference_part_b_common_volume_mm3"] < TOLERANCE
        assert report["d435i_reference_part_a_common_volume_mm3"] < TOLERANCE
        assert report["d435i_reference_sensor_common_volume_mm3"] < TOLERANCE
        assert report["d435i_reference_top_cover_common_volume_mm3"] < TOLERANCE

        document = App.openDocument(str(paths[0]))
        try:
            names = {obj.Name for obj in document.Objects}
            assert {
                "ComputeCarrierReference",
                "TopCover",
                "BottomCover",
                "PartBShape",
                "PartAShape",
                "OfficialMID360",
                "D435iReference",
            } <= names
            assert "BatteryHandleBody" not in names
            assert "BatteryHandleRearCover" not in names
            assert document.getObject("PartBShape").Shape.isValid()
            assert document.getObject("TopCover").Shape.isValid()
            assert document.getObject("D435iReference").Shape.Area > 0.0
            assert not any(name.startswith(("M25Screw", "M3Screw")) for name in names)
        finally:
            App.closeDocument(document.Name)

        step_document = App.newDocument("TestCombinedStepMembership")
        try:
            Import.insert(str(paths[1]), step_document.Name)
            step_document.recompute()
            labels = {
                obj.Label
                for obj in step_document.Objects
                if hasattr(obj, "Shape") and not obj.Shape.isNull()
            }
            required_label_prefixes = {
                "UAV V3 compute carrier reference",
                "UAV V3 upper cover",
                "UAV V3 lower cover",
                "Part B · 128 x 78 board mount",
                "Part A · 0 deg",
                "Official MID-360",
                "Official RealSense D435i reference",
            }
            assert all(
                any(label.startswith(prefix) for label in labels)
                for prefix in required_label_prefixes
            )
            cad_prefixes = required_label_prefixes - {
                "UAV V3 compute carrier reference"
            }
            assert all(
                any(
                    obj.Label.startswith(prefix)
                    and obj.Shape.isValid()
                    and len(obj.Shape.Faces) > 0
                    and len(obj.Shape.Edges) > 0
                    for obj in step_document.Objects
                    if hasattr(obj, "Shape") and not obj.Shape.isNull()
                )
                for prefix in cad_prefixes
            )
            source_bounds = Mesh.Mesh(
                str(
                    PROJECT_ROOT
                    / "renders/UAV_V3_compute_carrier_reference_clean.stl"
                )
            ).BoundBox
            carrier_candidates = [
                obj.Shape
                for obj in step_document.Objects
                if hasattr(obj, "Shape")
                and not obj.Shape.isNull()
                and obj.Label.startswith("UAV V3 compute carrier reference")
                and len(obj.Shape.Faces) > 0
                and len(obj.Shape.Edges) > 0
            ]
            assert any(
                min(
                    shape.BoundBox.XLength,
                    shape.BoundBox.YLength,
                    shape.BoundBox.ZLength,
                )
                > 0.0
                and all(
                    isfinite(actual)
                    and isclose(actual, expected, abs_tol=0.05)
                    for actual, expected in zip(
                        (
                            shape.BoundBox.XMin,
                            shape.BoundBox.XMax,
                            shape.BoundBox.YMin,
                            shape.BoundBox.YMax,
                            shape.BoundBox.ZMin,
                            shape.BoundBox.ZMax,
                        ),
                        (
                            source_bounds.XMin,
                            source_bounds.XMax,
                            source_bounds.YMin,
                            source_bounds.YMax,
                            source_bounds.ZMin,
                            source_bounds.ZMax,
                        ),
                    )
                )
                for shape in carrier_candidates
            )
            assert not any(
                forbidden in label
                for label in labels
                for forbidden in ("BatteryHandle", "Screw")
            )
        finally:
            App.closeDocument(step_document.Name)


if __name__ == "__main__":
    test_cover_reference_intersection_classification_is_load_bearing()
    test_board_assembly_omits_all_tilt_bracket_screw_models()
    test_complete_assembly_carries_the_battery_grip()
    test_revised_bottom_cover_and_upper_bracket_preserve_clearances()
    test_d435i_screw_envelope_clears_the_combined_board_assembly()
    test_d435i_reference_is_seated_aligned_and_clear_of_the_assembly()
    test_d435i_export_membership_and_report_fields()
    test_board_bracket_package_writes_viewable_fcstd_and_step()
    print("7 board/bracket assembly tests passed")
