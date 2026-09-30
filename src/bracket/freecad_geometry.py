"""Deterministic FreeCAD CSG builders for the two printable bracket parts."""

from dataclasses import replace

from math import cos, radians, sin, sqrt
from typing import Iterable

import FreeCAD as App
import Part

from .board_covers import BoardCoverParameters, extension_hole_centers

from .parameters import BracketParameters, derive


# The D435i visual mesh is decimated with a 0.05 mm maximum error; use that
# exact amount around each measured section envelope.  The outward +Y face is
# extended another 0.15 mm only to remove its otherwise detached R45-wall tip.
D435I_CAMERA_RELIEF_MESH_AND_MANUFACTURING_TOLERANCE_MM = 0.05
D435I_CAMERA_RELIEF_OUTWARD_Y_TERMINATION_TOLERANCE_MM = 0.15
# Measured with the deterministic official D435-derived mesh seated on the
# shelf, in Part-B-local coordinates.  Each tuple is x_min, x_max, y_min,
# y_max, z_min, z_max and is the *actual* mesh-section envelope before the
# explicit tolerance above is applied.
D435I_CAMERA_COLLISION_ENVELOPES_LOCAL_MM = (
    (-38.9001, -34.9000, 38.8499, 38.8501, 12.6676, 15.3324),
    (34.9000, 35.8000, 38.8499, 38.9833, 12.6676, 15.3324),
)

def _fuse_all(shapes: Iterable[Part.Shape]) -> Part.Shape:
    """Fuse a non-empty sequence without refining intermediate results."""

    iterator = iter(shapes)
    result = next(iterator)
    for shape in iterator:
        result = result.fuse(shape)
    return result


def rounded_box_xy(
    width: float, depth: float, height: float, radius: float, z0: float
) -> Part.Shape:
    """Return a centered XY box with vertical corner rounds and an exact Z span."""

    if min(width, depth, height) <= 0.0:
        raise ValueError("rounded-box dimensions must be positive")
    if radius < 0.0 or 2.0 * radius > min(width, depth):
        raise ValueError("rounded-box radius does not fit its footprint")
    if radius == 0.0:
        return Part.makeBox(
            width,
            depth,
            height,
            App.Vector(-width / 2.0, -depth / 2.0, z0),
        )

    center_x = Part.makeBox(
        width - 2.0 * radius,
        depth,
        height,
        App.Vector(-width / 2.0 + radius, -depth / 2.0, z0),
    )
    center_y = Part.makeBox(
        width,
        depth - 2.0 * radius,
        height,
        App.Vector(-width / 2.0, -depth / 2.0 + radius, z0),
    )
    corners = (
        Part.makeCylinder(
            radius,
            height,
            App.Vector(x, y, z0),
        )
        for x in (-width / 2.0 + radius, width / 2.0 - radius)
        for y in (-depth / 2.0 + radius, depth / 2.0 - radius)
    )
    return _fuse_all((center_x, center_y, *corners))


def _rear_relief_cutter() -> Part.Shape:
    """Build the 34 x 12 mm rear opening with R5 inner corners."""

    corner_offset = 5.0 / sqrt(2.0)

    def point(x: float, y: float) -> App.Vector:
        return App.Vector(x, y, -7.0)

    edges = (
        Part.makeLine(point(-17.0, -43.0), point(17.0, -43.0)),
        Part.makeLine(point(17.0, -43.0), point(17.0, -35.5)),
        Part.Arc(
            point(17.0, -35.5),
            point(12.0 + corner_offset, -35.5 + corner_offset),
            point(12.0, -30.5),
        ).toShape(),
        Part.makeLine(point(12.0, -30.5), point(-12.0, -30.5)),
        Part.Arc(
            point(-12.0, -30.5),
            point(-12.0 - corner_offset, -35.5 + corner_offset),
            point(-17.0, -35.5),
        ).toShape(),
        Part.makeLine(point(-17.0, -35.5), point(-17.0, -43.0)),
    )
    return Part.Face(Part.Wire(edges)).extrude(App.Vector(0.0, 0.0, 8.0))


def _d435i_camera_relief_cutters() -> Part.Shape:
    """Expand only measured D435i mesh collision envelopes by the named allowance."""

    tolerance = D435I_CAMERA_RELIEF_MESH_AND_MANUFACTURING_TOLERANCE_MM
    outward_y_tolerance = D435I_CAMERA_RELIEF_OUTWARD_Y_TERMINATION_TOLERANCE_MM
    return _fuse_all(
        Part.makeBox(
            x_max - x_min + 2.0 * tolerance,
            y_max - y_min + tolerance + outward_y_tolerance,
            z_max - z_min + 2.0 * tolerance,
            App.Vector(x_min - tolerance, y_min - tolerance, z_min - tolerance),
        )
        for x_min, x_max, y_min, y_max, z_min, z_max in (
            D435I_CAMERA_COLLISION_ENVELOPES_LOCAL_MM
        )
    )


def make_part_a(p: BracketParameters) -> Part.Shape:
    """Build printable Part A in its radar-contact-plane coordinates."""

    half_width = p.a_plate_width / 2.0
    plate = rounded_box_xy(
        p.a_plate_width,
        p.a_plate_depth,
        p.a_plate_thickness,
        4.0,
        -p.a_plate_thickness,
    )
    side_holes = (
        (p.a_pivot_y - p.lock_radius, p.a_insert_hole_depth),
        (p.a_pivot_y, p.a_insert_hole_depth),
    )
    pilot_holes: list[Part.Shape] = []
    for y, depth in side_holes:
        pilot_holes.extend(
            (
                Part.makeCylinder(
                    p.a_insert_hole_diameter / 2.0,
                    depth + 0.2,
                    App.Vector(-half_width - 0.1, y, p.a_pivot_z),
                    App.Vector(1.0, 0.0, 0.0),
                ),
                Part.makeCylinder(
                    p.a_insert_hole_diameter / 2.0,
                    depth + 0.2,
                    App.Vector(half_width + 0.1, y, p.a_pivot_z),
                    App.Vector(-1.0, 0.0, 0.0),
                ),
            )
        )

    solid = plate
    vent = rounded_box_xy(32.0, 20.0, 8.0, 4.0, -7.0)
    mount_holes = (
        Part.makeCylinder(
            p.sensor_mount_hole_diameter / 2.0,
            8.0,
            App.Vector(x, y, -7.0),
        )
        for x in (-p.sensor_mount_pitch_x / 2.0, p.sensor_mount_pitch_x / 2.0)
        for y in (-p.sensor_mount_pitch_y / 2.0, p.sensor_mount_pitch_y / 2.0)
    )
    cutters = _fuse_all((vent, _rear_relief_cutter(), *mount_holes, *pilot_holes))
    return solid.cut(cutters).removeSplitter()


def _root_rib(
    p: BracketParameters, outer_x: float, outward: float, y_center: float
) -> Part.Shape:
    """Build one compact external triangular sector-wall root rib."""

    outer_foot_x = outer_x + outward * p.root_rib_extension
    y0 = y_center - p.root_rib_depth / 2.0

    def point(x: float, z: float) -> App.Vector:
        return App.Vector(x, y0, z)

    wire = Part.makePolygon(
        (
            point(outer_x, p.b_base_thickness),
            point(outer_foot_x, p.b_base_thickness),
            point(outer_x, p.b_base_thickness + p.root_rib_height),
            point(outer_x, p.b_base_thickness),
        )
    )
    return Part.Face(wire).extrude(App.Vector(0.0, p.root_rib_depth, 0.0))


def _sector_point(
    p: BracketParameters, radius: float, angle_deg: float, x: float
) -> App.Vector:
    angle = radians(angle_deg)
    return App.Vector(
        x,
        p.b_pivot_y - radius * cos(angle),
        p.b_base_thickness + p.pivot_z_above_base + radius * sin(angle),
    )


def _annular_sector_prism(
    p: BracketParameters,
    inner_radius: float,
    outer_radius: float,
    start_angle: float,
    end_angle: float,
    x0: float,
    thickness: float,
) -> Part.Shape:
    """Build a YZ annular-sector prism along +X."""

    middle_angle = (start_angle + end_angle) / 2.0
    outer_start = _sector_point(p, outer_radius, start_angle, x0)
    outer_end = _sector_point(p, outer_radius, end_angle, x0)
    inner_start = _sector_point(p, inner_radius, start_angle, x0)
    inner_end = _sector_point(p, inner_radius, end_angle, x0)
    edges = (
        Part.Arc(
            outer_start,
            _sector_point(p, outer_radius, middle_angle, x0),
            outer_end,
        ).toShape(),
        Part.makeLine(outer_end, inner_end),
        Part.Arc(
            inner_end,
            _sector_point(p, inner_radius, middle_angle, x0),
            inner_start,
        ).toShape(),
        Part.makeLine(inner_start, outer_start),
    )
    return Part.Face(Part.Wire(edges)).extrude(App.Vector(thickness, 0.0, 0.0))


def make_sector_wall(p: BracketParameters, x0: float) -> Part.Shape:
    """Build one solid sector ear with an inset pivot and outer rail recess."""

    dimensions = derive(p)
    start_angle = -dimensions.sector_profile_extension_deg
    end_angle = p.working_angle_deg + dimensions.sector_profile_extension_deg
    middle_angle = (start_angle + end_angle) / 2.0
    center = App.Vector(
        x0,
        p.b_pivot_y,
        p.b_base_thickness + p.pivot_z_above_base,
    )
    start = _sector_point(p, p.sector_outer_radius, start_angle, x0)
    middle = _sector_point(p, p.sector_outer_radius, middle_angle, x0)
    end = _sector_point(p, p.sector_outer_radius, end_angle, x0)
    sector = Part.Face(
        Part.Wire(
            (
                Part.makeLine(center, start),
                Part.Arc(start, middle, end).toShape(),
                Part.makeLine(end, center),
            )
        )
    ).extrude(App.Vector(p.b_wall_thickness, 0.0, 0.0))
    lower_web = Part.makeBox(
        p.b_wall_thickness,
        p.sector_outer_radius,
        p.pivot_z_above_base,
        App.Vector(
            x0,
            p.b_pivot_y - p.sector_outer_radius,
            p.b_base_thickness,
        ),
    )
    pivot_lobe = Part.makeCylinder(
        p.sector_pivot_lobe_radius,
        p.b_wall_thickness,
        center,
        App.Vector(1.0, 0.0, 0.0),
    )
    wall = _fuse_all((sector, lower_web, pivot_lobe))

    slot_start = -dimensions.slot_overrun_deg
    slot_end = p.working_angle_deg + dimensions.slot_overrun_deg
    is_left_wall = x0 < 0.0
    recess_x = (
        x0
        if is_left_wall
        else x0 + p.b_wall_thickness - p.track_recess_depth
    )
    rail_recess = _annular_sector_prism(
        p,
        p.lock_radius - 6.0,
        p.sector_outer_radius + 0.1,
        slot_start,
        slot_end,
        recess_x,
        p.track_recess_depth,
    )
    return wall.cut(rail_recess).removeSplitter()


def make_arc_slot_cutter(p: BracketParameters) -> Part.Shape:
    """Build the annular arc slot with circular end caps."""

    overrun = derive(p).slot_overrun_deg
    start_angle = -overrun
    end_angle = p.working_angle_deg + overrun
    middle_angle = (start_angle + end_angle) / 2.0
    half_width = p.slot_width / 2.0
    inner_radius = p.lock_radius - half_width
    outer_radius = p.lock_radius + half_width

    wall_outer = p.b_inner_width / 2.0 + p.b_wall_thickness
    x0 = -wall_outer - 1.0
    length = 2.0 * (wall_outer + 1.0)
    outer_start = _sector_point(p, outer_radius, start_angle, x0)
    inner_start = _sector_point(p, inner_radius, start_angle, x0)
    outer_end = _sector_point(p, outer_radius, end_angle, x0)
    inner_end = _sector_point(p, inner_radius, end_angle, x0)
    edges = (
        Part.Arc(
            outer_start,
            _sector_point(p, outer_radius, middle_angle, x0),
            outer_end,
        ).toShape(),
        Part.makeLine(outer_end, inner_end),
        Part.Arc(
            inner_end,
            _sector_point(p, inner_radius, middle_angle, x0),
            inner_start,
        ).toShape(),
        Part.makeLine(inner_start, outer_start),
    )
    annular_path = Part.Face(Part.Wire(edges)).extrude(App.Vector(length, 0.0, 0.0))
    caps = (
        Part.makeCylinder(
            half_width,
            length,
            _sector_point(p, p.lock_radius, angle, x0),
            App.Vector(1.0, 0.0, 0.0),
        )
        for angle in (start_angle, end_angle)
    )
    return _fuse_all((annular_path, *caps)).removeSplitter()


def make_part_b(
    p: BracketParameters, rib_y_center: float | None = None
) -> Part.Shape:
    """Build printable Part B with a compact base and outer sector plates."""

    base = rounded_box_xy(
        p.b_base_width,
        p.b_base_depth,
        p.b_base_thickness,
        4.0,
        0.0,
    )
    shelf = rounded_box_xy(
        p.d435i_shelf_width,
        p.d435i_shelf_depth,
        p.b_base_thickness,
        p.d435i_shelf_corner_radius,
        0.0,
    )
    shelf.Placement = App.Placement(
        App.Vector(0.0, p.b_base_depth / 2.0 + p.d435i_shelf_depth / 2.0, 0.0),
        App.Rotation(),
    )
    # Keep the ordinary exterior R4 profile at the front of the D435i shelf,
    # but make its rear side continuous before blending into the wider base.
    shelf_rear_y = p.b_base_depth / 2.0
    shelf_radius = p.d435i_shelf_corner_radius
    shelf_half_width = p.d435i_shelf_width / 2.0
    rear_shelf_fill = Part.makeBox(
        p.d435i_shelf_width,
        shelf_radius,
        p.b_base_thickness,
        App.Vector(-shelf_half_width, shelf_rear_y, 0.0),
    )
    # At each rear reentrant corner, retain the connection square outside its
    # R4 quadrant.  The arc is tangent to the base front and shelf side, so
    # this adds a concave transition instead of an exterior shelf round.
    rear_shelf_blends = tuple(
        Part.makeBox(
            shelf_radius,
            shelf_radius,
            p.b_base_thickness,
            App.Vector(
                shelf_half_width if side > 0.0 else -shelf_half_width - shelf_radius,
                shelf_rear_y,
                0.0,
            ),
        ).cut(
            Part.makeCylinder(
                shelf_radius,
                p.b_base_thickness,
                App.Vector(
                    side * (shelf_half_width + shelf_radius),
                    shelf_rear_y + shelf_radius,
                    0.0,
                ),
            )
        )
        for side in (-1.0, 1.0)
    )
    half_inner = p.b_inner_width / 2.0
    left_x = -half_inner - p.b_wall_thickness
    right_x = half_inner
    left_wall = make_sector_wall(p, left_x)
    right_wall = make_sector_wall(p, right_x)
    outer_x = half_inner + p.b_wall_thickness
    rib_y = (
        p.root_rib_y_center
        if rib_y_center is None
        else rib_y_center
    )
    ribs = tuple(
        _root_rib(p, side * outer_x, side, y_center)
        for side in (-1.0, 1.0)
        for y_center in (-rib_y, rib_y)
    )
    solid = _fuse_all(
        (
            base,
            shelf,
            rear_shelf_fill,
            *rear_shelf_blends,
            left_wall,
            right_wall,
            *ribs,
        )
    )

    hole_x0 = -outer_x - 1.0
    hole_length = 2.0 * (outer_x + 1.0)
    pivot_hole = Part.makeCylinder(
        p.b_clearance_hole_diameter / 2.0,
        hole_length,
        App.Vector(
            hole_x0,
            p.b_pivot_y,
            p.b_base_thickness + p.pivot_z_above_base,
        ),
        App.Vector(1.0, 0.0, 0.0),
    )
    d435i_hole = Part.makeCylinder(
        p.d435i_mount_clearance_diameter / 2.0,
        p.b_base_thickness + 0.2,
        App.Vector(
            0.0,
            p.b_base_depth / 2.0 + p.d435i_shelf_depth / 2.0,
            -0.1,
        ),
    )
    # Rounded rectangular opening over the board's upper fan/heatsink, sized to
    # stop short of both sector ears so each keeps a full seat on the plate.
    fan_opening = rounded_box_xy(
        p.b_fan_opening_length,
        p.b_fan_opening_width,
        p.b_base_thickness + 0.2,
        p.b_fan_opening_corner_radius,
        -0.1,
    )
    fan_opening.Placement = App.Placement(
        App.Vector(p.b_fan_center_x, p.b_fan_center_y, 0.0), App.Rotation()
    )
    # Only the mesh-section envelopes of the two rear lower camera corners
    # are opened.  This retains the R45 wall everywhere outside those bands.
    d435i_camera_reliefs = _d435i_camera_relief_cutters()
    cutters = (
        pivot_hole.fuse(make_arc_slot_cutter(p))
        .fuse(d435i_hole)
        .fuse(fan_opening)
        .fuse(d435i_camera_reliefs)
    )
    return solid.cut(cutters).removeSplitter()


def make_board_mounted_part_b(
    p: BracketParameters | None = None,
) -> Part.Shape:
    """Build Part B on the UAV V3 top-cover M3 mounting pattern."""

    mounted = replace(
        p or BracketParameters(),
        b_base_width=128.0,
        b_base_depth=78.0,
    )
    solid = make_part_b(mounted)
    holes = _fuse_all(
        Part.makeCylinder(
            mounted.b_base_mount_hole_diameter / 2.0,
            mounted.b_base_thickness + 0.2,
            App.Vector(x, y, -0.1),
        )
        for x, y in extension_hole_centers(BoardCoverParameters())
    )
    return solid.cut(holes).removeSplitter()
