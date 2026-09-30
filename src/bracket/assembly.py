"""Assemble, validate, save, export, and reimport the bracket CAD package."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path
from typing import Any, Iterable

import FreeCAD as App
import Import
import Mesh
import Part

from .freecad_geometry import make_board_mounted_part_b, make_part_a
from .official_sensor import load_normalized_mid360_with_metadata
from .parameters import BracketParameters


REVIEW_ANGLES = (0.0, 20.0, 40.0)
VISIBLE_ANGLE_DEG = 0.0


@dataclass(frozen=True)
class AssemblyShapes:
    """All rigid shapes in one bracket pose."""

    part_a: Part.Shape
    part_b: Part.Shape
    sensor: Part.Shape
    side_screws: tuple[Part.Shape, ...]
    sensor_screws: tuple[Part.Shape, ...]


def placement_for_angle(p: BracketParameters, angle_deg: float) -> App.Placement:
    """Map A's local pivot onto B's global pivot at the requested pitch."""

    if not 0.0 <= angle_deg <= p.working_angle_deg:
        raise ValueError(f"angle must be in [0, {p.working_angle_deg}] degrees")
    global_pivot = App.Vector(
        0.0,
        p.b_pivot_y,
        p.b_base_thickness + p.pivot_z_above_base,
    )
    local_pivot = App.Vector(0.0, p.a_pivot_y, p.a_pivot_z)
    rotation = App.Rotation(App.Vector(1.0, 0.0, 0.0), -angle_deg)
    placement = App.Placement()
    placement.Rotation = rotation
    placement.Base = global_pivot - rotation.multVec(local_pivot)
    return placement


def _placed(shape: Part.Shape, placement: App.Placement) -> Part.Shape:
    placed = shape.copy()
    placed.Placement = placement * placed.Placement
    return placed


def _make_m3_side_screw(
    p: BracketParameters,
    side: float,
    y: float,
    z: float,
    outer_face_inset: float = 0.0,
) -> Part.Shape:
    """M3 screw through B's side wall into an M3 heat-set insert in Part A."""

    wall_outer_x = p.b_inner_width / 2.0 + p.b_wall_thickness
    outer_face_x = side * (wall_outer_x - outer_face_inset)
    inward = App.Vector(-side, 0.0, 0.0)
    shaft = Part.makeCylinder(
        1.5,
        p.m3_screw_length,
        App.Vector(outer_face_x, y, z),
        inward,
    )
    head_thickness = 3.0
    head = Part.makeCylinder(
        3.0,
        head_thickness,
        App.Vector(outer_face_x + side * head_thickness, y, z),
        inward,
    )
    return shaft.fuse(head).removeSplitter()


def _make_m3_screw(p: BracketParameters, x: float, y: float) -> Part.Shape:
    shaft = Part.makeCylinder(
        1.5,
        p.m3_screw_length,
        App.Vector(x, y, -p.a_plate_thickness),
    )
    head = Part.makeCylinder(
        3.0,
        3.0,
        App.Vector(x, y, -p.a_plate_thickness - 3.0),
    )
    return shaft.fuse(head).removeSplitter()


def build_assembly(
    p: BracketParameters, sensor_shape: Part.Shape, angle_deg: float
) -> AssemblyShapes:
    """Build one complete rigid assembly at *angle_deg*."""

    placement = placement_for_angle(p, angle_deg)
    lock_point = placement.multVec(
        App.Vector(0.0, p.a_pivot_y - p.lock_radius, p.a_pivot_z)
    )
    pivot_point = placement.multVec(App.Vector(0.0, p.a_pivot_y, p.a_pivot_z))
    side_screws = (
        *tuple(
            _make_m3_side_screw(p, side, pivot_point.y, pivot_point.z)
            for side in (-1.0, 1.0)
        ),
        *tuple(
            _make_m3_side_screw(
                p,
                side,
                lock_point.y,
                lock_point.z,
                outer_face_inset=p.track_recess_depth,
            )
            for side in (-1.0, 1.0)
        ),
    )
    sensor_screws = tuple(
        _placed(_make_m3_screw(p, x, y), placement)
        for x in (-p.sensor_mount_pitch_x / 2.0, p.sensor_mount_pitch_x / 2.0)
        for y in (-p.sensor_mount_pitch_y / 2.0, p.sensor_mount_pitch_y / 2.0)
    )
    return AssemblyShapes(
        part_a=_placed(make_part_a(p), placement),
        part_b=make_board_mounted_part_b(p),
        sensor=_placed(sensor_shape, placement),
        side_screws=side_screws,
        sensor_screws=sensor_screws,
    )


def validate_assembly(shapes: AssemblyShapes) -> dict[str, float | bool]:
    """Return validity and unintended A/B, sensor/A, and sensor/B common volumes."""

    return {
        "a_b_common_volume_mm3": shapes.part_a.common(shapes.part_b).Volume,
        "sensor_a_common_volume_mm3": shapes.sensor.common(shapes.part_a).Volume,
        "sensor_b_common_volume_mm3": shapes.sensor.common(shapes.part_b).Volume,
        "a_valid": shapes.part_a.isValid() and shapes.part_a.Volume > 1.0,
        "b_valid": shapes.part_b.isValid() and shapes.part_b.Volume > 1.0,
        "sensor_valid": shapes.sensor.isValid() and shapes.sensor.Volume > 1.0,
    }


def _add_shape(
    document: App.Document, name: str, label: str, shape: Part.Shape
) -> App.DocumentObject:
    obj = document.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape
    return obj


def _save_fcstd(path: Path, p: BracketParameters, shapes: AssemblyShapes) -> int:
    document = App.newDocument("MID360TiltBracket")
    try:
        spreadsheet = document.addObject("Spreadsheet::Sheet", "Parameters")
        spreadsheet.Label = "Bracket Parameters"
        spreadsheet.set("A1", "Parameter")
        spreadsheet.set("B1", "Value")
        spreadsheet.set("C1", "Unit")
        for row, field in enumerate(fields(p), start=2):
            spreadsheet.set(f"A{row}", field.name)
            spreadsheet.set(f"B{row}", str(getattr(p, field.name)))
            spreadsheet.set(f"C{row}", "deg" if field.name.endswith("_deg") else "mm")
            spreadsheet.setAlias(f"B{row}", field.name)

        group_b = document.addObject("App::DocumentObjectGroup", "PartB")
        group_b.Label = "Part B - Fixed Base"
        group_b.addObject(_add_shape(document, "PartBShape", "Part B", shapes.part_b))

        group_a = document.addObject("App::DocumentObjectGroup", "PartA")
        group_a.Label = f"Part A - {VISIBLE_ANGLE_DEG:g} deg"
        group_a.addObject(_add_shape(document, "PartAShape", "Part A", shapes.part_a))

        group_sensor = document.addObject("App::DocumentObjectGroup", "Sensor")
        group_sensor.Label = f"Official MID-360 - {VISIBLE_ANGLE_DEG:g} deg"
        group_sensor.addObject(
            _add_shape(document, "OfficialMID360", "Official MID-360", shapes.sensor)
        )

        group_screws = document.addObject("App::DocumentObjectGroup", "Screws")
        group_screws.Label = "Metal Screws"
        for index, screw in enumerate(shapes.side_screws, start=1):
            group_screws.addObject(
                _add_shape(
                    document,
                    f"M3Screw{index}",
                    f"M3 x 8 Screw {index}",
                    screw,
                )
            )
        for index, screw in enumerate(shapes.sensor_screws, start=1):
            group_screws.addObject(
                _add_shape(
                    document,
                    f"M3SensorScrew{index}",
                    f"M3 x 8 Sensor Screw {index}",
                    screw,
                )
            )

        document.recompute()
        document.saveAs(str(path))
        return len(fields(p))
    finally:
        App.closeDocument(document.Name)


def _export_step(path: Path, named_shapes: Iterable[tuple[str, Part.Shape]]) -> None:
    document = App.newDocument(f"ExportSTEP_{path.stem}")
    try:
        objects = [
            _add_shape(document, f"Shape{index}", label, shape)
            for index, (label, shape) in enumerate(named_shapes, start=1)
        ]
        document.recompute()
        Import.export(objects, str(path))
    finally:
        App.closeDocument(document.Name)


def _export_stl(path: Path, shape: Part.Shape) -> None:
    document = App.newDocument(f"ExportSTL_{path.stem}")
    try:
        obj = _add_shape(document, "PrintableShape", path.stem, shape)
        document.recompute()
        Mesh.export([obj], str(path))
    finally:
        App.closeDocument(document.Name)


def _step_reimports_as_valid_shape(path: Path) -> bool:
    document = App.newDocument(f"ReimportSTEP_{path.stem}")
    try:
        Import.insert(str(path), document.Name)
        document.recompute()
        shapes = [
            obj.Shape
            for obj in document.Objects
            if hasattr(obj, "Shape")
            and not obj.Shape.isNull()
            and (obj.TypeId.startswith("Part::") or obj.TypeId == "App::Part")
            and (len(obj.Shape.Faces) > 0 or len(obj.Shape.Solids) > 0)
        ]
        return bool(shapes) and all(
            shape.isValid()
            and len(shape.Edges) > 0
            and max(
                shape.BoundBox.XLength,
                shape.BoundBox.YLength,
                shape.BoundBox.ZLength,
            )
            > 0.0
            for shape in shapes
        )
    finally:
        App.closeDocument(document.Name)


def _stl_reimports_as_valid_shape(path: Path) -> bool:
    document = App.newDocument(f"ReimportSTL_{path.stem}")
    try:
        Mesh.insert(str(path), document.Name)
        document.recompute()
        meshes = [
            obj.Mesh
            for obj in document.Objects
            if hasattr(obj, "Mesh") and obj.Mesh.CountFacets > 0
        ]
        if not meshes:
            return False
        for mesh in meshes:
            shape = Part.Shape()
            shape.makeShapeFromMesh(mesh.Topology, 0.05)
            if shape.isNull() or not shape.isValid() or len(shape.Faces) == 0:
                return False
        return True
    finally:
        App.closeDocument(document.Name)


def _print_oriented_part_a(p: BracketParameters) -> Part.Shape:
    rotation = App.Placement(
        App.Vector(), App.Rotation(App.Vector(1.0, 0.0, 0.0), 180.0)
    )
    printable = _placed(make_part_a(p), rotation)
    correction = App.Placement(
        App.Vector(0.0, 0.0, -printable.BoundBox.ZMin), App.Rotation()
    )
    return _placed(printable, correction)


def _assembly_named_shapes(
    shapes: AssemblyShapes,
) -> tuple[tuple[str, Part.Shape], ...]:
    return (
        ("Part B", shapes.part_b),
        ("Part A", shapes.part_a),
        ("Official MID-360", shapes.sensor),
        *tuple(
            (f"M3 x 8 Screw {index}", screw)
            for index, screw in enumerate(shapes.side_screws, start=1)
        ),
        *tuple(
            (f"M3 x 8 Sensor Screw {index}", screw)
            for index, screw in enumerate(shapes.sensor_screws, start=1)
        ),
    )


def build_all_outputs(root: Path) -> dict[str, object]:
    """Build, validate, save, export, reimport, and report all CAD artifacts."""

    project_root = Path(root).resolve()
    models_dir = project_root / "models"
    exports_dir = project_root / "exports"
    reports_dir = project_root / "reports"
    for directory in (models_dir, exports_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    p = BracketParameters()
    sensor, official_metadata = load_normalized_mid360_with_metadata(
        project_root / "vendor/livox/mid-360-asm.stp"
    )
    assemblies: list[dict[str, float | bool]] = []
    for angle in REVIEW_ANGLES:
        shapes = build_assembly(p, sensor, angle)
        result = validate_assembly(shapes)
        result["angle_deg"] = angle
        if not all(result[key] for key in ("a_valid", "b_valid", "sensor_valid")):
            raise ValueError(f"invalid shape at {angle} degrees: {result}")
        if result["a_b_common_volume_mm3"] >= 1e-6:
            raise ValueError(f"A/B collision at {angle} degrees: {result}")
        if result["sensor_a_common_volume_mm3"] >= 1e-6:
            raise ValueError(f"sensor/A collision at {angle} degrees: {result}")
        if result["sensor_b_common_volume_mm3"] >= 1e-6:
            raise ValueError(f"sensor/B collision at {angle} degrees: {result}")
        assemblies.append(result)

    visible_shapes = build_assembly(p, sensor, VISIBLE_ANGLE_DEG)
    fcstd_relative = Path("models/mid360_tilt_bracket.FCStd")
    parameter_count = _save_fcstd(project_root / fcstd_relative, p, visible_shapes)

    a_step = Path("exports/A_mid360_mount.step")
    a_stl = Path("exports/A_mid360_mount.stl")
    b_step = Path("exports/B_tilt_base.step")
    b_stl = Path("exports/B_tilt_base.stl")
    assembly_step = Path("exports/mid360_tilt_bracket_assembly.step")

    _export_step(project_root / a_step, (("Part A", make_part_a(p)),))
    _export_stl(project_root / a_stl, _print_oriented_part_a(p))
    _export_step(project_root / b_step, (("Part B", make_board_mounted_part_b(p)),))
    _export_stl(project_root / b_stl, make_board_mounted_part_b(p))
    _export_step(
        project_root / assembly_step,
        _assembly_named_shapes(visible_shapes),
    )

    reimport_paths = (a_step, a_stl, b_step, b_stl, assembly_step)
    reimports: dict[str, bool] = {}
    for relative in reimport_paths:
        path = project_root / relative
        valid = (
            _stl_reimports_as_valid_shape(path)
            if path.suffix.lower() == ".stl"
            else _step_reimports_as_valid_shape(path)
        )
        if not valid:
            raise ValueError(f"export does not reimport as valid geometry: {relative}")
        reimports[str(relative)] = valid

    report: dict[str, object] = {
        "schema_version": 1,
        "angles": list(REVIEW_ANGLES),
        "visible_angle_deg": VISIBLE_ANGLE_DEG,
        "parameter_count": parameter_count,
        "parameters": asdict(p),
        "official_model": official_metadata,
        "assemblies": assemblies,
        "reimports": reimports,
    }
    report_path = reports_dir / "geometry_validation.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
