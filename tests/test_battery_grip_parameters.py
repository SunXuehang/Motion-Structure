"""Unit checks for the cylindrical battery-grip dimensions and derived chain."""

from dataclasses import replace
from math import pi, sqrt

import pytest

try:
    from bracket.battery_grip import (
        AA_CELL_DIAMETER_MM,
        AA_CELL_LENGTH_MM,
        BatteryGripParameters,
        board_screw_centers,
        cap_screw_centers,
        cell_centers,
        mount_pilot_centers,
    )
except ImportError:  # pragma: no cover - only when the module is missing
    BatteryGripParameters = None


def test_flange_matches_the_lower_cover_outline() -> None:
    """Catch a flange that stops matching the 128 x 78 mm lower cover."""

    assert BatteryGripParameters is not None, "battery-grip parameters are missing"
    p = BatteryGripParameters()
    assert (p.flange_length, p.flange_width, p.flange_corner_radius) == (
        128.0,
        78.0,
        4.0,
    )
    assert (p.cover_underside_z, p.flange_z0) == (-5.5, -11.5)


def test_cylinder_is_bore_35_6_wall_3_outer_41_6() -> None:
    """Catch a bore or wall change that silently moves the grip diameter."""

    p = BatteryGripParameters()
    assert (p.bore_diameter, p.wall_thickness) == (35.6, 3.0)
    assert p.tube_outer_diameter == pytest.approx(41.6)
    assert p.grip_circumference == pytest.approx(pi * 41.6)


def test_derived_z_chain_stacks_flange_root_tube_and_cap() -> None:
    """Catch a broken Z chain that would float or bury the grip."""

    p = BatteryGripParameters()
    assert (p.root_z0, p.grip_z0) == (-25.5, -97.5)
    assert p.cell_z1 == -47.0
    assert (p.cap_z0, p.total_height) == (-101.5, 96.0)
    assert p.plenum_height == pytest.approx(41.5)
    assert p.window_center_z == pytest.approx(-36.25)


def test_bore_has_no_top_lid_so_the_cover_closes_it() -> None:
    """Catch a re-introduced top lid, or cells growing into the cover."""

    p = BatteryGripParameters()
    # The cells stop below the cover underside; the plenum is the fan's path.
    assert p.cell_z1 < p.cover_underside_z
    assert p.plenum_height > 0.0
    with pytest.raises(ValueError, match="cells reach the lower cover"):
        replace(p, tube_height=20.0)


def test_three_cells_form_an_equilateral_triangle_inside_the_bore() -> None:
    """Catch a pack that stops being an equilateral triangle or outgrows the bore."""

    p = BatteryGripParameters()
    assert (p.cell_diameter, p.cell_length) == (AA_CELL_DIAMETER_MM, AA_CELL_LENGTH_MM)
    assert (p.cell_count, p.cell_pitch) == (3, 14.8)
    centers = cell_centers(p)
    assert len(centers) == 3
    # Every cell axis is the same distance from the bore axis...
    circumradius = p.cell_pitch / sqrt(3.0)
    for x, y in centers:
        assert (x * x + y * y) ** 0.5 == pytest.approx(circumradius)
    # ...and every pair is exactly one pitch apart.
    for first in range(3):
        for second in range(first + 1, 3):
            (x0, y0), (x1, y1) = centers[first], centers[second]
            side = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            assert side == pytest.approx(p.cell_pitch)
    assert p.pack_circumdiameter == pytest.approx(31.5896, abs=1e-3)
    # The user set the single-side bore clearance to 2 mm.
    assert (p.bore_diameter - p.pack_circumdiameter) / 2.0 == pytest.approx(
        2.005, abs=1e-3
    )
    with pytest.raises(ValueError, match="does not fit the bore"):
        replace(p, bore_diameter=31.0)


def test_all_sixteen_cover_extension_holes_carry_an_m3_pilot() -> None:
    """Catch a fastener pattern that no longer uses every side through-hole."""

    p = BatteryGripParameters()
    pilots = mount_pilot_centers(p)
    assert len(pilots) == 16
    assert sorted({x for x, _ in pilots}) == [-59.0, 59.0]
    assert sorted({y for _, y in pilots}) == [
        -35.0,
        -25.0,
        -15.0,
        -5.0,
        5.0,
        15.0,
        25.0,
        35.0,
    ]
    assert p.pilot_diameter == 2.9
    # The flange is one uniform slab, tapped through its full thickness.
    assert p.pilot_depth == p.flange_thickness == 6.0
    # The four Ø6.5 holes are clearance for the cover's own screws, not fasteners.
    assert board_screw_centers(p) == (
        (-50.0, -35.0),
        (-50.0, 35.0),
        (50.0, -35.0),
        (50.0, 35.0),
    )
    assert p.board_screw_clearance_diameter == 6.5


def test_three_cap_posts_take_the_gaps_between_the_cells() -> None:
    """Catch cap posts that collide with a cell or miss the bore wall."""

    p = BatteryGripParameters()
    posts = cap_screw_centers(p)
    assert len(posts) == 3
    bore_radius = p.bore_diameter / 2.0
    post_radius = p.post_diameter / 2.0
    clearance = post_radius + p.cell_diameter / 2.0
    for post_x, post_y in posts:
        # Each post deliberately overlaps the bore wall so the fuse is solid...
        assert p.post_radius + post_radius > bore_radius
        # ...without punching through the outside of the tube.
        assert p.post_radius + post_radius < bore_radius + p.wall_thickness
        for cell_x, cell_y in cell_centers(p):
            assert ((post_x - cell_x) ** 2 + (post_y - cell_y) ** 2) ** 0.5 > clearance
    # Each post is tapped over its full height, so that height is the M3
    # engagement and is independent of the flange thickness.
    assert p.post_height == p.cap_pilot_depth == 5.0
    assert p.cap_pilot_depth >= 5.0
    with pytest.raises(ValueError, match="fuse into the bore wall"):
        replace(p, post_radius=12.0)
    with pytest.raises(ValueError, match="push through the tube wall"):
        replace(p, post_radius=17.5)
    with pytest.raises(ValueError, match="collides with a cell"):
        replace(p, post_diameter=11.0, post_radius=13.0)
    with pytest.raises(ValueError, match="engagement must be at least 5 mm"):
        replace(p, post_height=3.0)
