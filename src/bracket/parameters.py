"""Immutable R45 bracket dimensions and their derived design chains."""

from dataclasses import dataclass
from math import degrees, radians, sin


@dataclass(frozen=True)
class DerivedDimensions:
    """Values calculated from one bracket parameter set, in millimetres."""

    main_side_gap: float
    pivot_thread_engagement: float
    locked_thread_engagement: float
    screw_tip_setback: float
    slot_overrun_deg: float
    slot_total_arc_length: float
    sector_profile_extension_deg: float
    sector_top_above_base: float
    plate_base_clearance: float


@dataclass(frozen=True)
class BracketParameters:
    """Source dimensions for the compact R45 MID-360 PLA tilt bracket."""

    sensor_width: float = 65.0
    sensor_mount_pitch_x: float = 36.0
    sensor_mount_pitch_y: float = 48.0
    sensor_mount_hole_diameter: float = 3.5
    a_plate_width: float = 69.0
    a_plate_depth: float = 85.0
    a_plate_thickness: float = 6.0
    a_b_pilot_hole_diameter: float = 2.9
    side_thread_depth: float = 6.0
    lock_thread_depth: float = 7.0
    a_pivot_y: float = 38.0
    a_pivot_z: float = -3.0
    b_base_width: float = 128.0
    b_base_depth: float = 78.0
    b_base_thickness: float = 4.0
    b_inner_width: float = 69.8
    b_wall_thickness: float = 4.0
    b_clearance_hole_diameter: float = 3.4
    b_base_mount_hole_diameter: float = 3.4
    b_pivot_y: float = 33.0
    pivot_z_above_base: float = 10.0
    lock_radius: float = 45.0
    sector_outer_radius: float = 53.0
    working_angle_deg: float = 40.0
    slot_width: float = 3.4
    slot_overrun_length: float = 1.5
    sector_bridge_length: float = 4.0
    sector_pivot_lobe_radius: float = 6.0
    track_recess_depth: float = 1.0
    root_rib_extension: float = 10.0
    root_rib_depth: float = 8.0
    root_rib_height: float = 6.0
    root_rib_y_center: float = 16.0
    m25_screw_length: float = 10.0
    m3_screw_length: float = 8.0
    # Rounded rectangular opening through the base plate, over the upper
    # cover's fan/heatsink opening.  These four values copy
    # BoardCoverParameters' top_fan_* fields; parameters.py stays FreeCAD-free
    # so it cannot import them, and a FreeCAD test asserts they stay in step.
    b_fan_center_x: float = -0.153
    b_fan_center_y: float = 6.830
    b_fan_opening_length: float = 60.0
    b_fan_opening_width: float = 41.0
    b_fan_opening_corner_radius: float = 3.0
    d435i_shelf_width: float = 92.0
    d435i_shelf_depth: float = 20.0
    d435i_shelf_corner_radius: float = 4.0
    d435i_mount_clearance_diameter: float = 6.8
    d435i_screw_shaft_diameter: float = 6.35
    d435i_screw_head_diameter: float = 12.0
    d435i_screw_head_height: float = 7.0
    # Rounded rectangular opening through the B base plate, over the upper
    # cover's fan/heatsink opening.  The centre and size mirror
    # BoardCoverParameters.top_fan_* -- board_covers.py needs FreeCAD, so this
    # pure-Python module cannot import it; tests/freecad/test_part_geometry.py
    # asserts the two stay in step.
    b_fan_center_x: float = -0.153
    b_fan_center_y: float = 6.830
    b_fan_opening_length: float = 60.0
    b_fan_opening_width: float = 41.0
    b_fan_opening_corner_radius: float = 3.0

    def __post_init__(self) -> None:
        positive = (
            self.sensor_mount_pitch_x,
            self.sensor_mount_pitch_y,
            self.sensor_mount_hole_diameter,
            self.a_plate_width,
            self.a_plate_depth,
            self.a_plate_thickness,
            self.a_b_pilot_hole_diameter,
            self.side_thread_depth,
            self.lock_thread_depth,
            self.b_base_width,
            self.b_base_depth,
            self.b_base_thickness,
            self.b_inner_width,
            self.b_wall_thickness,
            self.b_clearance_hole_diameter,
            self.b_base_mount_hole_diameter,
            self.pivot_z_above_base,
            self.lock_radius,
            self.sector_outer_radius,
            self.slot_width,
            self.slot_overrun_length,
            self.sector_bridge_length,
            self.sector_pivot_lobe_radius,
            self.track_recess_depth,
            self.root_rib_extension,
            self.root_rib_depth,
            self.root_rib_height,
            self.root_rib_y_center,
            self.m25_screw_length,
            self.m3_screw_length,
            self.b_fan_opening_length,
            self.b_fan_opening_width,
            self.b_fan_opening_corner_radius,
            self.d435i_shelf_width,
            self.d435i_shelf_depth,
            self.d435i_shelf_corner_radius,
            self.d435i_mount_clearance_diameter,
            self.d435i_screw_shaft_diameter,
            self.d435i_screw_head_diameter,
            self.d435i_screw_head_height,
            self.b_fan_opening_length,
            self.b_fan_opening_width,
            self.b_fan_opening_corner_radius,
        )
        if any(value <= 0.0 for value in positive):
            raise ValueError("physical dimensions must be positive")
        if not 0.0 <= self.working_angle_deg <= 40.0:
            raise ValueError("angle must be in [0, 40] degrees")

        dimensions = derive(self)
        if dimensions.main_side_gap < 0.4 - 1e-9:
            raise ValueError("A/B side gap must be at least 0.4 mm")
        if dimensions.plate_base_clearance < 2.0:
            raise ValueError("A plate/base clearance must be at least 2 mm")
        if dimensions.locked_thread_engagement < 5.0:
            raise ValueError("M2.5 thread engagement must be at least 5 mm")
        if dimensions.pivot_thread_engagement < 5.0:
            raise ValueError("M2.5 pivot engagement must be at least 5 mm")
        if dimensions.screw_tip_setback < 0.2:
            raise ValueError("M2.5 screw tip setback must be at least 0.2 mm")
        if self.side_thread_depth - dimensions.pivot_thread_engagement < 0.2:
            raise ValueError("M2.5 pivot screw tip setback must be at least 0.2 mm")
        if self.sector_outer_radius < self.lock_radius + 8.0:
            raise ValueError("sector requires 8 mm outside the slot centerline")
        if self.track_recess_depth >= self.b_wall_thickness:
            raise ValueError("track recess must leave positive wall thickness")
        if self.sector_pivot_lobe_radius > self.b_base_depth / 2.0 - self.b_pivot_y:
            raise ValueError("pivot lobe must stay inside the base depth")
        outer_wall_x = self.b_inner_width / 2.0 + self.b_wall_thickness
        if self.root_rib_extension > self.b_base_width / 2.0 - outer_wall_x:
            raise ValueError("root rib must stay inside the B base width")
        if 2.0 * self.b_fan_opening_corner_radius > min(
            self.b_fan_opening_length, self.b_fan_opening_width
        ):
            raise ValueError("B fan opening corner radius does not fit")
        # The opening must stay between the two sector ears so each ear keeps an
        # uninterrupted seat, and the plate must stay a continuous frame rather
        # than a pair of slivers.
        ear_strip = self.b_inner_width / 2.0 - (
            abs(self.b_fan_center_x) + self.b_fan_opening_length / 2.0
        )
        edge_strip = self.b_base_depth / 2.0 - (
            abs(self.b_fan_center_y) + self.b_fan_opening_width / 2.0
        )
        if ear_strip < 0.0:
            raise ValueError("B fan opening reaches past the sector ears")
        if min(ear_strip, edge_strip) < 3.0:
            raise ValueError("B fan opening leaves less than 3 mm of base plate")
        if self.d435i_shelf_width > self.b_base_width:
            raise ValueError("D435i shelf must stay inside the B base width")
        if 2.0 * self.d435i_shelf_corner_radius > self.d435i_shelf_depth:
            raise ValueError("D435i shelf corner radius must fit its depth")
        if self.d435i_mount_clearance_diameter <= self.d435i_screw_shaft_diameter:
            raise ValueError("D435i clearance must exceed the screw shaft")
        if self.d435i_screw_head_diameter <= self.d435i_mount_clearance_diameter:
            raise ValueError("D435i screw head must exceed the clearance hole")
        if self.d435i_screw_head_height > 20.0:
            raise ValueError("D435i screw head must fit below the upper cover gap")

        rib_half_depth = self.root_rib_depth / 2.0
        if (
            -self.root_rib_y_center - rib_half_depth
            < self.b_pivot_y - self.sector_outer_radius
            or self.root_rib_y_center + rib_half_depth > self.b_pivot_y
        ):
            raise ValueError("both root ribs must overlap the sector-wall footprint")


def derive(p: BracketParameters) -> DerivedDimensions:
    """Calculate side, fastening, slot, and vertical-clearance chains."""

    main_side_gap = (p.b_inner_width - p.a_plate_width) / 2.0
    pivot_thread_engagement = p.m25_screw_length - p.b_wall_thickness - main_side_gap
    locked_thread_engagement = (
        p.m25_screw_length
        - (p.b_wall_thickness - p.track_recess_depth)
        - main_side_gap
    )
    slot_overrun_deg = degrees(p.slot_overrun_length / p.lock_radius)
    sector_profile_extension_deg = degrees(
        (p.slot_overrun_length + p.slot_width / 2.0 + p.sector_bridge_length)
        / p.lock_radius
    )
    return DerivedDimensions(
        main_side_gap=main_side_gap,
        pivot_thread_engagement=pivot_thread_engagement,
        locked_thread_engagement=locked_thread_engagement,
        screw_tip_setback=p.lock_thread_depth - locked_thread_engagement,
        slot_overrun_deg=slot_overrun_deg,
        slot_total_arc_length=(
            p.lock_radius * radians(p.working_angle_deg)
            + 2.0 * p.slot_overrun_length
        ),
        sector_profile_extension_deg=sector_profile_extension_deg,
        sector_top_above_base=(
            p.pivot_z_above_base
            + p.sector_outer_radius
            * sin(radians(p.working_angle_deg + sector_profile_extension_deg))
        ),
        plate_base_clearance=(
            p.pivot_z_above_base - p.a_pivot_z - p.a_plate_thickness
        ),
    )
