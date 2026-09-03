"""Assemble the compute carrier, covers, and board-mounted MID-360 bracket."""

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path

import FreeCAD as App
import Import
import Mesh
import MeshPart
import Part

from .battery_grip import (
    BatteryGripParameters,
    make_bottom_cap,
    make_cell_reference,
    make_grip_body,
)
from .board_covers import BoardCoverParameters, make_bottom_cover, make_top_cover
from .assembly import build_assembly
from .freecad_geometry import make_board_mounted_part_b
from .official_sensor import load_normalized_mid360
from .parameters import BracketParameters


BRACKET_ANGLE_DEG = 0.0
BRACKET_STANDOFF_HEIGHT_MM = 20.0
COVER_CARRIER_SECTION_TOLERANCE_MM = 0.05
STEP_REFERENCE_DECIMATION_REDUCTION = 0.82
REQUIRED_STEP_LABEL_PREFIXES = (
    "UAV V3 compute carrier reference",
    "UAV V3 upper cover",
    "UAV V3 lower cover",
    "Part B · 128 x 78 board mount",
    "Part A · 0 deg",
    "Official MID-360",
    "Official RealSense D435i reference",
    "Battery grip body",
    "Battery grip bottom cap",
    "Battery pack reference",
)
# The combined assembly models no screws.
FORBIDDEN_STEP_LABEL_FRAGMENTS = ("Screw",)
D435I_VISUAL_STL = Path("vendor/realsense/d435_mm.stl")
D435I_MESH_TO_BOTTOM_SCREW_FRAME_MM = (14.9, 0.0, 12.5)
D435I_STEP_DECIMATION_MAX_ERROR_MM = 0.05
D435I_STEP_DECIMATION_REDUCTION = 0.9


@dataclass(frozen=True)
class BoardBracketAssembly:
    """Board-local solids with Part B seated on the upper cover."""

    top_cover: Part.Shape
    bottom_cover: Part.Shape
    part_b: Part.Shape
    part_a: Part.Shape
    sensor: Part.Shape
    d435i_reference: Part.Shape
    d435i_mount_axis: App.Vector
    d435i_lens_direction: App.Vector
    grip_body: Part.Shape
    grip_bottom_cap: Part.Shape
    cell_pack: Part.Shape
    screws: tuple[tuple[str, Part.Shape], ...]


def _translated(shape: Part.Shape, z_offset: float) -> Part.Shape:
    placed = shape.copy()
    placed.Placement = App.Placement(
        App.Vector(0.0, 0.0, z_offset), App.Rotation()
    ) * placed.Placement
    return placed


def _d435i_reference_shape(root: Path) -> Part.Shape:
    """Load the official D435 visual mesh into its URDF bottom-screw frame."""

    source = root / D435I_VISUAL_STL
    if not source.is_file():
        raise FileNotFoundError(f"official D435i visual mesh missing: {source}")
    mesh = Mesh.Mesh(str(source))
    if mesh.CountFacets == 0:
        raise ValueError("official D435i visual mesh has no facets")
    # A compact face representation keeps the reference selectable in FCStd
    # and STEP without turning a visual mesh into printable geometry.
    mesh.decimate(
        D435I_STEP_DECIMATION_MAX_ERROR_MM,
        D435I_STEP_DECIMATION_REDUCTION,
    )
    # Reproduce the upstream D435 URDF: DAE (Z-up) x/y/z map to camera
    # link y/z/x, then the physical bottom 1/4-20 frame is the origin.
    transform = App.Matrix()
    offset_x, offset_y, offset_z = D435I_MESH_TO_BOTTOM_SCREW_FRAME_MM
    transform.A11, transform.A12, transform.A13, transform.A14 = (
        0.0,
        0.0,
        1.0,
        offset_x,
    )
    transform.A21, transform.A22, transform.A23, transform.A24 = (
        1.0,
        0.0,
        0.0,
        offset_y,
    )
    transform.A31, transform.A32, transform.A33, transform.A34 = (
        0.0,
        1.0,
        0.0,
        offset_z,
    )
    mesh.transform(transform)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, D435I_STEP_DECIMATION_MAX_ERROR_MM)
    if shape.isNull() or len(shape.Faces) == 0 or shape.Area <= 0.0:
        raise ValueError("official D435i visual mesh did not convert to faces")
    # Decimation may move the visual underside by less than its 0.05 mm bound.
    # Restore that surface to the URDF bottom-mount plane before assembly.
    shape.Placement = App.Placement(
        App.Vector(0.0, 0.0, -shape.BoundBox.ZMin), App.Rotation()
    )
    return shape


def _place_d435i_reference(
    shape: Part.Shape, mount_axis: App.Vector
) -> Part.Shape:
    """Seat the D435i bottom mount on the shelf and aim its lenses along +Y."""

    placed = shape.copy()
    placed.Placement = App.Placement(
        mount_axis, App.Rotation(App.Vector(0.0, 0.0, 1.0), 90.0)
    ) * placed.Placement
    return placed


def _in_reference_coordinates(
    shape: Part.Shape, parameters: BoardCoverParameters
) -> Part.Shape:
    placed = shape.copy()
    reference = App.Placement(
        App.Vector(parameters.reference_center_x, parameters.reference_center_y, 0.0),
        App.Rotation(
            App.Vector(0.0, 0.0, 1.0), parameters.reference_rotation_deg
        ),
    )
    placed.Placement = reference * placed.Placement
    return placed


def _classify_cover_reference_sections(
    sections: tuple[list[App.Vector], ...] | list[list[App.Vector]],
    parameters: BoardCoverParameters,
    *,
    is_bottom_cover: bool,
) -> dict[str, int]:
    """Classify actual mesh-section curves against explicit allowed contacts."""

    tolerance = COVER_CARRIER_SECTION_TOLERANCE_MM
    mounting_radius = parameters.standoff_outer_diameter / 2.0 + tolerance
    mounting_centers = (
        (x, y)
        for x in (-parameters.mount_pitch_x / 2.0, parameters.mount_pitch_x / 2.0)
        for y in (-parameters.mount_pitch_y / 2.0, parameters.mount_pitch_y / 2.0)
    )
    mounting_centers = tuple(mounting_centers)

    mounting_contacts = 0
    tolerance_near_contacts = 0
    unexpected = 0
    rim_near_contact_candidates = 0
    rim_top = (
        parameters.board_mounting_z_min
        - parameters.bottom_standoff_height
        + parameters.bottom_rim_height
    )
    half_x = (
        parameters.mount_pitch_x / 2.0
        + parameters.standoff_outer_diameter / 2.0
        - parameters.rim_thickness / 2.0
    )
    half_y = (
        parameters.mount_pitch_y / 2.0
        + parameters.standoff_outer_diameter / 2.0
        - parameters.rim_thickness / 2.0
    )
    half_rim = parameters.rim_thickness / 2.0 + tolerance

    for section in sections:
        in_mounting_zone = any(
            all(
                (point.x - center_x) ** 2 + (point.y - center_y) ** 2
                <= mounting_radius**2
                and abs(point.z - parameters.board_mounting_z_min) <= tolerance
                for point in section
            )
            for center_x, center_y in mounting_centers
        )
        if in_mounting_zone:
            mounting_contacts += 1
            continue

        in_rim_footprint = is_bottom_cover and all(
            (
                min(abs(point.x - half_x), abs(point.x + half_x)) <= half_rim
                and abs(point.y) <= half_y + tolerance
            )
            or (
                min(abs(point.y - half_y), abs(point.y + half_y)) <= half_rim
                and abs(point.x) <= half_x + tolerance
            )
            for point in section
        )
        rim_depth = rim_top - min(point.z for point in section)
        is_tolerance_near_contact = (
            in_rim_footprint
            and 0.0 <= rim_depth <= tolerance
            and max(point.z for point in section) <= rim_top + tolerance
        )
        if is_tolerance_near_contact:
            rim_near_contact_candidates += 1
        else:
            unexpected += 1

    if rim_near_contact_candidates == 1:
        tolerance_near_contacts = 1
    elif rim_near_contact_candidates > 1:
        tolerance_near_contacts = 1
        unexpected += rim_near_contact_candidates - 1

    return {
        "raw_intersection_count": len(sections),
        "expected_mounting_contact_count": mounting_contacts,
        "tolerance_near_contact_count": tolerance_near_contacts,
        "unexpected_intersection_count": unexpected,
    }


def _cover_reference_clearance_results(
    root: Path,
    assembly: BoardBracketAssembly,
    parameters: BoardCoverParameters,
) -> tuple[dict[str, int], int, bool, tuple[float, ...]]:
    """Section both placed covers against the unchanged open reference mesh."""

    reference_path = root / "renders/UAV_V3_compute_carrier_reference_clean.stl"
    if not reference_path.is_file():
        raise FileNotFoundError(f"board reference mesh missing: {reference_path}")
    reference_mesh = Mesh.Mesh(str(reference_path))
    reference_placement = App.Placement(
        App.Vector(parameters.reference_center_x, parameters.reference_center_y, 0.0),
        App.Rotation(
            App.Vector(0.0, 0.0, 1.0), parameters.reference_rotation_deg
        ),
    )
    inverse_reference = reference_placement.inverse()
    results: dict[str, int] = {}
    for prefix, cover, is_bottom_cover in (
        ("top_cover_carrier", assembly.top_cover, False),
        ("bottom_cover_carrier", assembly.bottom_cover, True),
    ):
        placed_cover = _in_reference_coordinates(cover, parameters)
        cover_mesh = MeshPart.meshFromShape(
            Shape=placed_cover,
            LinearDeflection=0.2,
            AngularDeflection=0.3,
            Relative=False,
        )
        local_sections = tuple(
            [inverse_reference.multVec(point) for point in section]
            for section in reference_mesh.section(cover_mesh)
        )
        classification = _classify_cover_reference_sections(
            local_sections,
            parameters,
            is_bottom_cover=is_bottom_cover,
        )
        results.update(
            {f"{prefix}_{name}": value for name, value in classification.items()}
        )
    bounds = reference_mesh.BoundBox
    return (
        results,
        reference_mesh.CountFacets,
        reference_mesh.isSolid(),
        (
            bounds.XMin,
            bounds.XMax,
            bounds.YMin,
            bounds.YMax,
            bounds.ZMin,
            bounds.ZMax,
        ),
    )


def _d435i_reference_interference_sections(
    assembly: BoardBracketAssembly,
) -> dict[str, int]:
    """Count real mesh intersections for the non-printable camera reference."""

    camera_mesh = MeshPart.meshFromShape(
        Shape=assembly.d435i_reference,
        LinearDeflection=D435I_STEP_DECIMATION_MAX_ERROR_MM,
        AngularDeflection=0.3,
        Relative=False,
    )
    return {
        name: len(
            camera_mesh.section(
                MeshPart.meshFromShape(
                    Shape=shape,
                    LinearDeflection=D435I_STEP_DECIMATION_MAX_ERROR_MM,
                    AngularDeflection=0.3,
                    Relative=False,
                )
            )
        )
        for name, shape in (
            ("part_b", assembly.part_b),
            ("part_a", assembly.part_a),
            ("sensor", assembly.sensor),
            ("top_cover", assembly.top_cover),
        )
    }


def build_board_bracket_assembly(project_root: Path) -> BoardBracketAssembly:
    """Build the compact R45 bracket 20 mm above the upper cover."""

    root = Path(project_root).resolve()
    parameters = BoardCoverParameters()
    top_cover = make_top_cover(parameters)
    bottom_cover = make_bottom_cover(parameters)
    bracket_parameters = BracketParameters()
    grip_parameters = BatteryGripParameters()
    sensor = load_normalized_mid360(root / "vendor/livox/mid-360-asm.stp")
    bracket_shapes = build_assembly(
        bracket_parameters,
        sensor,
        BRACKET_ANGLE_DEG,
    )
    z_offset = top_cover.BoundBox.ZMax + BRACKET_STANDOFF_HEIGHT_MM
    d435i_mount_axis = App.Vector(
        0.0,
        bracket_parameters.b_base_depth / 2.0
        + bracket_parameters.d435i_shelf_depth / 2.0,
        z_offset + bracket_parameters.b_base_thickness,
    )
    return BoardBracketAssembly(
        top_cover=top_cover,
        bottom_cover=bottom_cover,
        part_b=_translated(make_board_mounted_part_b(bracket_parameters), z_offset),
        part_a=_translated(bracket_shapes.part_a, z_offset),
        sensor=_translated(bracket_shapes.sensor, z_offset),
        d435i_reference=_place_d435i_reference(
            _d435i_reference_shape(root), d435i_mount_axis
        ),
        d435i_mount_axis=d435i_mount_axis,
        d435i_lens_direction=App.Vector(0.0, 1.0, 0.0),
        # The grip is already authored in this board-local frame, hanging from
        # the lower cover underside at Z = -5.5.
        grip_body=make_grip_body(grip_parameters),
        grip_bottom_cap=make_bottom_cap(grip_parameters),
        cell_pack=make_cell_reference(grip_parameters),
        screws=(),
    )


def _add_shape(document, name: str, label: str, shape: Part.Shape):
    obj = document.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape
    return obj


def _named_local_shapes(
    assembly: BoardBracketAssembly,
) -> tuple[tuple[str, str, Part.Shape], ...]:
    return (
        ("TopCover", "UAV V3 upper cover", assembly.top_cover),
        ("BottomCover", "UAV V3 lower cover", assembly.bottom_cover),
        ("PartBShape", "Part B · 128 x 78 board mount", assembly.part_b),
        ("PartAShape", "Part A · 0 deg", assembly.part_a),
        ("OfficialMID360", "Official MID-360", assembly.sensor),
        (
            "D435iReference",
            "Official RealSense D435i reference",
            assembly.d435i_reference,
        ),
        ("GripBody", "Battery grip body", assembly.grip_body),
        ("GripBottomCap", "Battery grip bottom cap", assembly.grip_bottom_cap),
        ("CellPackReference", "Battery pack reference · 3 x AA", assembly.cell_pack),
        *tuple((name, name, shape) for name, shape in assembly.screws),
    )


def _d435i_reference_report_fields(
    assembly: BoardBracketAssembly,
    interference_sections: dict[str, int],
) -> dict[str, object]:
    """Return D435i report data shared by the final delivery builder."""
    return {
        "d435i_reference_included": True,
        "d435i_reference_source": "vendor/realsense/d435.dae",
        "d435i_reference_source_sha256": (
            "42f3b66f47a1f8f425a2e4dc07c1d9c283183167d8441f520a15623d98f9bf78"
        ),
        "d435i_reference_license": "Apache-2.0",
        "d435i_reference_mount_axis_mm": [
            assembly.d435i_mount_axis.x,
            assembly.d435i_mount_axis.y,
            assembly.d435i_mount_axis.z,
        ],
        "d435i_reference_lens_direction": [
            assembly.d435i_lens_direction.x,
            assembly.d435i_lens_direction.y,
            assembly.d435i_lens_direction.z,
        ],
        "d435i_reference_seating_error_mm": (
            assembly.d435i_reference.BoundBox.ZMin - assembly.d435i_mount_axis.z
        ),
        "d435i_reference_part_b_common_volume_mm3": assembly.d435i_reference.common(
            assembly.part_b
        ).Volume,
        "d435i_reference_part_a_common_volume_mm3": assembly.d435i_reference.common(
            assembly.part_a
        ).Volume,
        "d435i_reference_sensor_common_volume_mm3": assembly.d435i_reference.common(
            assembly.sensor
        ).Volume,
        "d435i_reference_top_cover_common_volume_mm3": assembly.d435i_reference.common(
            assembly.top_cover
        ).Volume,
        "d435i_reference_part_b_mesh_section_count": interference_sections["part_b"],
        "d435i_reference_part_a_mesh_section_count": interference_sections["part_a"],
        "d435i_reference_sensor_mesh_section_count": interference_sections["sensor"],
        "d435i_reference_top_cover_mesh_section_count": interference_sections[
            "top_cover"
        ],
    }


def _battery_grip_report_fields(
    assembly: BoardBracketAssembly,
) -> dict[str, object]:
    """Return the grip's contact volumes and its clearance to the board CAD."""

    grip = assembly.grip_body
    return {
        "grip_bottom_cover_common_volume_mm3": grip.common(
            assembly.bottom_cover
        ).Volume,
        "grip_top_cover_common_volume_mm3": grip.common(assembly.top_cover).Volume,
        "grip_part_b_common_volume_mm3": grip.common(assembly.part_b).Volume,
        "grip_part_a_common_volume_mm3": grip.common(assembly.part_a).Volume,
        "grip_sensor_common_volume_mm3": grip.common(assembly.sensor).Volume,
        "grip_d435i_common_volume_mm3": grip.common(
            assembly.d435i_reference
        ).Volume,
        "grip_cap_common_volume_mm3": grip.common(assembly.grip_bottom_cap).Volume,
        "cells_grip_common_volume_mm3": assembly.cell_pack.common(grip).Volume,
        "grip_top_z": grip.BoundBox.ZMax,
        "grip_bottom_z": assembly.grip_bottom_cap.BoundBox.ZMin,
        # The grip hangs entirely below the compute carrier's Z envelope, so no
        # mesh sectioning against the board CAD is needed to prove clearance.
        "grip_carrier_reference_z_gap_mm": (
            BoardCoverParameters().reference_z_min - grip.BoundBox.ZMax
        ),
    }


def _save_fcstd(
    path: Path,
    root: Path,
    assembly: BoardBracketAssembly,
    parameters: BoardCoverParameters,
) -> None:
    document = App.newDocument("UAV_V3_MID360_Assembly")
    try:
        reference_path = root / "renders/UAV_V3_compute_carrier_reference_clean.stl"
        if not reference_path.is_file():
            raise FileNotFoundError(f"board reference mesh missing: {reference_path}")
        reference = document.addObject("Mesh::Feature", "ComputeCarrierReference")
        reference.Label = "UAV V3 compute carrier reference"
        reference.Mesh = Mesh.Mesh(str(reference_path))

        for name, label, shape in _named_local_shapes(assembly):
            _add_shape(
                document,
                name,
                label,
                _in_reference_coordinates(shape, parameters),
            )
        document.recompute()
        document.saveAs(str(path))
    finally:
        App.closeDocument(document.Name)


def _export_step(
    path: Path,
    root: Path,
    assembly: BoardBracketAssembly,
    parameters: BoardCoverParameters,
) -> int:
    document = App.newDocument("UAVV3MID360StepExport")
    try:
        reference_path = root / "renders/UAV_V3_compute_carrier_reference_clean.stl"
        if not reference_path.is_file():
            raise FileNotFoundError(f"board reference mesh missing: {reference_path}")
        reference_mesh = Mesh.Mesh(str(reference_path))
        reference_mesh.decimate(
            COVER_CARRIER_SECTION_TOLERANCE_MM,
            STEP_REFERENCE_DECIMATION_REDUCTION,
        )
        reference_shape = Part.Shape()
        reference_shape.makeShapeFromMesh(
            reference_mesh.Topology, COVER_CARRIER_SECTION_TOLERANCE_MM
        )
        if (
            reference_shape.isNull()
            or not reference_shape.isValid()
            or len(reference_shape.Faces) == 0
        ):
            raise ValueError("compute-carrier mesh did not convert to valid Part faces")
        reference = _add_shape(
            document,
            "ExportComputeCarrierReference",
            "UAV V3 compute carrier reference",
            reference_shape,
        )
        local_objects = [
            _add_shape(
                document,
                f"Export{index}",
                label,
                _in_reference_coordinates(shape, parameters),
            )
            for index, (_, label, shape) in enumerate(
                _named_local_shapes(assembly), start=1
            )
        ]
        document.recompute()
        Import.export([reference, *local_objects], str(path))
        return len(reference_shape.Faces)
    finally:
        App.closeDocument(document.Name)


def _step_reimport_validation(
    path: Path, expected_reference_bounds: tuple[float, ...]
) -> tuple[bool, tuple[str, ...], dict[str, bool]]:
    document = App.newDocument("CombinedStepValidation")
    try:
        Import.insert(str(path), document.Name)
        document.recompute()
        shape_objects = [
            obj
            for obj in document.Objects
            if hasattr(obj, "Shape") and not obj.Shape.isNull()
        ]
        labels = tuple(obj.Label for obj in shape_objects)
        required_members = tuple(
            prefix
            for prefix in REQUIRED_STEP_LABEL_PREFIXES
            if any(label.startswith(prefix) for label in labels)
        )
        forbidden_present = any(
            fragment in label
            for label in labels
            for fragment in FORBIDDEN_STEP_LABEL_FRAGMENTS
        )
        carrier_prefix = REQUIRED_STEP_LABEL_PREFIXES[0]
        carrier_contract_valid = any(
            obj.Label.startswith(carrier_prefix)
            and len(obj.Shape.Faces) > 0
            and len(obj.Shape.Edges) > 0
            and min(
                obj.Shape.BoundBox.XLength,
                obj.Shape.BoundBox.YLength,
                obj.Shape.BoundBox.ZLength,
            )
            > 0.0
            and all(
                isfinite(actual)
                and abs(actual - expected) <= COVER_CARRIER_SECTION_TOLERANCE_MM
                for actual, expected in zip(
                    (
                        obj.Shape.BoundBox.XMin,
                        obj.Shape.BoundBox.XMax,
                        obj.Shape.BoundBox.YMin,
                        obj.Shape.BoundBox.YMax,
                        obj.Shape.BoundBox.ZMin,
                        obj.Shape.BoundBox.ZMax,
                    ),
                    expected_reference_bounds,
                )
            )
            for obj in shape_objects
        )
        cad_products_valid = all(
            any(
                obj.Label.startswith(prefix)
                and obj.Shape.isValid()
                and len(obj.Shape.Faces) > 0
                and len(obj.Shape.Edges) > 0
                for obj in shape_objects
            )
            for prefix in REQUIRED_STEP_LABEL_PREFIXES[1:]
        )
        contracts = {
            "compute_carrier_step_reference_contract_valid": (
                carrier_contract_valid
            ),
            "step_existing_cad_products_valid": cad_products_valid,
            "step_forbidden_products_absent": not forbidden_present,
        }
        valid = (
            len(required_members) == len(REQUIRED_STEP_LABEL_PREFIXES)
            and all(contracts.values())
        )
        return valid, required_members, contracts
    finally:
        App.closeDocument(document.Name)


def build_board_bracket_outputs(
    project_root: Path, output_dir: Path | None = None
) -> tuple[Path, Path, Path]:
    """Save and validate the combined board/bracket FCStd, STEP, and report."""

    root = Path(project_root).resolve()
    parameters = BoardCoverParameters()
    bracket_parameters = BracketParameters()
    assembly = build_board_bracket_assembly(root)
    d435i_interference_sections = _d435i_reference_interference_sections(assembly)
    if any(d435i_interference_sections.values()):
        raise ValueError(
            "D435i reference intersects the assembly outside its shelf support: "
            f"{d435i_interference_sections}"
        )
    grip_fields = _battery_grip_report_fields(assembly)
    grip_interference = {
        name: value
        for name, value in grip_fields.items()
        if name.endswith("_common_volume_mm3") and value >= 1e-6
    }
    if grip_interference:
        raise ValueError(
            f"battery grip interferes with the assembly: {grip_interference}"
        )
    if grip_fields["grip_carrier_reference_z_gap_mm"] <= 0.0:
        raise ValueError(
            "battery grip reaches into the compute-carrier Z envelope: "
            f"{grip_fields['grip_carrier_reference_z_gap_mm']} mm"
        )
    (
        clearance_results,
        reference_face_count,
        reference_is_solid,
        reference_bounds,
    ) = _cover_reference_clearance_results(root, assembly, parameters)
    unexpected_fields = (
        "top_cover_carrier_unexpected_intersection_count",
        "bottom_cover_carrier_unexpected_intersection_count",
    )
    if any(clearance_results[field] != 0 for field in unexpected_fields):
        raise ValueError(
            "cover intersects compute-carrier reference outside allowed contacts: "
            f"{clearance_results}"
        )
    if output_dir is None:
        fcstd_path = root / "models/UAV_V3_board_mid360_assembly.FCStd"
        step_path = root / "exports/UAV_V3_board_mid360_assembly.step"
        report_path = root / "reports/UAV_V3_board_mid360_assembly.json"
    else:
        destination = Path(output_dir).resolve()
        fcstd_path = destination / "UAV_V3_board_mid360_assembly.FCStd"
        step_path = destination / "UAV_V3_board_mid360_assembly.step"
        report_path = destination / "UAV_V3_board_mid360_assembly.json"
    for directory in {fcstd_path.parent, step_path.parent, report_path.parent}:
        directory.mkdir(parents=True, exist_ok=True)

    _save_fcstd(fcstd_path, root, assembly, parameters)
    step_reference_face_count = _export_step(step_path, root, assembly, parameters)
    step_valid, step_members, step_contracts = _step_reimport_validation(
        step_path, reference_bounds
    )
    if not step_valid:
        raise ValueError(
            "combined assembly STEP failed round-trip membership validation: "
            f"members={step_members}, contracts={step_contracts}"
        )

    report = {
        "schema_version": 1,
        "bracket_angle_deg": BRACKET_ANGLE_DEG,
        "standoff_height_mm": BRACKET_STANDOFF_HEIGHT_MM,
        "tilt_screw_models_included": False,
        "battery_grip_included": True,
        "cover_mounting_hole_diameter_mm": parameters.mounting_hole_diameter,
        "tilt_clearance_hole_diameter_mm": bracket_parameters.b_clearance_hole_diameter,
        "tilt_pilot_hole_diameter_mm": bracket_parameters.a_b_pilot_hole_diameter,
        "bottom_standoff_height_mm": parameters.bottom_standoff_height,
        "lock_radius_mm": bracket_parameters.lock_radius,
        "working_angle_deg": bracket_parameters.working_angle_deg,
        "part_b_size_mm": [
            bracket_parameters.b_base_width,
            bracket_parameters.b_base_depth,
            bracket_parameters.b_base_thickness,
        ],
        "part_b_body_size_mm": [
            bracket_parameters.b_base_width,
            bracket_parameters.b_base_depth,
            bracket_parameters.b_base_thickness,
        ],
        "part_b_plan_envelope_mm": [
            bracket_parameters.b_base_width,
            bracket_parameters.b_base_depth + bracket_parameters.d435i_shelf_depth,
        ],
        "mount_hole_pitch_mm": [
            parameters.board_length + parameters.bottom_end_extension,
            parameters.bottom_extension_hole_y_pitch * 7.0,
        ],
        "d435i_shelf_size_mm": [
            bracket_parameters.d435i_shelf_width,
            bracket_parameters.d435i_shelf_depth,
            bracket_parameters.b_base_thickness,
        ],
        "d435i_mount_clearance_diameter_mm": (
            bracket_parameters.d435i_mount_clearance_diameter
        ),
        "d435i_screw_models_included": False,
        "d435i_screw_head_clearance_mm": (
            BRACKET_STANDOFF_HEIGHT_MM - bracket_parameters.d435i_screw_head_height
        ),
        "cover_carrier_section_method": "mesh_surface_section",
        "cover_carrier_section_tolerance_mm": (
            COVER_CARRIER_SECTION_TOLERANCE_MM
        ),
        "compute_carrier_reference_mesh_face_count": reference_face_count,
        "compute_carrier_reference_mesh_is_solid": reference_is_solid,
        "compute_carrier_step_decimation_max_error_mm": (
            COVER_CARRIER_SECTION_TOLERANCE_MM
        ),
        "compute_carrier_step_decimation_reduction": (
            STEP_REFERENCE_DECIMATION_REDUCTION
        ),
        "compute_carrier_step_face_count": step_reference_face_count,
        "step_required_member_count": len(step_members),
        "step_required_members": list(step_members),
        **step_contracts,
        **clearance_results,
        "part_b_top_cover_common_volume_mm3": assembly.part_b.common(
            assembly.top_cover
        ).Volume,
        "part_a_top_cover_common_volume_mm3": assembly.part_a.common(
            assembly.top_cover
        ).Volume,
        "sensor_top_cover_common_volume_mm3": assembly.sensor.common(
            assembly.top_cover
        ).Volume,
        "sensor_part_b_common_volume_mm3": assembly.sensor.common(
            assembly.part_b
        ).Volume,
        **_battery_grip_report_fields(assembly),
        "step_reimport_valid": step_valid,
        **_d435i_reference_report_fields(
            assembly, d435i_interference_sections
        ),
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return fcstd_path, step_path, report_path
