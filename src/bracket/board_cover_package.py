"""Export and validate the UAV V3 board-cover CAD package."""

from dataclasses import asdict
import json
from pathlib import Path

import FreeCAD as App
import Import
import Mesh

from bracket.board_covers import (
    BoardCoverParameters,
    make_bottom_cover,
    make_top_cover,
    place_in_reference_coordinates,
)


def _add_part(document, name: str, label: str, shape):
    obj = document.addObject("PartDesign::Feature", name)
    obj.Label = label
    obj.Shape = shape
    return obj


def _export_step(path: Path, objects) -> None:
    Import.export(list(objects), str(path))


def _export_stl(path: Path, obj) -> None:
    Mesh.export([obj], str(path))


def _step_reimports(path: Path) -> bool:
    document = App.newDocument("StepValidation")
    try:
        Import.insert(str(path), document.Name)
        document.recompute()
        shapes = [
            obj.Shape
            for obj in document.Objects
            if hasattr(obj, "Shape") and not obj.Shape.isNull()
        ]
        return bool(shapes) and all(shape.isValid() for shape in shapes)
    finally:
        App.closeDocument(document.Name)


def _stl_reimports(path: Path) -> bool:
    document = App.newDocument("MeshValidation")
    try:
        Mesh.insert(str(path), document.Name)
        document.recompute()
        meshes = [
            obj.Mesh
            for obj in document.Objects
            if hasattr(obj, "Mesh") and obj.Mesh.CountFacets > 0
        ]
        return bool(meshes)
    finally:
        App.closeDocument(document.Name)


def _write_fcstd(
    path: Path,
    top_shape,
    bottom_shape,
    parameters: BoardCoverParameters,
    reference_mesh_path: Path,
) -> bool:
    document = App.newDocument("UAV_V3_Board_Covers")
    try:
        top = _add_part(document, "TopCover", "UAV V3 upper cover", top_shape)
        bottom = _add_part(
            document, "BottomCover", "UAV V3 lower cover", bottom_shape
        )
        top.addProperty("App::PropertyString", "Material", "Design")
        top.Material = "PLA"
        bottom.addProperty("App::PropertyString", "Material", "Design")
        bottom.Material = "PLA"

        parameter_sheet = document.addObject("Spreadsheet::Sheet", "Parameters")
        parameter_sheet.set("A1", "Parameter")
        parameter_sheet.set("B1", "Value (mm or deg)")
        for row, (name, value) in enumerate(asdict(parameters).items(), start=2):
            parameter_sheet.set(f"A{row}", name)
            parameter_sheet.set(f"B{row}", str(value))

        reference_included = reference_mesh_path.is_file()
        if reference_included:
            reference = document.addObject("Mesh::Feature", "ComputeCarrierReference")
            reference.Label = "UAV V3 compute carrier (reference mesh)"
            reference.Mesh = Mesh.Mesh(str(reference_mesh_path))

        document.recompute()
        document.saveAs(str(path))
        return reference_included
    finally:
        App.closeDocument(document.Name)


def build_board_cover_outputs(root: Path) -> dict:
    """Build, export, round-trip validate, and report all cover CAD files."""

    root = Path(root)
    export_dir = root / "exports"
    model_dir = root / "models"
    report_dir = root / "reports"
    for directory in (export_dir, model_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)

    parameters = BoardCoverParameters()
    top_local = make_top_cover(parameters)
    bottom_local = make_bottom_cover(parameters)
    top_placed = place_in_reference_coordinates(top_local, parameters)
    bottom_placed = place_in_reference_coordinates(bottom_local, parameters)

    document = App.newDocument("BoardCoverExports")
    try:
        top_local_obj = _add_part(document, "TopCover", "UAV V3 upper cover", top_local)
        bottom_local_obj = _add_part(
            document, "BottomCover", "UAV V3 lower cover", bottom_local
        )
        top_placed_obj = _add_part(
            document, "TopCoverPlaced", "UAV V3 upper cover", top_placed
        )
        bottom_placed_obj = _add_part(
            document, "BottomCoverPlaced", "UAV V3 lower cover", bottom_placed
        )
        document.recompute()

        top_step = export_dir / "UAV_V3_top_cover.step"
        top_stl = export_dir / "UAV_V3_top_cover.stl"
        bottom_step = export_dir / "UAV_V3_bottom_cover.step"
        bottom_stl = export_dir / "UAV_V3_bottom_cover.stl"
        assembly_step = export_dir / "UAV_V3_board_covers_assembly.step"
        _export_step(top_step, (top_local_obj,))
        _export_stl(top_stl, top_local_obj)
        _export_step(bottom_step, (bottom_local_obj,))
        _export_stl(bottom_stl, bottom_local_obj)
        _export_step(assembly_step, (top_placed_obj, bottom_placed_obj))
    finally:
        App.closeDocument(document.Name)

    reference_included = _write_fcstd(
        model_dir / "UAV_V3_board_covers.FCStd",
        top_placed,
        bottom_placed,
        parameters,
        root / "renders/UAV_V3_compute_carrier_reference_clean.stl",
    )

    reimports = {
        "exports/UAV_V3_board_covers_assembly.step": _step_reimports(assembly_step),
        "exports/UAV_V3_bottom_cover.step": _step_reimports(bottom_step),
        "exports/UAV_V3_bottom_cover.stl": _stl_reimports(bottom_stl),
        "exports/UAV_V3_top_cover.step": _step_reimports(top_step),
        "exports/UAV_V3_top_cover.stl": _stl_reimports(top_stl),
    }
    report = {
        "schema_version": 1,
        "parameters": asdict(parameters),
        "reference_mesh_included": reference_included,
        "reimports": reimports,
        "top_standoff_height_mm": parameters.top_standoff_height,
        "bottom_standoff_height_mm": parameters.bottom_standoff_height,
        "standoff_outer_diameter_mm": parameters.standoff_outer_diameter,
        "mounting_hole_diameter_mm": parameters.mounting_hole_diameter,
    }
    report_path = report_dir / "UAV_V3_board_cover_validation.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
