"""Parametric hollow cylindrical standing grip for the UAV V3 lower cover.

The part keeps the battery grip's mounting flange (128 x 78 mm, R4, 6 mm,
sixteen M3 through-holes matching the lower cover extension columns plus four
Ø6.5 board-screw clearances).  Below the flange a short shoulder steps into a
straight hollow cylinder whose outside diameter suits one-hand holding, and
the cylinder flares smoothly into a rectangular foot so the rig can stand on
a table.  There is no battery cavity: the inner bore is open and empty.

Dimensions are in millimetres in the board-local frame used by
:mod:`bracket.board_covers`, where the lower cover underside sits at
Z = -5.5.
"""

from dataclasses import dataclass
from math import cos, isfinite, radians, sin

if False:  # pragma: no cover - type checkers only
    import Part


@dataclass(frozen=True)
class StandingHandleParameters:
    """Source dimensions for the cylindrical standing grip, in millimetres."""

    # Flange: identical to the battery grip's mounting flange / lower cover.
    flange_length: float = 128.0
    flange_width: float = 78.0
    flange_corner_radius: float = 4.0
    flange_thickness: float = 6.0
    cover_underside_z: float = -5.5
    mount_x: float = 59.0
    mount_y_pitch: float = 10.0
    mount_hole_diameter: float = 3.4
    board_screw_x: float = 50.0
    board_screw_y: float = 35.0
    board_screw_clearance_diameter: float = 6.5

    # Short shoulder from the flange rectangle down to the cylinder.  The loft
    # starts from an inset outline that keeps both the outer screw ring and the
    # four inner board-screw clearances clear: the flange stays flat and open
    # under every hole, so nuts seat flat instead of riding a tapered cone.
    shoulder_height: float = 6.0
    shoulder_top_length: float = 88.0
    shoulder_top_width: float = 58.0
    shoulder_top_corner_radius: float = 15.0

    # Hollow one-hand cylinder (outer grip diameter and wall).
    grip_outer_diameter: float = 42.0
    wall_thickness: float = 3.5
    grip_length: float = 88.0

    # Smooth flare from the cylinder into the rectangular foot.
    base_blend_height: float = 12.0
    base_plate_length: float = 104.0
    base_plate_width: float = 88.0
    base_plate_corner_radius: float = 24.0
    base_thickness: float = 6.0
    # Sighting hole through the foot's front (+Y) side, clear of the grip so
    # the target can be seen from the side.
    base_sight_hole_diameter: float = 5.0
    base_sight_edge_clearance: float = 10.0

    @property
    def grip_inner_diameter(self) -> float:
        return self.grip_outer_diameter - 2.0 * self.wall_thickness

    @property
    def flange_z0(self) -> float:
        return self.cover_underside_z - self.flange_thickness

    @property
    def shoulder_z0(self) -> float:
        return self.flange_z0 - self.shoulder_height

    @property
    def grip_z0(self) -> float:
        return self.shoulder_z0 - self.grip_length

    @property
    def base_top_z(self) -> float:
        return self.grip_z0 - self.base_blend_height

    @property
    def base_z0(self) -> float:
        return self.base_top_z - self.base_thickness

    @property
    def total_height(self) -> float:
        return self.cover_underside_z - self.base_z0

    def __post_init__(self) -> None:
        positive = (
            self.flange_length,
            self.flange_width,
            self.flange_thickness,
            self.mount_x,
            self.mount_y_pitch,
            self.mount_hole_diameter,
            self.board_screw_x,
            self.board_screw_y,
            self.board_screw_clearance_diameter,
            self.shoulder_height,
            self.shoulder_top_length,
            self.shoulder_top_width,
            self.shoulder_top_corner_radius,
            self.grip_outer_diameter,
            self.wall_thickness,
            self.grip_length,
            self.base_blend_height,
            self.base_plate_length,
            self.base_plate_width,
            self.base_plate_corner_radius,
            self.base_thickness,
            self.base_sight_hole_diameter,
            self.base_sight_edge_clearance,
        )
        if not all(isfinite(value) and value > 0.0 for value in positive):
            raise ValueError("standing-handle dimensions must be finite and positive")
        if not isfinite(self.cover_underside_z):
            raise ValueError("the cover underside plane must be finite")
        if 2.0 * self.flange_corner_radius > min(
            self.flange_length, self.flange_width
        ):
            raise ValueError("flange corner radius does not fit its outline")
        if 2.0 * self.base_plate_corner_radius > min(
            self.base_plate_length, self.base_plate_width
        ):
            raise ValueError("base corner radius does not fit its outline")
        if 2.0 * self.shoulder_top_corner_radius > min(
            self.shoulder_top_length, self.shoulder_top_width
        ):
            raise ValueError("shoulder top corner radius does not fit")
        if self.shoulder_top_length / 2.0 > (
            self.mount_x - self.mount_hole_diameter / 2.0 - 1.5
        ):
            raise ValueError("shoulder top must leave the mount columns clear")
        if self.shoulder_top_length / 2.0 > (
            self.board_screw_x - self.board_screw_clearance_diameter / 2.0 - 1.5
        ) or self.shoulder_top_width / 2.0 > (
            self.board_screw_y - self.board_screw_clearance_diameter / 2.0 - 1.5
        ):
            raise ValueError("shoulder top must leave the board-screw holes clear")
        if self.wall_thickness >= self.grip_outer_diameter / 2.0:
            raise ValueError("wall thickness must leave an inner bore")
        if self.grip_outer_diameter >= min(self.flange_length, self.flange_width):
            raise ValueError("the cylinder leaves the flange outline")
        # The cylinder and its inner bore stay clear of mount columns and of
        # the board-screw clearances in the flange.
        if self.grip_outer_diameter / 2.0 >= self.board_screw_y:
            raise ValueError("the cylinder would touch the board-screw clearances")
        if self.grip_outer_diameter / 2.0 >= self.mount_x:
            raise ValueError("the cylinder would touch the mount columns")
        sight_y = self.base_plate_width / 2.0 - self.base_sight_edge_clearance
        if sight_y <= self.grip_outer_diameter / 2.0 + 2.0:
            raise ValueError("sight hole must sit outside the grip")
        if self.base_sight_edge_clearance <= (
            self.base_sight_hole_diameter / 2.0 + 2.0
        ):
            raise ValueError("sight hole must stay inside the foot")


def mount_hole_centers(
    p: StandingHandleParameters,
) -> tuple[tuple[float, float], ...]:
    """Return the sixteen flange axes, matching the cover extension columns."""

    return tuple(
        (x, multiplier * p.mount_y_pitch)
        for x in (-p.mount_x, p.mount_x)
        for multiplier in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5)
    )


def board_screw_centers(
    p: StandingHandleParameters,
) -> tuple[tuple[float, float], ...]:
    """Return the four board-mounting screw axes the flange must pass."""

    return tuple(
        (x, y)
        for x in (-p.board_screw_x, p.board_screw_x)
        for y in (-p.board_screw_y, p.board_screw_y)
    )


def _rounded_rect_wire(
    length: float,
    width: float,
    radius: float,
    z: float,
) -> "Part.Shape":
    """Return a closed rounded-rectangle wire (4 lines + 4 arcs) at plane z."""

    import FreeCAD as App
    import Part

    a = length / 2.0
    b = width / 2.0
    cc = a - radius
    dd = b - radius

    def arc_edge(cx: float, cy: float, start_deg: float, mid_deg: float,
                 end_deg: float) -> "Part.Shape":
        def pt(angle_deg: float):
            angle = radians(angle_deg)
            return App.Vector(
                cx + radius * cos(angle),
                cy + radius * sin(angle),
                z,
            )
        return Part.Arc(pt(start_deg), pt(mid_deg), pt(end_deg)).toShape()

    edges = []
    edges.append(Part.makeLine(App.Vector(-cc, -b, z), App.Vector(cc, -b, z)))
    edges.append(arc_edge(cc, -dd, -90.0, -45.0, 0.0))
    edges.append(Part.makeLine(App.Vector(a, -dd, z), App.Vector(a, dd, z)))
    edges.append(arc_edge(cc, dd, 0.0, 45.0, 90.0))
    edges.append(Part.makeLine(App.Vector(cc, b, z), App.Vector(-cc, b, z)))
    edges.append(arc_edge(-cc, dd, 90.0, 135.0, 180.0))
    edges.append(Part.makeLine(App.Vector(-a, dd, z), App.Vector(-a, -dd, z)))
    edges.append(arc_edge(-cc, -dd, 180.0, 225.0, 270.0))
    return Part.Wire(edges)


def _circle_wire(p: StandingHandleParameters, diameter: float, z: float) -> "Part.Shape":
    """Return a closed circular wire (4 quarter arcs) at plane z."""

    import FreeCAD as App
    import Part

    radius = diameter / 2.0
    edges = []
    for k in range(4):
        start = radians(90.0 * k)
        mid = radians(90.0 * k + 45.0)
        end = radians(90.0 * (k + 1))
        points = tuple(
            App.Vector(radius * cos(angle), radius * sin(angle), z)
            for angle in (start, mid, end)
        )
        edges.append(Part.Arc(*points).toShape())
    return Part.Wire(edges)


def _rounded_prism(
    length: float,
    width: float,
    radius: float,
    height: float,
    z0: float,
) -> "Part.Shape":
    """Build a rectangular prism with four vertical rounded corners."""

    import FreeCAD as App
    import Part

    left = -length / 2.0
    bottom = -width / 2.0
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
    corners = tuple(
        Part.makeCylinder(radius, height, App.Vector(x, y, z0))
        for x in (left + radius, left + length - radius)
        for y in (bottom + radius, bottom + width - radius)
    )
    fused = x_box.fuse(y_box)
    for corner in corners:
        fused = fused.fuse(corner)
    return fused.removeSplitter()


def _flange_solid(p: StandingHandleParameters) -> "Part.Shape":
    return _rounded_prism(
        p.flange_length,
        p.flange_width,
        p.flange_corner_radius,
        p.flange_thickness,
        p.flange_z0,
    )


def make_standing_handle(p: StandingHandleParameters | None = None) -> "Part.Shape":
    """Build the one-piece standing grip: flange, cylinder, hollow bore, foot."""

    import FreeCAD as App
    import Part

    params = p or StandingHandleParameters()

    # Separate lofts keep identical transition topology; fusing the parts
    # afterwards is far more robust than one mixed 8/4/4/8-edge loft.
    shoulder = Part.makeLoft(
        [
            _rounded_rect_wire(
                params.shoulder_top_length,
                params.shoulder_top_width,
                params.shoulder_top_corner_radius,
                params.flange_z0,
            ),
            _circle_wire(params, params.grip_outer_diameter, params.shoulder_z0),
        ],
        True,
    ).removeSplitter()

    cylinder = Part.makeCylinder(
        params.grip_outer_diameter / 2.0,
        params.grip_length,
        App.Vector(0.0, 0.0, params.shoulder_z0),
        App.Vector(0.0, 0.0, -1.0),
    )

    base_flare = Part.makeLoft(
        [
            _circle_wire(params, params.grip_outer_diameter, params.grip_z0),
            _rounded_rect_wire(
                params.base_plate_length,
                params.base_plate_width,
                params.base_plate_corner_radius,
                params.base_top_z,
            ),
        ],
        True,
    ).removeSplitter()

    flange = _flange_solid(params)
    base = _rounded_prism(
        params.base_plate_length,
        params.base_plate_width,
        params.base_plate_corner_radius,
        params.base_thickness,
        params.base_z0,
    )

    solid = flange
    for piece in (shoulder, cylinder, base_flare, base):
        solid = solid.fuse(piece).removeSplitter()

    down = App.Vector(0.0, 0.0, -1.0)

    # Sixteen Ø3.4 mount holes and four Ø6.5 clearances through the flange.
    mount_cylinders = tuple(
        Part.makeCylinder(
            params.mount_hole_diameter / 2.0,
            params.flange_thickness + 0.2,
            App.Vector(x, y, params.cover_underside_z + 0.1),
            down,
        )
        for x, y in mount_hole_centers(params)
    )
    board_screw_holes = tuple(
        Part.makeCylinder(
            params.board_screw_clearance_diameter / 2.0,
            params.flange_thickness + 0.2,
            App.Vector(x, y, params.cover_underside_z + 0.1),
            down,
        )
        for x, y in board_screw_centers(params)
    )
    # Central sight hole through the foot, on the bore axis.
    sight_y = params.base_plate_width / 2.0 - params.base_sight_edge_clearance
    base_hole = Part.makeCylinder(
        params.base_sight_hole_diameter / 2.0,
        params.grip_z0 - (params.base_z0 - 0.1),
        App.Vector(0.0, sight_y, params.base_z0 - 0.1),
    )
    # Central hollow bore: through the flange, shoulder, cylinder, and flare,
    # stopping just inside the top of the solid foot.
    inner_bore = Part.makeCylinder(
        params.grip_inner_diameter / 2.0,
        (params.cover_underside_z - params.base_top_z) + 0.2,
        App.Vector(0.0, 0.0, params.cover_underside_z + 0.1),
        down,
    )

    cutters = (*mount_cylinders, *board_screw_holes, base_hole, inner_bore)
    fused_cutters = cutters[0]
    for cutter in cutters[1:]:
        fused_cutters = fused_cutters.fuse(cutter)
    return solid.cut(fused_cutters).removeSplitter()
