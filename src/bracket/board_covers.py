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
    # Downward guard under the top cover's rear (-Y) rim protecting the two
    # USB Type-C shells measured on the carrier CAD (local x 22.6..44.2 mm,
    # shells ~26.25 tall there).  usbc_guard_bottom_z keeps the deepened wall
    # 1 mm above the shells so it shields without touching.
    usbc_guard_enabled: bool = True
    usbc_guard_x0: float = 21.0
    usbc_guard_x1: float = 46.0
    usbc_guard_bottom_z: float = 27.3
    # Deepening for the rest of the top-cover rim, one value per side, each
    # roughly 1 mm above the tallest carrier feature measured under that rim
    # wall.  A side whose value is not below the plain rim bottom (front +Y,
    # 29.33) gets no extra guard: the existing rim is already as close as the
    # 1 mm rule allows there.
    rim_guard_enabled: bool = True
    rim_guard_neg_y_bottom_z: float = 28.7  # rear -Y, excluding the USB span
    rim_guard_pos_y_bottom_z: float = 29.33  # front +Y (blocked by a tall part)
    rim_guard_neg_x_bottom_z: float = 28.5  # -X short edge
    rim_guard_pos_x_bottom_z: float = 28.7  # +X short edge
    # The bottom cover's rim faces up toward the board, so its guards grow
    # upward instead.  Each value is the raised wall top, 1 mm below the
    # lowest carrier feature measured under that wall (mostly the board
    # underside at ~10.45; the -X short edge has an under-hang down to 5.45).
    bottom_rim_guard_enabled: bool = True
    bottom_rim_guard_neg_y_top_z: float = 9.45  # -Y rear
    bottom_rim_guard_pos_y_top_z: float = 9.45  # +Y front
    bottom_rim_guard_neg_x_top_z: float = 9.45  # -X short edge
    bottom_rim_guard_pos_x_top_z: float = 9.45  # +X short edge
    # Leave a local gap in the raised -X wall so the board's short-edge
    # interface stays exposed instead of capping the whole -X wall at the
    # interface height.  The interface (local x ~ -57..-50) hangs to z 5.45
    # across y ~ -1..+5; inside the y band the wall is raised only to
    # bottom_rim_guard_neg_x_gap_top_z (just below the interface), while the
    # rest of the -X wall rises to bottom_rim_guard_neg_x_top_z.
    bottom_rim_guard_neg_x_gap_enabled: bool = True
    bottom_rim_guard_neg_x_gap_y0: float = -3.5
    bottom_rim_guard_neg_x_gap_y1: float = 7.0
    bottom_rim_guard_neg_x_gap_top_z: float = 5.45
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
                self.usbc_guard_x0,
                self.usbc_guard_x1,
                self.usbc_guard_bottom_z,
                self.rim_guard_neg_y_bottom_z,
                self.rim_guard_pos_y_bottom_z,
                self.rim_guard_neg_x_bottom_z,
                self.rim_guard_pos_x_bottom_z,
                self.bottom_rim_guard_neg_y_top_z,
                self.bottom_rim_guard_pos_y_top_z,
                self.bottom_rim_guard_neg_x_top_z,
                self.bottom_rim_guard_pos_x_top_z,
                self.bottom_rim_guard_neg_x_gap_y0,
                self.bottom_rim_guard_neg_x_gap_y1,
                self.bottom_rim_guard_neg_x_gap_top_z,
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

        if self.usbc_guard_enabled:
            plate_z0 = self.board_mounting_z_max + self.top_standoff_height
            if not (
                -edge_x <= self.usbc_guard_x0 < self.usbc_guard_x1 <= edge_x
            ):
                raise ValueError("USB-C guard span must sit on the board edge")
            if self.usbc_guard_bottom_z >= plate_z0:
                raise ValueError("USB-C guard must hang below the upper plate")
            if self.usbc_guard_bottom_z <= self.board_mounting_z_max + 0.5:
                raise ValueError(
                    "USB-C guard bottom must stay clear of the board top"
                )
        if self.rim_guard_enabled:
            plate_z0 = self.board_mounting_z_max + self.top_standoff_height
            for label, value in (
                ("rear -Y", self.rim_guard_neg_y_bottom_z),
                ("front +Y", self.rim_guard_pos_y_bottom_z),
                ("-X", self.rim_guard_neg_x_bottom_z),
                ("+X", self.rim_guard_pos_x_bottom_z),
            ):
                if not (
                    self.board_mounting_z_max + 0.5
                    < value
                    < plate_z0
                ):
                    raise ValueError(
                        f"rim guard bottom on {label} must clear the board "
                        "yet stay under the plate"
                    )
        if self.bottom_rim_guard_enabled:
            rim_top = (
                self.board_mounting_z_min
                - self.bottom_standoff_height
                + self.bottom_rim_height
            )
            half_y = self.mount_pitch_y / 2.0 + self.standoff_outer_diameter / 2.0
            inner_half_y = half_y - self.rim_thickness
            for label, value in (
                ("rear -Y", self.bottom_rim_guard_neg_y_top_z),
                ("front +Y", self.bottom_rim_guard_pos_y_top_z),
                ("-X", self.bottom_rim_guard_neg_x_top_z),
                ("+X", self.bottom_rim_guard_pos_x_top_z),
            ):
                if not (rim_top < value < self.board_mounting_z_min):
                    raise ValueError(
                        f"bottom rim guard top on {label} must rise above the "
                        "plain rim yet stay below the board underside"
                    )
            if self.bottom_rim_guard_neg_x_gap_enabled and not (
                -inner_half_y
                <= self.bottom_rim_guard_neg_x_gap_y0
                < self.bottom_rim_guard_neg_x_gap_y1
                <= inner_half_y
            ):
                raise ValueError(
                    "bottom -X rim gap must sit within the -X wall span"
                )
            if self.bottom_rim_guard_neg_x_gap_enabled and not (
                rim_top
                < self.bottom_rim_guard_neg_x_gap_top_z
                < self.bottom_rim_guard_neg_x_top_z
            ):
                raise ValueError(
                    "bottom -X rim gap wall must be shorter than the full wall"
                )


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
    extras: Iterable[Part.Shape] = (),
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
    solid = _fuse_all((blank, rim, *standoffs, *extras)).removeSplitter()

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


def _top_cover_guards(p: BoardCoverParameters) -> tuple[Part.Shape, ...]:
    """Deepened rim walls that guard the board's edge connectors.

    Each guard is a downward extension of a side of the existing rim wall,
    cut to stop 1 mm above the tallest carrier feature measured under that
    wall (values live in the ``rim_guard_*`` and ``usbc_guard_*`` fields).
    A side whose guard bottom would not go below the plain rim bottom (the
    front +Y) simply contributes nothing, because the plain rim is already
    as deep as the 1 mm rule allows there.
    """

    plate_z0 = p.board_mounting_z_max + p.top_standoff_height
    rim_z0 = plate_z0 - p.top_rim_height
    half_x = p.mount_pitch_x / 2.0 + p.standoff_outer_diameter / 2.0
    half_y = p.mount_pitch_y / 2.0 + p.standoff_outer_diameter / 2.0
    thickness = p.rim_thickness
    guards: list[Part.Shape] = []

    def add(x0: float, y0: float, length_x: float, length_y: float,
            bottom_z: float) -> None:
        if bottom_z >= rim_z0:
            return
        guards.append(
            Part.makeBox(
                length_x,
                length_y,
                plate_z0 - bottom_z,
                App.Vector(x0, y0, bottom_z),
            )
        )

    if p.usbc_guard_enabled and p.usbc_guard_bottom_z < rim_z0:
        # Rear -Y, the two USB Type-C shells (x 21..46): deepest guard.
        add(
            p.usbc_guard_x0,
            -half_y,
            p.usbc_guard_x1 - p.usbc_guard_x0,
            thickness,
            p.usbc_guard_bottom_z,
        )
    if p.rim_guard_enabled:
        # Rear -Y wall, whole side.
        add(-half_x, -half_y, 2.0 * half_x, thickness,
            p.rim_guard_neg_y_bottom_z)
        # Front +Y wall, whole side (skipped: already near the tall part).
        add(-half_x, half_y - thickness, 2.0 * half_x, thickness,
            p.rim_guard_pos_y_bottom_z)
        # Left and right short-edge walls.
        add(-half_x, -(half_y - thickness), thickness,
            2.0 * (half_y - thickness), p.rim_guard_neg_x_bottom_z)
        add(half_x - thickness, -(half_y - thickness), thickness,
            2.0 * (half_y - thickness), p.rim_guard_pos_x_bottom_z)
    return tuple(guards)


def make_top_cover(p: BoardCoverParameters) -> Part.Shape:
    """Build the upper plate on board-side collision-clearance standoffs."""

    plate_z0 = p.board_mounting_z_max + p.top_standoff_height
    extras = _top_cover_guards(p)
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
        extras=extras,
    )


def _bottom_cover_guards(p: BoardCoverParameters) -> tuple[Part.Shape, ...]:
    """Raised rim walls on the lower cover that shield the board underside.

    The bottom rim faces up toward the board, so its guard walls grow from the
    plain rim crest upward to one value per side.  Each value keeps ~1 mm
    below the lowest carrier feature measured under that wall (the values live
    in the ``bottom_rim_guard_*`` fields).  A side whose value is not above
    the plain rim crest contributes nothing.
    """

    plate_top = p.board_mounting_z_min - p.bottom_standoff_height
    rim_top = plate_top + p.bottom_rim_height
    half_x = p.mount_pitch_x / 2.0 + p.standoff_outer_diameter / 2.0
    half_y = p.mount_pitch_y / 2.0 + p.standoff_outer_diameter / 2.0
    thickness = p.rim_thickness
    guards: list[Part.Shape] = []

    def add(x0: float, y0: float, length_x: float, length_y: float,
            top_z: float) -> None:
        if top_z <= rim_top:
            return
        guards.append(
            Part.makeBox(
                length_x,
                length_y,
                top_z - rim_top,
                App.Vector(x0, y0, rim_top),
            )
        )

    if not p.bottom_rim_guard_enabled:
        return ()
    add(-half_x, -half_y, 2.0 * half_x, thickness,
        p.bottom_rim_guard_neg_y_top_z)
    add(-half_x, half_y - thickness, 2.0 * half_x, thickness,
        p.bottom_rim_guard_pos_y_top_z)
    inner_half_y = half_y - thickness
    if p.bottom_rim_guard_neg_x_gap_enabled:
        # Whole -X wall rises to the full crest; inside the gap band it only
        # rises to gap_top_z, leaving the interface exposed above that wall.
        gap_y0 = p.bottom_rim_guard_neg_x_gap_y0
        gap_y1 = p.bottom_rim_guard_neg_x_gap_y1
        if -inner_half_y < gap_y0:
            add(-half_x, -inner_half_y, thickness, gap_y0 - (-inner_half_y),
                p.bottom_rim_guard_neg_x_top_z)
        add(-half_x, gap_y0, thickness, gap_y1 - gap_y0,
            p.bottom_rim_guard_neg_x_gap_top_z)
        if gap_y1 < inner_half_y:
            add(-half_x, gap_y1, thickness, inner_half_y - gap_y1,
                p.bottom_rim_guard_neg_x_top_z)
    else:
        add(-half_x, -inner_half_y, thickness, 2.0 * inner_half_y,
            p.bottom_rim_guard_neg_x_top_z)
    add(half_x - thickness, -inner_half_y, thickness, 2.0 * inner_half_y,
        p.bottom_rim_guard_pos_x_top_z)
    return tuple(guards)


def make_bottom_cover(p: BoardCoverParameters) -> Part.Shape:
    """Build the lower plate on board-side collision-clearance standoffs."""

    plate_z0 = (
        p.board_mounting_z_min
        - p.bottom_standoff_height
        - p.plate_thickness
    )
    standoff_z0 = plate_z0 + p.plate_thickness
    cover = _make_cover(
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
        extras=_bottom_cover_guards(p),
    )
    return cover


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
