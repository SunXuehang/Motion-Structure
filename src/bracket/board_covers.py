"""Parametric flat cover plates for the UAV V3 compute-carrier assembly."""

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

import FreeCAD as App
import Part


@dataclass(frozen=True)
class BoardCoverParameters:
    """Source dimensions derived from the extracted UAV V3 CAD, in millimetres."""

    board_length: float = 108.0
    board_width: float = 78.0
    corner_radius: float = 4.0
    plate_thickness: float = 3.0
    reference_z_min: float = 0.0
    reference_z_max: float = 48.1784
    board_mounting_z_min: float = 10.5
    board_mounting_z_max: float = 23.1522
    mount_pitch_x: float = 100.0
    mount_pitch_y: float = 70.0
    mounting_hole_diameter: float = 3.4
    standoff_outer_diameter: float = 6.0
    top_standoff_height: float = 10.0
    bottom_standoff_height: float = 13.0
    rim_thickness: float = 1.5
    top_rim_height: float = 4.0
    bottom_rim_height: float = 5.5
    bottom_end_extension: float = 10.0
    bottom_extension_hole_y_pitch: float = 10.0
    top_fan_center_x: float = -0.153
    top_fan_center_y: float = 6.830
    top_fan_opening_length: float = 60.0
    top_fan_opening_width: float = 41.0
    top_fan_opening_corner_radius: float = 2.0
    bottom_fan_center_x: float = -11.3610
    bottom_fan_center_y: float = -2.3275
    bottom_fan_opening_length: float = 24.0
    bottom_fan_opening_width: float = 24.0
    bottom_fan_opening_corner_radius: float = 3.0
    bottom_imu_center_x: float = 33.6671
    bottom_imu_center_y: float = -2.5159
    bottom_imu_opening_length: float = 14.0
    bottom_imu_opening_width: float = 18.0
    bottom_imu_opening_corner_radius: float = 1.0
    reference_center_x: float = 47.7845
    reference_center_y: float = 60.6035
    reference_rotation_deg: float = 80.0

    def __post_init__(self) -> None:
        positive = (
            self.board_length,
            self.board_width,
            self.plate_thickness,
            self.mount_pitch_x,
            self.mount_pitch_y,
            self.mounting_hole_diameter,
            self.standoff_outer_diameter,
            self.top_standoff_height,
            self.bottom_standoff_height,
            self.rim_thickness,
            self.top_rim_height,
            self.bottom_rim_height,
            self.bottom_end_extension,
            self.bottom_extension_hole_y_pitch,
            self.top_fan_opening_length,
            self.top_fan_opening_width,
            self.top_fan_opening_corner_radius,
            self.bottom_fan_opening_length,
            self.bottom_fan_opening_width,
            self.bottom_fan_opening_corner_radius,
            self.bottom_imu_opening_length,
            self.bottom_imu_opening_width,
            self.bottom_imu_opening_corner_radius,
        )
        if any(value <= 0.0 for value in positive):
            raise ValueError("cover dimensions must be positive")
        if not all(
            isfinite(value)
            for value in (
                self.reference_z_min,
                self.reference_z_max,
                self.board_mounting_z_min,
                self.board_mounting_z_max,
                self.top_fan_center_x,
                self.top_fan_center_y,
                self.bottom_fan_center_x,
                self.bottom_fan_center_y,
                self.bottom_imu_center_x,
                self.bottom_imu_center_y,
                self.reference_center_x,
                self.reference_center_y,
                self.reference_rotation_deg,
            )
        ):
            raise ValueError("cover reference coordinates must be finite")
        if self.reference_z_max <= self.reference_z_min:
            raise ValueError("reference Z envelope must have positive height")
        if self.board_mounting_z_max <= self.board_mounting_z_min:
            raise ValueError("board mounting faces must have positive separation")
        if self.standoff_outer_diameter <= self.mounting_hole_diameter:
            raise ValueError("standoff must have material around its through-hole")
        if self.top_rim_height >= self.top_standoff_height:
            raise ValueError("top rim cannot reach the PCB mounting plane")
        if self.bottom_rim_height >= self.bottom_standoff_height:
            raise ValueError("bottom rim cannot reach the PCB mounting plane")
        if self.corner_radius < 0.0 or 2.0 * self.corner_radius > min(
            self.board_length, self.board_width
        ):
            raise ValueError("corner radius does not fit the cover")
        edge_x = self.board_length / 2.0
        edge_y = self.board_width / 2.0
        mount_edge_x = edge_x - self.mount_pitch_x / 2.0
        mount_edge_y = edge_y - self.mount_pitch_y / 2.0
        if min(mount_edge_x, mount_edge_y) <= self.standoff_outer_diameter / 2.0:
            raise ValueError("standoffs do not fit the cover outline")

        openings = (
            (
                self.top_fan_center_x,
                self.top_fan_center_y,
                self.top_fan_opening_length,
                self.top_fan_opening_width,
                self.top_fan_opening_corner_radius,
            ),
            (
                self.bottom_fan_center_x,
                self.bottom_fan_center_y,
                self.bottom_fan_opening_length,
                self.bottom_fan_opening_width,
                self.bottom_fan_opening_corner_radius,
            ),
            (
                self.bottom_imu_center_x,
                self.bottom_imu_center_y,
                self.bottom_imu_opening_length,
                self.bottom_imu_opening_width,
                self.bottom_imu_opening_corner_radius,
            ),
        )
        for center_x, center_y, length, width, radius in openings:
            if 2.0 * radius > min(length, width):
                raise ValueError("cover-opening corner radius does not fit")
            if abs(center_x) + length / 2.0 >= edge_x:
                raise ValueError("cover opening exceeds the cover length")
            if abs(center_y) + width / 2.0 >= edge_y:
                raise ValueError("cover opening exceeds the cover width")


def _fuse_all(shapes: Iterable[Part.Shape]) -> Part.Shape:
    """Fuse a non-empty sequence of cover-profile primitives."""

    iterator = iter(shapes)
    result = next(iterator)
    for shape in iterator:
        result = result.fuse(shape)
    return result


def _rounded_prism(
    length: float,
    width: float,
    radius: float,
    height: float,
    center_x: float,
    center_y: float,
    z0: float,
) -> Part.Shape:
    """Build a rectangular prism with four vertical rounded corners."""

    if radius == 0.0:
        return Part.makeBox(
            length,
            width,
            height,
            App.Vector(center_x - length / 2.0, center_y - width / 2.0, z0),
        )

    left = center_x - length / 2.0
    bottom = center_y - width / 2.0
    x_box = Part.makeBox(
        length - 2.0 * radius,
        width,
        height,
        App.Vector(left + radius, bottom, z0),
    )
    y_box = Part.makeBox(
        length,
        width - 2.0 * radius,
        height,
        App.Vector(left, bottom + radius, z0),
    )
    corners = (
        Part.makeCylinder(
            radius,
            height,
            App.Vector(x, y, z0),
        )
        for x in (left + radius, left + length - radius)
        for y in (bottom + radius, bottom + width - radius)
    )
    return _fuse_all((x_box, y_box, *corners))


def _rounded_plate(
    p: BoardCoverParameters,
    z0: float,
    length: float | None = None,
) -> Part.Shape:
    """Build the rounded flat blank shared by both covers."""

    return _rounded_prism(
        p.board_length if length is None else length,
        p.board_width,
        p.corner_radius,
        p.plate_thickness,
        0.0,
        0.0,
        z0,
    )


def _make_standoff_rim(
    p: BoardCoverParameters,
    z0: float,
    height: float,
) -> Part.Shape:
    """Build the continuous rectangular rim that faces the circuit board."""

    half_x = p.mount_pitch_x / 2.0 + p.standoff_outer_diameter / 2.0
    half_y = p.mount_pitch_y / 2.0 + p.standoff_outer_diameter / 2.0
    t = p.rim_thickness
    outer = Part.makeBox(2.0 * half_x, 2.0 * half_y, height, App.Vector(-half_x, -half_y, z0))
    inner = Part.makeBox(
        2.0 * (half_x - t),
        2.0 * (half_y - t),
        height,
        App.Vector(-half_x + t, -half_y + t, z0),
    )
    return outer.cut(inner).removeSplitter()


def _make_cover(
    p: BoardCoverParameters,
    z0: float,
    standoff_z0: float,
    standoff_height: float,
    rim_z0: float,
    rim_height: float,
    openings: Iterable[tuple[float, float, float, float, float]],
    plate_length: float | None = None,
    additional_hole_centers: Iterable[tuple[float, float]] = (),
) -> Part.Shape:
    """Fuse the plate, standoffs, and board-facing rim before cutting openings."""

    blank = _rounded_plate(p, z0, plate_length)
    mounting_centers = tuple(
        (x, y)
        for x in (-p.mount_pitch_x / 2.0, p.mount_pitch_x / 2.0)
        for y in (-p.mount_pitch_y / 2.0, p.mount_pitch_y / 2.0)
    )
    standoffs = tuple(
        Part.makeCylinder(
            p.standoff_outer_diameter / 2.0,
            standoff_height,
            App.Vector(x, y, standoff_z0),
        )
        for x, y in mounting_centers
    )
    rim = _make_standoff_rim(p, rim_z0, rim_height)
    solid = _fuse_all((blank, rim, *standoffs)).removeSplitter()

    cutter_z = min(z0, standoff_z0) - 0.1
    cutter_height = (
        max(z0 + p.plate_thickness, standoff_z0 + standoff_height)
        - cutter_z
        + 0.1
    )
    mounting_radius = p.mounting_hole_diameter / 2.0
    all_hole_centers = (*mounting_centers, *additional_hole_centers)
    mounting_holes = (
        Part.makeCylinder(
            mounting_radius,
            cutter_height,
            App.Vector(x, y, cutter_z),
        )
        for x, y in all_hole_centers
    )
    component_openings = tuple(
        _rounded_prism(
            length,
            width,
            radius,
            cutter_height,
            center_x,
            center_y,
            cutter_z,
        )
        for center_x, center_y, length, width, radius in openings
    )
    cutters = _fuse_all((*mounting_holes, *component_openings))
    return solid.cut(cutters).removeSplitter()


def extension_hole_centers(
    p: BoardCoverParameters,
) -> tuple[tuple[float, float], ...]:
    """Return the shared eight-hole column on each extended short edge."""

    x_offset = p.board_length / 2.0 + p.bottom_end_extension / 2.0
    return tuple(
        (x, multiplier * p.bottom_extension_hole_y_pitch)
        for x in (-x_offset, x_offset)
        for multiplier in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5)
    )


def make_top_cover(p: BoardCoverParameters) -> Part.Shape:
    """Build the upper plate on board-side collision-clearance standoffs."""

    plate_z0 = p.board_mounting_z_max + p.top_standoff_height
    return _make_cover(
        p,
        plate_z0,
        p.board_mounting_z_max,
        p.top_standoff_height,
        plate_z0 - p.top_rim_height,
        p.top_rim_height,
        (
            (
                p.top_fan_center_x,
                p.top_fan_center_y,
                p.top_fan_opening_length,
                p.top_fan_opening_width,
                p.top_fan_opening_corner_radius,
            ),
        ),
        plate_length=p.board_length + 2.0 * p.bottom_end_extension,
        additional_hole_centers=extension_hole_centers(p),
    )


def make_bottom_cover(p: BoardCoverParameters) -> Part.Shape:
    """Build the lower plate on board-side collision-clearance standoffs."""

    plate_z0 = (
        p.board_mounting_z_min
        - p.bottom_standoff_height
        - p.plate_thickness
    )
    standoff_z0 = plate_z0 + p.plate_thickness
    return _make_cover(
        p,
        plate_z0,
        standoff_z0,
        p.bottom_standoff_height,
        standoff_z0,
        p.bottom_rim_height,
        (
            (
                p.bottom_fan_center_x,
                p.bottom_fan_center_y,
                p.bottom_fan_opening_length,
                p.bottom_fan_opening_width,
                p.bottom_fan_opening_corner_radius,
            ),
            (
                p.bottom_imu_center_x,
                p.bottom_imu_center_y,
                p.bottom_imu_opening_length,
                p.bottom_imu_opening_width,
                p.bottom_imu_opening_corner_radius,
            ),
        ),
        plate_length=p.board_length + 2.0 * p.bottom_end_extension,
        additional_hole_centers=extension_hole_centers(p),
    )


def place_in_reference_coordinates(
    shape: Part.Shape, p: BoardCoverParameters
) -> Part.Shape:
    """Place a board-local cover on the extracted CAD reference axes."""

    placed = shape.copy()
    placed.Placement = App.Placement(
        App.Vector(p.reference_center_x, p.reference_center_y, 0.0),
        App.Rotation(App.Vector(0.0, 0.0, 1.0), p.reference_rotation_deg),
    )
    return placed
