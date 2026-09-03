"""Export one STEP per printable PLA part, plus one combined handle-free STEP.

Every part is written in its printing orientation, seated on Z = 0 and centred
on the origin, so a file can go straight into a slicer.  The bed-packing
rotations live in :mod:`bracket.print_plate`; this module only decides which
face each part is printed on.

The combined file holds the four board/bracket parts laid out on one
256 x 256 mm bed.  The battery grip is deliberately excluded: it has its own
plate in :func:`bracket.battery_grip.build_battery_grip_print_plate`.
"""

from pathlib import Path

import FreeCAD as App
import Import
import Part

from .battery_grip import BatteryGripParameters, make_bottom_cap, make_grip_body
from .board_covers import BoardCoverParameters, make_bottom_cover, make_top_cover
from .freecad_geometry import make_board_mounted_part_b, make_part_a
from .parameters import BracketParameters
from .print_plate import build_print_plate, place_on_bed


STEP_DIRECTORY = "step"
COMBINED_STEP_NAME = "board_and_bracket_all_parts.step"
# The four board/bracket parts share one bed; the grip has its own.
COMBINED_PART_COUNT = 4

def printable_parts() -> tuple[tuple[str, str, Part.Shape], ...]:
    """Return every PLA part as (file stem, STEP label, print-oriented solid).

    The rotation on each entry is only "which face goes down"; nothing here
    packs a bed, so each part stays centred on the origin.
    """

    bracket = BracketParameters()
    covers = BoardCoverParameters()
    grip = BatteryGripParameters()
    x_axis = App.Vector(1.0, 0.0, 0.0)
    flip = ((x_axis, 180.0),)

    return (
        (
            "part_a_radar_plate",
            "Part A · MID-360 radar plate",
            # Authored top-down, so it flips to print on its flat top face.
            place_on_bed(make_part_a(bracket), 0.0, 0.0, flip),
        ),
        (
            "part_b_tilt_base",
            "Part B · tilt base",
            # Base plate is already the lowest face; sectors point up.
            place_on_bed(make_board_mounted_part_b(bracket), 0.0, 0.0, ()),
        ),
        (
            "board_cover_upper",
            "UAV V3 upper board cover",
            place_on_bed(make_top_cover(covers), 0.0, 0.0, flip),
        ),
        (
            "board_cover_lower",
            "UAV V3 lower board cover",
            place_on_bed(make_bottom_cover(covers), 0.0, 0.0, ()),
        ),
        (
            "battery_grip_body",
            "Battery grip body",
            # Flange down: 128 x 78 first layer, cone self-supporting above it.
            place_on_bed(make_grip_body(grip), 0.0, 0.0, flip),
        ),
        (
            "battery_grip_bottom_cap",
            "Battery grip bottom cap",
            place_on_bed(make_bottom_cap(grip), 0.0, 0.0, flip),
        ),
    )


def _export(path: Path, named: tuple[tuple[str, Part.Shape], ...]) -> None:
    """Write one STEP holding *named* shapes, each as its own labelled product."""

    document = App.newDocument(f"StepExport_{path.stem}")
    try:
        objects = []
        for index, (label, shape) in enumerate(named, start=1):
            obj = document.addObject("Part::Feature", f"Product{index}")
            obj.Label = label
            obj.Shape = shape
            objects.append(obj)
        document.recompute()
        Import.export(objects, str(path))
    finally:
        App.closeDocument(document.Name)


def _reimported_solid_count(path: Path) -> int:
    """Return how many valid solids a written STEP hands back."""

    document = App.newDocument(f"StepCheck_{path.stem}")
    try:
        Import.insert(str(path), document.Name)
        document.recompute()
        shapes = [
            obj.Shape
            for obj in document.Objects
            if obj.TypeId == "Part::Feature"
            and hasattr(obj, "Shape")
            and not obj.Shape.isNull()
        ]
        if not all(shape.isValid() and shape.Volume > 1.0 for shape in shapes):
            return -1
        return sum(len(shape.Solids) for shape in shapes)
    finally:
        App.closeDocument(document.Name)


def build_step_package(
    project_root: Path,
    output_dir: Path | None = None,
) -> tuple[Path, ...]:
    """Write one STEP per PLA part plus the combined handle-free STEP.

    Every file is round-tripped before returning, so a corrupt or accidentally
    fused export fails here rather than in a slicer.
    """

    root = Path(project_root).resolve()
    destination = (
        Path(output_dir).resolve() if output_dir else root / STEP_DIRECTORY
    )
    destination.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for stem, label, shape in printable_parts():
        if not (shape.isValid() and len(shape.Solids) == 1):
            raise ValueError(f"{stem} is not a single valid solid")
        if abs(shape.BoundBox.ZMin) > 1e-6:
            raise ValueError(f"{stem} does not sit on Z = 0")
        path = destination / f"{stem}.step"
        _export(path, ((label, shape),))
        if _reimported_solid_count(path) != 1:
            raise ValueError(f"{path.name} did not round-trip as one valid solid")
        written.append(path)

    combined = destination / COMBINED_STEP_NAME
    plate = build_print_plate()
    if len(plate) != COMBINED_PART_COUNT:
        raise ValueError(
            f"expected {COMBINED_PART_COUNT} board/bracket parts, got {len(plate)}"
        )
    _export(combined, plate)
    if _reimported_solid_count(combined) != COMBINED_PART_COUNT:
        raise ValueError(
            f"{combined.name} did not round-trip as {COMBINED_PART_COUNT} solids"
        )
    written.append(combined)
    return tuple(written)
