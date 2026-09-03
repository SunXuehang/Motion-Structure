"""Parametric hollow cylindrical battery grip under the UAV V3 lower cover.

The grip is a printable PLA tube hanging from a flange that reproduces the
lower cover's 128 x 78 mm outline.  The flange bolts flat against the cover
underside through all sixteen of the cover's side-extension holes, eight per
side at X = +/-59 mm.  Each M3 passes through a matching Ø3.4 hole in the
flange and is locked by a nut under the flange -- the flange is never tapped.

The tube's bore runs straight through the flange: the handle has no top lid
of its own, so the lower cover closes the battery cavity and the board's
bottom fan exhausts straight down into the bore, over the pack.  The bore
holds one solid prismatic battery pack whose footprint is an equilateral
triangle with a 36 mm side; the pack loads from the open bottom, seats on
three cap-screw posts fused into the bore wall, and is closed by a cap
screwed into those posts.  A small window in the tube's rear (-Y) wall
passes the two DC 12 V leads (supply and charging).

Every dimension is in millimetres, in the same board-local frame as
:mod:`bracket.board_covers`, where the lower cover underside sits at
Z = -5.5.
"""

from dataclasses import asdict, dataclass
import json
from math import cos, isfinite, radians, sin, sqrt
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # pragma: no cover - only needed for annotations
    import Part


# One solid prismatic battery pack: an equilateral triangle footprint with a
# 36 mm side, 78 mm tall.  The pack seats on the three cap posts, not on the
# tube mouth, so the cap leaves a 5 mm wiring pocket under it.
PACK_TRIANGLE_SIDE_MM = 36.0
PACK_HEIGHT_MM = 78.0
ASSEMBLY_SOLID_COUNT = 4
# Pack vertices sit at 90/210/330 degrees; the cap posts take the gaps
# between them.
PACK_VERTEX_ANGLES_DEG = (90.0, 210.0, 330.0)
POST_ANGLES_DEG = (30.0, 150.0, 270.0)

@dataclass(frozen=True)
class BatteryGripParameters:
    """Source dimensions for the cylindrical PLA battery grip, in millimetres."""

    # Top flange: identical outline to the lower board cover.
    flange_length: float = 128.0
    flange_width: float = 78.0
    flange_corner_radius: float = 4.0
    flange_thickness: float = 6.0
    cover_underside_z: float = -5.5

    # Screw interface: sixteen M3 pass down through the cover's Ø3.4
    # extension holes and through matching Ø3.4 clearance holes in the full
    # 6 mm flange, held by M3 nuts under the flange.  The flange is one
    # uniform slab -- no local thickening at the hole columns, no tapping.
    mount_hole_x: float = 59.0
    mount_hole_y_pitch: float = 10.0
    mount_hole_diameter: float = 3.4

    # The bottom-cap pilots are the only tapped threads in the handle: each
    # Ø6.5 post carries an M3 thread cut from a Ø2.9 pilot hole.
    cap_pilot_diameter: float = 2.9

    # Pass-through clearance for the four board-mounting screw heads on the
    # cover underside at X = +/-50 mm, Y = +/-35 mm.
    board_screw_x: float = 50.0
    board_screw_y: float = 35.0
    board_screw_clearance_diameter: float = 6.5

    # Cylindrical grip, centred under the cover.  The bottom fan is allowed to
    # exhaust into the bore, so the flange keeps no fan or IMU opening.  The
    # tube was slimmed to Ø44/Ø50 and shortened by 10 mm to 99.
    bore_diameter: float = 44.0
    wall_thickness: float = 3.0
    tube_height: float = 99.0
    root_height: float = 14.0
    root_top_diameter: float = 60.0

    # Solid triangular-prism pack, centred on the bore axis.
    pack_side: float = PACK_TRIANGLE_SIDE_MM
    pack_height: float = PACK_HEIGHT_MM

    # Rear DC-lead window in the tube's -Y wall.  window_top_gap is the plain
    # wall kept between the window's top edge and the conical root: 2 mm more
    # than a band-centred window, so the window sits farther from the flange.
    window_length: float = 14.0
    window_height: float = 13.0
    window_corner_radius: float = 2.0
    window_top_gap: float = 2.5

    # Bottom cap, screwed into three posts standing in the bore's free gaps.
    # Each post is tapped over its whole height, so post_height *is* the M3
    # thread engagement -- it is deliberately independent of the flange.
    # post_radius sits inboard of the Ø44/Ø50 wall so the Ø6.5 posts fuse
    # into the bore wall without punching through the thinner tube.
    post_diameter: float = 6.5
    post_radius: float = 20.0
    post_height: float = 5.0
    cap_thickness: float = 4.0
    cap_hole_diameter: float = 3.4
    cap_counterbore_diameter: float = 6.2
    cap_counterbore_depth: float = 2.2

    @property
    def cap_pilot_depth(self) -> float:
        """M3 thread engagement for the bottom cap: the post is tapped through."""

        return self.post_height

    @property
    def tube_outer_diameter(self) -> float:
        """Outside diameter of the grip you actually hold."""

        return self.bore_diameter + 2.0 * self.wall_thickness

    @property
    def grip_circumference(self) -> float:
        """Grip circumference, the number that decides hand comfort."""

        return 3.141592653589793 * self.tube_outer_diameter

    @property
    def flange_z0(self) -> float:
        """Underside of the mounting flange."""

        return self.cover_underside_z - self.flange_thickness

    @property
    def root_bore_top_diameter(self) -> float:
        """Bore diameter where the conical root meets the flange.

        The root is hollow too: its bore tapers with the outside so the wall
        stays at :attr:`wall_thickness`, which also turns the transition into a
        funnel for the fan exhaust.
        """

        return self.root_top_diameter - 2.0 * self.wall_thickness

    @property
    def window_cut_depth(self) -> float:
        """Radial depth the window cutter needs to clear the curved bore wall.

        A flat cutter meets the round bore first at the window's centre and
        last at its edges, so it must run past the wall by that sagitta or the
        window ends up a blind pocket at both ends.
        """

        bore_radius = self.bore_diameter / 2.0
        half = self.window_length / 2.0
        sagitta = bore_radius - sqrt(max(bore_radius**2 - half**2, 0.0))
        return 0.5 + self.wall_thickness + sagitta + 1.0

    @property
    def mount_hole_depth(self) -> float:
        """Depth of the mounting through-holes: the flange is cut clean through."""

        return self.flange_thickness

    @property
    def root_z0(self) -> float:
        """Plane where the conical root meets the plain tube."""

        return self.flange_z0 - self.root_height

    @property
    def grip_z0(self) -> float:
        """Open bottom face of the tube; the cap posts stand on this plane."""

        return self.root_z0 - self.tube_height

    @property
    def pack_z0(self) -> float:
        """Bottom face of the loaded pack: it seats on the cap-post tops."""

        return self.grip_z0 + self.post_height

    @property
    def pack_z1(self) -> float:
        """Top of the loaded pack."""

        return self.pack_z0 + self.pack_height

    @property
    def plenum_height(self) -> float:
        """Free bore above the pack, which the fan exhausts into."""

        return self.cover_underside_z - self.pack_z1

    @property
    def cap_z0(self) -> float:
        """Outer face of the bottom cap, the lowest point of the handle."""

        return self.grip_z0 - self.cap_thickness

    @property
    def window_center_z(self) -> float:
        """Centre the window, keeping window_top_gap of plain wall above it.

        The window hangs 2 mm lower than a band-centred one, i.e. farther from
        the flange, so the weld line by the conical root keeps more plastic.
        """

        return self.root_z0 - self.window_top_gap - self.window_height / 2.0

    @property
    def total_height(self) -> float:
        """Overall handle height below the lower cover, cap included."""

        return self.cover_underside_z - self.cap_z0

    @property
    def pack_circumdiameter(self) -> float:
        """Diameter of the circle enclosing the triangular pack footprint."""

        return 2.0 * self.pack_side / sqrt(3.0)

    @property
    def pack_inradius(self) -> float:
        """Distance from the bore axis to each triangle edge line."""

        return self.pack_side / (2.0 * sqrt(3.0))

    def __post_init__(self) -> None:
        positive = (
            self.flange_length,
            self.flange_width,
            self.flange_thickness,
            self.mount_hole_x,
            self.mount_hole_y_pitch,
            self.mount_hole_diameter,
            self.cap_pilot_diameter,
            self.board_screw_clearance_diameter,
            self.bore_diameter,
            self.wall_thickness,
            self.tube_height,
            self.root_height,
            self.root_top_diameter,
            self.pack_side,
            self.pack_height,
            self.window_length,
            self.window_height,
            self.window_top_gap,
            self.post_diameter,
            self.post_radius,
            self.post_height,
            self.cap_thickness,
            self.cap_hole_diameter,
            self.cap_counterbore_diameter,
            self.cap_counterbore_depth,
        )
        if not all(isfinite(value) and value > 0.0 for value in positive):
            raise ValueError("grip dimensions must be finite and positive")
        if not isfinite(self.cover_underside_z):
            raise ValueError("the cover underside plane must be finite")
        if 2.0 * self.flange_corner_radius > min(
            self.flange_length, self.flange_width
        ):
            raise ValueError("flange corner radius does not fit its outline")
        if 2.0 * self.window_corner_radius > min(
            self.window_length, self.window_height
        ):
            raise ValueError("window corner radius does not fit the window")

        # The tube and its conical root must stay inside the flange outline.
        if self.root_top_diameter < self.tube_outer_diameter:
            raise ValueError("the root must be at least as wide as the tube")
        if self.root_top_diameter >= min(self.flange_length, self.flange_width):
            raise ValueError("the conical root leaves the flange outline")
        # The root is hollow: its bore must widen, and the flange must keep a
        # usable ring of material around that mouth.
        if self.root_bore_top_diameter <= self.bore_diameter:
            raise ValueError("the hollow root bore must widen toward the flange")
        if self.root_bore_top_diameter >= self.flange_width - 20.0:
            raise ValueError("the root bore leaves too little flange material")

        # The triangular pack must load into the bore with clearance.  The
        # pack seats on the post tops, so it can rotate freely inside the
        # round bore without ever meeting the posts.
        if self.pack_circumdiameter >= self.bore_diameter:
            raise ValueError("the triangular pack does not fit the bore")
        if self.pack_z1 >= self.cover_underside_z:
            raise ValueError("the loaded pack reaches the lower cover")

        # The three cap-screw posts must overlap the bore wall (a tangent post
        # fuses along a line and yields an invalid solid).
        post_radius = self.post_diameter / 2.0
        bore_radius = self.bore_diameter / 2.0
        if self.post_radius + post_radius < bore_radius + 0.3:
            raise ValueError("cap-screw posts must fuse into the bore wall")
        if (
            self.post_radius + post_radius
            > bore_radius + self.wall_thickness - 0.5
        ):
            raise ValueError("cap-screw posts push through the tube wall")
        if self.post_height > self.tube_height:
            raise ValueError("cap-screw posts are taller than the tube")
        if self.cap_pilot_depth < 5.0:
            raise ValueError("cap-screw M3 engagement must be at least 5 mm")
        if self.cap_thickness - self.cap_counterbore_depth + self.cap_pilot_depth < 5.0:
            raise ValueError("the cap screw has too little shank to grip")

        # The DC-lead window must sit in the plain wall above the pack with
        # plastic above it (window_top_gap) and clear of the pack top below.
        if (
            self.root_z0 - self.pack_z1
            <= self.window_top_gap + self.window_height
        ):
            raise ValueError("no plain wall band left for the DC-lead window")
        if self.window_length >= self.bore_diameter:
            raise ValueError("the window is wider than the bore")

        # Mount holes are plain M3 clearance cut through the whole 6 mm
        # flange; retention comes from an M3 nut under the flange, never from
        # threads in the flange itself.
        if self.mount_hole_diameter >= self.mount_hole_y_pitch:
            raise ValueError(
                "adjacent mount holes must leave material between them"
            )
        if (
            self.mount_hole_x + self.mount_hole_diameter / 2.0
            >= self.flange_length / 2.0
        ):
            raise ValueError("the mount hole columns leave the flange length")
        if (
            3.5 * self.mount_hole_y_pitch + self.mount_hole_diameter / 2.0
            >= self.flange_width / 2.0
        ):
            raise ValueError("the outer mount hole row leaves the flange width")
        if self.cap_counterbore_diameter <= self.cap_hole_diameter:
            raise ValueError("the cap counterbore must exceed its through hole")
        if self.cap_counterbore_depth >= self.cap_thickness:
            raise ValueError("the cap counterbore must leave material")
        if self.cap_hole_diameter >= self.post_diameter:
            raise ValueError("cap screws must land inside the posts")

def _polar_offsets(
    radius: float, angles_deg: Iterable[float]
) -> tuple[tuple[float, float], ...]:
    """Return XY offsets from the bore axis at *radius* for each angle."""

    return tuple(
        (radius * cos(radians(angle)), radius * sin(radians(angle)))
        for angle in angles_deg
    )


def pack_vertices(p: BatteryGripParameters) -> tuple[tuple[float, float], ...]:
    """Return the board-local XY vertices of the triangular pack footprint."""

    return _polar_offsets(p.pack_side / sqrt(3.0), PACK_VERTEX_ANGLES_DEG)


def cap_screw_centers(
    p: BatteryGripParameters,
) -> tuple[tuple[float, float], ...]:
    """Return the board-local XY axes of the three bottom-cap screws."""

    return _polar_offsets(p.post_radius, POST_ANGLES_DEG)


def mount_hole_centers(
    p: BatteryGripParameters,
) -> tuple[tuple[float, float], ...]:
    """Return all sixteen flange mount-hole axes, matching the cover columns."""

    return tuple(
        (x, multiplier * p.mount_hole_y_pitch)
        for x in (-p.mount_hole_x, p.mount_hole_x)
        for multiplier in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5)
    )


def board_screw_centers(
    p: BatteryGripParameters,
) -> tuple[tuple[float, float], ...]:
    """Return the four board-mounting screw axes the flange must pass."""

    return tuple(
        (x, y)
        for x in (-p.board_screw_x, p.board_screw_x)
        for y in (-p.board_screw_y, p.board_screw_y)
    )


def _fuse_all(shapes: Iterable["Part.Shape"]) -> "Part.Shape":
    """Fuse a non-empty sequence without refining intermediate results."""

    iterator = iter(shapes)
    result = next(iterator)
    for shape in iterator:
        result = result.fuse(shape)
    return result


def rounded_prism_xy(
    length: float,
    width: float,
    radius: float,
    height: float,
    center_x: float,
    center_y: float,
    z0: float,
) -> "Part.Shape":
    """Build a rectangular prism with four vertical rounded corners."""

    import FreeCAD as App
    import Part

    left = center_x - length / 2.0
    bottom = center_y - width / 2.0
    if radius <= 0.0:
        return Part.makeBox(length, width, height, App.Vector(left, bottom, z0))

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
    return _fuse_all((x_box, y_box, *corners))


def make_grip_body(p: BatteryGripParameters) -> "Part.Shape":
    """Build the printable grip body: flange, conical root, tube, and posts."""

    import FreeCAD as App
    import Part

    # One uniform flange slab: no local thickening at the screw columns.
    flange = rounded_prism_xy(
        p.flange_length,
        p.flange_width,
        p.flange_corner_radius,
        p.flange_thickness,
        0.0,
        0.0,
        p.flange_z0,
    )
    root = Part.makeCone(
        p.tube_outer_diameter / 2.0,
        p.root_top_diameter / 2.0,
        p.root_height,
        App.Vector(0.0, 0.0, p.root_z0),
    )
    tube = Part.makeCylinder(
        p.tube_outer_diameter / 2.0,
        p.tube_height,
        App.Vector(0.0, 0.0, p.grip_z0),
    )
    # The bore runs from the open bottom right through the flange: the lower
    # cover is the cavity ceiling and the fan exhausts straight into it.  The
    # conical root is hollow too, so the bore flares with it into a funnel.
    tube_bore = Part.makeCylinder(
        p.bore_diameter / 2.0,
        p.tube_height + 0.1,
        App.Vector(0.0, 0.0, p.grip_z0 - 0.1),
    )
    root_bore = Part.makeCone(
        p.bore_diameter / 2.0,
        p.root_bore_top_diameter / 2.0,
        p.root_height,
        App.Vector(0.0, 0.0, p.root_z0),
    )
    flange_bore = Part.makeCylinder(
        p.root_bore_top_diameter / 2.0,
        p.flange_thickness + 0.1,
        App.Vector(0.0, 0.0, p.flange_z0),
    )
    bore = _fuse_all((tube_bore, root_bore, flange_bore))
    posts = tuple(
        Part.makeCylinder(
            p.post_diameter / 2.0,
            p.post_height,
            App.Vector(x, y, p.grip_z0),
        )
        for x, y in cap_screw_centers(p)
    )
    solid = _fuse_all(
        (_fuse_all((flange, root, tube)).cut(bore), *posts)
    )
    mount_holes = tuple(
        Part.makeCylinder(
            p.mount_hole_diameter / 2.0,
            p.mount_hole_depth,
            App.Vector(x, y, p.cover_underside_z),
            App.Vector(0.0, 0.0, -1.0),
        )
        for x, y in mount_hole_centers(p)
    )
    cap_pilots = tuple(
        Part.makeCylinder(
            p.cap_pilot_diameter / 2.0,
            p.cap_pilot_depth + 0.1,
            App.Vector(x, y, p.grip_z0 - 0.1),
        )
        for x, y in cap_screw_centers(p)
    )
    board_screw_holes = tuple(
        Part.makeCylinder(
            p.board_screw_clearance_diameter / 2.0,
            p.flange_thickness + 0.2,
            App.Vector(x, y, p.flange_z0 - 0.1),
        )
        for x, y in board_screw_centers(p)
    )
    window = rounded_prism_xy(
        p.window_length,
        p.window_height,
        p.window_corner_radius,
        p.window_cut_depth,
        0.0,
        0.0,
        0.0,
    )
    window.Placement = App.Placement(
        App.Vector(
            0.0,
            -p.tube_outer_diameter / 2.0 - 0.5,
            p.window_center_z,
        ),
        App.Rotation(App.Vector(1.0, 0.0, 0.0), -90.0),
    )
    cutters = _fuse_all((*mount_holes, *cap_pilots, *board_screw_holes, window))
    return solid.cut(cutters).removeSplitter()


def make_bottom_cap(p: BatteryGripParameters) -> "Part.Shape":
    """Build the screwed bottom cap that closes the loaded battery cavity."""

    import FreeCAD as App
    import Part

    plate = Part.makeCylinder(
        p.tube_outer_diameter / 2.0,
        p.cap_thickness,
        App.Vector(0.0, 0.0, p.cap_z0),
    )
    holes = tuple(
        Part.makeCylinder(
            p.cap_hole_diameter / 2.0,
            p.cap_thickness + 0.2,
            App.Vector(x, y, p.cap_z0 - 0.1),
        )
        for x, y in cap_screw_centers(p)
    )
    counterbores = tuple(
        Part.makeCylinder(
            p.cap_counterbore_diameter / 2.0,
            p.cap_counterbore_depth + 0.1,
            App.Vector(x, y, p.cap_z0 - 0.1),
        )
        for x, y in cap_screw_centers(p)
    )
    return plate.cut(_fuse_all((*holes, *counterbores))).removeSplitter()


def make_pack_reference(p: BatteryGripParameters) -> "Part.Shape":
    """Build the solid triangular-prism pack envelope; never a printed part."""

    import FreeCAD as App
    import Part

    points = [App.Vector(x, y, p.pack_z0) for x, y in pack_vertices(p)]
    face = Part.Face(Part.makePolygon([*points, points[0]]))
    return face.extrude(App.Vector(0.0, 0.0, p.pack_height))


@dataclass(frozen=True)
class GripCoverAssembly:
    """The lower board cover with the cylindrical battery grip underneath."""

    lower_cover: "Part.Shape"
    grip_body: "Part.Shape"
    bottom_cap: "Part.Shape"
    pack_reference: "Part.Shape"


def build_grip_cover_assembly(
    p: BatteryGripParameters | None = None,
) -> GripCoverAssembly:
    """Assemble the grip against the current lower board cover, in place."""

    from .board_covers import BoardCoverParameters, make_bottom_cover

    parameters = p or BatteryGripParameters()
    cover_parameters = BoardCoverParameters()
    cover = make_bottom_cover(cover_parameters)
    underside = cover.BoundBox.ZMin
    if abs(underside - parameters.cover_underside_z) > 1e-9:
        raise ValueError(
            "lower cover underside moved: grip expects "
            f"{parameters.cover_underside_z}, cover is at {underside}"
        )
    expected_length = (
        cover_parameters.board_length + 2.0 * cover_parameters.bottom_end_extension
    )
    if (
        abs(parameters.flange_length - expected_length) > 1e-9
        or abs(parameters.flange_width - cover_parameters.board_width) > 1e-9
    ):
        raise ValueError(
            "the grip flange no longer matches the lower cover outline: "
            f"{parameters.flange_length} x {parameters.flange_width} vs "
            f"{expected_length} x {cover_parameters.board_width}"
        )
    return GripCoverAssembly(
        lower_cover=cover,
        grip_body=make_grip_body(parameters),
        bottom_cap=make_bottom_cap(parameters),
        pack_reference=make_pack_reference(parameters),
    )


PRINT_BED_MM = 256.0
PRINT_PART_CLEARANCE_MM = 8.0


def build_battery_grip_print_plate(
    p: BatteryGripParameters | None = None,
) -> tuple[tuple[str, "Part.Shape"], ...]:
    """Lay both printed grip parts on a centred 256 x 256 mm bed.

    Both are flipped 180 degrees about X relative to the assembly:

    * the body prints **flange-down**, giving a 128 x 78 mm first layer and
      leaving every outer surface self-supporting -- the conical root shrinks
      as it rises, and the bore's open end faces up;
    * the cap prints **outer-face-down**, so its counterbores open upward and
      no overhang is created at all.
    """

    from .print_plate import place_on_bed

    import FreeCAD as App

    parameters = p or BatteryGripParameters()
    flip = ((App.Vector(1.0, 0.0, 0.0), 180.0),)
    return (
        (
            "Battery grip body",
            place_on_bed(make_grip_body(parameters), 0.0, -20.0, flip),
        ),
        (
            "Battery grip bottom cap",
            place_on_bed(make_bottom_cap(parameters), 0.0, 56.0, flip),
        ),
    )


def validate_print_plate(
    parts: tuple[tuple[str, "Part.Shape"], ...],
) -> dict[str, float | bool]:
    """Check both parts sit on Z = 0, fit the bed, and keep their clearance."""

    half_bed = PRINT_BED_MM / 2.0
    boxes = [shape.BoundBox for _name, shape in parts]
    first, second = boxes
    # Two parts are separated if they clear each other on either axis; take the
    # larger of the two directed gaps so a negative overlap cannot mask it.
    clearance = max(
        max(second.XMin - first.XMax, first.XMin - second.XMax),
        max(second.YMin - first.YMax, first.YMin - second.YMax),
    )
    (_body_name, body), (_cap_name, cap) = parts
    return {
        "part_count": len(parts),
        "all_single_solids": all(
            shape.isValid() and len(shape.Solids) == 1 for _name, shape in parts
        ),
        "all_seated_on_bed": all(abs(box.ZMin) < 1e-6 for box in boxes),
        "within_bed": all(
            -half_bed <= box.XMin and box.XMax <= half_bed
            and -half_bed <= box.YMin and box.YMax <= half_bed
            for box in boxes
        ),
        "min_part_clearance_mm": clearance,
        "parts_disjoint": body.common(cap).Volume < 1e-6,
        "body_height_mm": boxes[0].ZLength,
        "body_first_layer_mm2": boxes[0].XLength * boxes[0].YLength,
        "cap_height_mm": boxes[1].ZLength,
    }


INTERFERENCE_FIELDS = (
    "grip_cover_common_volume_mm3",
    "grip_cap_common_volume_mm3",
    "pack_grip_common_volume_mm3",
    "pack_cap_common_volume_mm3",
    "pack_cover_common_volume_mm3",
)


def _cover_opening_flow(
    body: "Part.Shape", p: BatteryGripParameters
) -> dict[str, float]:
    """Measure how much of each cover opening stays open through the flange.

    The flange deliberately keeps no fan or IMU cut-out: the bore is meant to
    take the fan exhaust.  These numbers record what that actually leaves open
    so the thermal consequence is visible rather than implied.
    """

    from .board_covers import BoardCoverParameters

    cover = BoardCoverParameters()
    results: dict[str, float] = {}
    for name, center_x, center_y, length, width, radius in (
        (
            "fan",
            cover.bottom_fan_center_x,
            cover.bottom_fan_center_y,
            cover.bottom_fan_opening_length,
            cover.bottom_fan_opening_width,
            cover.bottom_fan_opening_corner_radius,
        ),
        (
            "imu",
            cover.bottom_imu_center_x,
            cover.bottom_imu_center_y,
            cover.bottom_imu_opening_length,
            cover.bottom_imu_opening_width,
            cover.bottom_imu_opening_corner_radius,
        ),
    ):
        column = rounded_prism_xy(
            length, width, radius, p.flange_thickness, center_x, center_y, p.flange_z0
        )
        total = column.Volume / p.flange_thickness
        open_area = column.cut(body).Volume / p.flange_thickness
        results[f"{name}_opening_area_mm2"] = total
        results[f"{name}_opening_open_area_mm2"] = open_area
        results[f"{name}_opening_open_fraction"] = open_area / total
    return results


def validate_grip_cover_assembly(
    assembly: GripCoverAssembly,
    p: BatteryGripParameters | None = None,
) -> dict[str, float | bool]:
    """Return solid validity, contact volumes, and cover-opening flow areas."""

    parameters = p or BatteryGripParameters()
    body = assembly.grip_body
    bounds = body.BoundBox
    return {
        "grip_body_valid": body.isValid() and len(body.Solids) == 1,
        "bottom_cap_valid": (
            assembly.bottom_cap.isValid() and len(assembly.bottom_cap.Solids) == 1
        ),
        "grip_body_volume_mm3": body.Volume,
        "bottom_cap_volume_mm3": assembly.bottom_cap.Volume,
        "grip_cover_common_volume_mm3": body.common(assembly.lower_cover).Volume,
        "grip_cap_common_volume_mm3": body.common(assembly.bottom_cap).Volume,
        "pack_grip_common_volume_mm3": assembly.pack_reference.common(body).Volume,
        "pack_cap_common_volume_mm3": assembly.pack_reference.common(
            assembly.bottom_cap
        ).Volume,
        "pack_cover_common_volume_mm3": assembly.pack_reference.common(
            assembly.lower_cover
        ).Volume,
        "flange_top_z": bounds.ZMax,
        "handle_bottom_z": assembly.bottom_cap.BoundBox.ZMin,
        "flange_length_mm": bounds.XLength,
        "flange_width_mm": bounds.YLength,
        **_cover_opening_flow(body, parameters),
    }


def mount_holes_match_cover(p: BatteryGripParameters | None = None) -> bool:
    """Confirm every flange mount hole sits on a cover extension hole, and the
    through diameter matches the cover's, so an M3 passes both plates freely."""

    from .board_covers import BoardCoverParameters, extension_hole_centers

    parameters = p or BatteryGripParameters()
    cover = BoardCoverParameters()
    cover_holes = {
        (round(x, 6), round(y, 6))
        for x, y in extension_hole_centers(cover)
    }
    holes = {
        (round(x, 6), round(y, 6)) for x, y in mount_hole_centers(parameters)
    }
    return (
        holes == cover_holes
        and parameters.mount_hole_diameter == cover.mounting_hole_diameter
    )


NAMED_ASSEMBLY_SHAPES = (
    ("LowerCover", "UAV V3 下盖板"),
    ("GripBody", "电池手柄本体"),
    ("GripBottomCap", "电池手柄底盖"),
    ("CellPackReference", "三角柱电池包参考（非打印件）"),
)


def _assembly_members(
    assembly: GripCoverAssembly,
) -> tuple[tuple[str, str, "Part.Shape"], ...]:
    shapes = (
        assembly.lower_cover,
        assembly.grip_body,
        assembly.bottom_cap,
        assembly.pack_reference,
    )
    return tuple(
        (name, label, shape)
        for (name, label), shape in zip(NAMED_ASSEMBLY_SHAPES, shapes)
    )


def _add_shape(document, name: str, label: str, shape: "Part.Shape"):
    obj = document.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape
    return obj


def _step_reimports_as_valid_solids(path: Path, expected_solids: int) -> bool:
    """Confirm a STEP export reimports as exactly *expected_solids* valid solids.

    Counting solids rather than document objects keeps the check stable: the
    pack reference is one shape on export but STEP may hand it back as a
    separate product.
    """

    import FreeCAD as App
    import Import

    document = App.newDocument(f"GripStepCheck_{path.stem}")
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
        if not shapes:
            return False
        return sum(len(shape.Solids) for shape in shapes) == expected_solids and all(
            shape.isValid() and shape.Volume > 1.0 for shape in shapes
        )
    finally:
        App.closeDocument(document.Name)


def build_battery_grip_outputs(
    project_root: Path,
    output_dir: Path | None = None,
) -> tuple[Path, ...]:
    """Save the grip/cover FCStd, printable STEP parts, and a validation report.

    No STL is written: the user asked for CAD only.
    """

    import FreeCAD as App
    import Import

    root = Path(project_root).resolve()
    p = BatteryGripParameters()
    assembly = build_grip_cover_assembly(p)
    results = validate_grip_cover_assembly(assembly, p)
    if not (results["grip_body_valid"] and results["bottom_cap_valid"]):
        raise ValueError(f"grip solids are not single valid solids: {results}")
    for field in INTERFERENCE_FIELDS:
        if results[field] >= 1e-6:
            raise ValueError(f"unexpected interference in {field}: {results}")
    if not mount_holes_match_cover(p):
        raise ValueError(
            "flange mount holes no longer match the cover extension holes"
        )

    if output_dir is None:
        model_dir = root / "models"
        export_dir = root / "exports"
        report_dir = root / "reports"
    else:
        model_dir = export_dir = report_dir = Path(output_dir).resolve()
    for directory in {model_dir, export_dir, report_dir}:
        directory.mkdir(parents=True, exist_ok=True)

    fcstd_path = model_dir / "battery_grip_cover_assembly.FCStd"
    body_step = export_dir / "battery_grip_body.step"
    cap_step = export_dir / "battery_grip_bottom_cap.step"
    assembly_step = export_dir / "battery_grip_cover_assembly.step"
    plate_step = export_dir / "battery_grip_256x256_print_plate.step"
    report_path = report_dir / "battery_grip_validation.json"

    document = App.newDocument("UAV_V3_BatteryGrip")
    try:
        sheet = document.addObject("Spreadsheet::Sheet", "Parameters")
        sheet.Label = "手柄参数"
        sheet.set("A1", "Parameter")
        sheet.set("B1", "Value (mm)")
        for row, (name, value) in enumerate(asdict(p).items(), start=2):
            sheet.set(f"A{row}", name)
            sheet.set(f"B{row}", str(value))

        objects = {
            name: _add_shape(document, name, label, shape)
            for name, label, shape in _assembly_members(assembly)
        }
        # ViewObject is absent in console mode; only style the reference when a
        # GUI is attached so the pack reads as non-printable.
        reference_view = objects["CellPackReference"].ViewObject
        if reference_view is not None:
            reference_view.Transparency = 55
            reference_view.ShapeColor = (0.30, 0.72, 0.35)
        document.recompute()
        document.saveAs(str(fcstd_path))
        Import.export([objects["GripBody"]], str(body_step))
        Import.export([objects["GripBottomCap"]], str(cap_step))
        Import.export(list(objects.values()), str(assembly_step))
    finally:
        App.closeDocument(document.Name)

    # One ready-to-slice STEP: both printed parts, print-oriented, seated on Z = 0.
    plate = build_battery_grip_print_plate(p)
    plate_results = validate_print_plate(plate)
    if not (
        plate_results["all_single_solids"]
        and plate_results["all_seated_on_bed"]
        and plate_results["within_bed"]
        and plate_results["parts_disjoint"]
        and plate_results["min_part_clearance_mm"] >= PRINT_PART_CLEARANCE_MM
    ):
        raise ValueError(f"print plate layout is not printable: {plate_results}")
    plate_document = App.newDocument("BatteryGripPrintPlate")
    try:
        plate_objects = [
            _add_shape(plate_document, f"PrintPart{index}", label, shape)
            for index, (label, shape) in enumerate(plate, start=1)
        ]
        plate_document.recompute()
        Import.export(plate_objects, str(plate_step))
    finally:
        App.closeDocument(plate_document.Name)

    reimports = {
        "exports/battery_grip_body.step": _step_reimports_as_valid_solids(body_step, 1),
        "exports/battery_grip_bottom_cap.step": _step_reimports_as_valid_solids(
            cap_step, 1
        ),
        "exports/battery_grip_cover_assembly.step": _step_reimports_as_valid_solids(
            assembly_step, ASSEMBLY_SOLID_COUNT
        ),
        "exports/battery_grip_256x256_print_plate.step": (
            _step_reimports_as_valid_solids(plate_step, 2)
        ),
    }
    if not all(reimports.values()):
        raise ValueError(f"a grip export failed STEP round-trip: {reimports}")

    report = {
        "schema_version": 1,
        "parameters": asdict(p),
        "printed_parts": ["battery_grip_body", "battery_grip_bottom_cap"],
        "print_plate_step": "exports/battery_grip_256x256_print_plate.step",
        "print_plate_bed_mm": [PRINT_BED_MM, PRINT_BED_MM],
        "print_orientation": (
            "body flange-down, cap outer-face-down; both flipped 180 deg about X"
        ),
        **{f"print_plate_{k}": v for k, v in plate_results.items()},
        "stl_written": False,
        "grip_profile": "cylindrical",
        "bore_diameter_mm": p.bore_diameter,
        "root_bore_top_diameter_mm": p.root_bore_top_diameter,
        "root_is_hollow": True,
        "tube_outer_diameter_mm": p.tube_outer_diameter,
        "wall_thickness_mm": p.wall_thickness,
        "grip_circumference_mm": p.grip_circumference,
        "tube_height_mm": p.tube_height,
        "pack_shape": "solid equilateral triangular prism",
        "pack_side_mm": p.pack_side,
        "pack_height_mm": p.pack_height,
        "pack_vertices_mm": [list(vertex) for vertex in pack_vertices(p)],
        "pack_circumdiameter_mm": p.pack_circumdiameter,
        "bore_pack_radial_clearance_mm": (
            p.bore_diameter - p.pack_circumdiameter
        ) / 2.0,
        "pack_seat_z": p.pack_z0,
        "pack_seats_on_cap_posts": True,
        "top_lid": "none - the lower board cover closes the bore",
        "plenum_height_mm": p.plenum_height,
        "handle_total_height_mm": p.total_height,
        "flange_size_mm": [p.flange_length, p.flange_width, p.flange_thickness],
        "mount_screw_count": len(mount_hole_centers(p)),
        "mount_hole_diameter_mm": p.mount_hole_diameter,
        "mount_hole_depth_mm": p.mount_hole_depth,
        "mount_holes_match_cover": mount_holes_match_cover(p),
        "board_screw_clearance_diameter_mm": p.board_screw_clearance_diameter,
        "dc_window_size_mm": [p.window_length, p.window_height],
        "dc_window_center_mm": [
            0.0,
            -p.tube_outer_diameter / 2.0,
            p.window_center_z,
        ],
        "cap_screw_count": len(cap_screw_centers(p)),
        "cap_post_diameter_mm": p.post_diameter,
        "cap_post_height_mm": p.post_height,
        "cap_post_axis_radius_mm": p.post_radius,
        "cap_pilot_depth_mm": p.cap_pilot_depth,
        "cap_screw_centers_mm": [list(center) for center in cap_screw_centers(p)],
        "reimports": reimports,
        **results,
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return (
        fcstd_path,
        body_step,
        cap_step,
        assembly_step,
        plate_step,
        report_path,
    )
