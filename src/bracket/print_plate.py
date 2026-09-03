"""Arrange all four PLA parts for one 256 x 256 mm print job."""

from pathlib import Path
from typing import Iterable

import FreeCAD as App
import Import
import Part

from .board_covers import BoardCoverParameters, make_bottom_cover, make_top_cover
from .freecad_geometry import make_board_mounted_part_b, make_part_a
from .parameters import BracketParameters


NamedShapes = tuple[tuple[str, Part.Shape], ...]


def place_on_bed(
    shape: Part.Shape,
    center_x: float,
    center_y: float,
    rotations: Iterable[tuple[App.Vector, float]],
) -> Part.Shape:
    """Rotate a shape, then seat it on Z = 0 centred at (*center_x*, *center_y*)."""

    placed = shape.copy()
    for axis, angle_deg in rotations:
        rotation = App.Placement(
            App.Vector(), App.Rotation(axis, angle_deg)
        )
        placed.Placement = rotation * placed.Placement

    bounds = placed.BoundBox
    translation = App.Placement(
        App.Vector(
            center_x - bounds.Center.x,
            center_y - bounds.Center.y,
            -bounds.ZMin,
        ),
        App.Rotation(),
    )
    placed.Placement = translation * placed.Placement
    return placed


def build_print_plate() -> NamedShapes:
    """Return four independent solids arranged within a centered 256 mm bed."""

    bracket = BracketParameters()
    covers = BoardCoverParameters()
    x_axis = App.Vector(1.0, 0.0, 0.0)
    z_axis = App.Vector(0.0, 0.0, 1.0)
    rotate_z_90 = ((z_axis, 90.0),)

    return (
        (
            "Part B tilt base",
            place_on_bed(
                make_board_mounted_part_b(bracket), -75.0, 50.0, rotate_z_90
            ),
        ),
        (
            "Upper board cover",
            place_on_bed(
                make_top_cover(covers),
                54.0,
                55.0,
                ((x_axis, 180.0),),
            ),
        ),
        (
            "Lower board cover",
            place_on_bed(
                make_bottom_cover(covers), 54.0, -45.0, ()
            ),
        ),
        (
            "Part A radar plate",
            place_on_bed(
                make_part_a(bracket),
                -75.0,
                -65.0,
                ((x_axis, 180.0),),
            ),
        ),
    )


def build_print_plate_outputs(
    project_root: Path,
    output_directory: Path | None = None,
) -> Path:
    """Export the four-part print layout as one multi-body STEP file."""

    root = Path(project_root).resolve()
    destination = (
        Path(output_directory)
        if output_directory is not None
        else root / "exports"
    )
    destination.mkdir(parents=True, exist_ok=True)
    step_path = destination / "all_PLA_parts_256x256_print_plate.step"

    document = App.newDocument("AllPLAPartsPrintPlate")
    try:
        objects = []
        for index, (label, shape) in enumerate(build_print_plate(), start=1):
            obj = document.addObject("Part::Feature", f"PrintPart{index}")
            obj.Label = label
            obj.Shape = shape
            objects.append(obj)
        document.recompute()
        Import.export(objects, str(step_path))
    finally:
        App.closeDocument(document.Name)

    return step_path
