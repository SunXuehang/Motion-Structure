"""Unit checks for the cylindrical battery-grip dimensions and derived chain."""

from dataclasses import replace
from math import pi, sqrt

import pytest

try:
    from bracket.battery_grip import (
        PACK_HEIGHT_MM,
        PACK_TRIANGLE_SIDE_MM,
        BatteryGripParameters,
        board_screw_centers,
        cap_screw_centers,
        mount_hole_centers,
        pack_vertices,
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


def test_cylinder_is_bore_44_wall_3_outer_50() -> None:
    """Catch a bore or wall change that silently moves the grip diameter."""

    p = BatteryGripParameters()
    assert (p.bore_diameter, p.wall_thickness) == (44.0, 3.0)
    assert p.tube_outer_diameter == pytest.approx(50.0)
    assert p.grip_circumference == pytest.approx(pi * 50.0)


def test_derived_z_chain_stacks_flange_root_tube_and_cap() -> None:
    """Catch a broken Z chain that would float or bury the grip."""

    p = BatteryGripParameters()
    assert (p.root_z0, p.grip_z0) == (-25.5, -124.5)
    assert (p.pack_z0, p.pack_z1) == (-119.5, -41.5)
    assert (p.cap_z0, p.total_height) == (-128.5, 123.0)
    assert p.plenum_height == pytest.approx(36.0)
    assert p.window_center_z == pytest.approx(-34.5)


def test_bore_has_no_top_lid_so_the_cover_closes_it() -> None:
    """Catch a re-introduced top lid, or a pack growing into the cover."""

    p = BatteryGripParameters()
    # The pack stops below the cover underside; the plenum is the fan's path.
    assert p.pack_z1 < p.cover_underside_z
    assert p.plenum_height > 0.0
    with pytest.raises(ValueError, match="pack reaches the lower cover"):
        replace(p, pack_height=200.0)


def test_triangular_prism_pack_fits_the_bore_with_clearance() -> None:
    """Catch a pack that stops being an equilateral triangle or outgrows the bore."""

    p = BatteryGripParameters()
    assert (p.pack_side, p.pack_height) == (PACK_TRIANGLE_SIDE_MM, PACK_HEIGHT_MM)
    vertices = pack_vertices(p)
    assert len(vertices) == 3
    # Every vertex is the same distance from the bore axis...
    circumradius = p.pack_side / sqrt(3.0)
    for x, y in vertices:
        assert (x * x + y * y) ** 0.5 == pytest.approx(circumradius)
    # ...and every pair is exactly one side apart.
    for first in range(3):
        for second in range(first + 1, 3):
            (x0, y0), (x1, y1) = vertices[first], vertices[second]
            side = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            assert side == pytest.approx(p.pack_side)
    assert p.pack_circumdiameter == pytest.approx(41.569, abs=1e-3)
    # The Ø44 bore leaves 1.215 mm of radial clearance per side.
    assert (p.bore_diameter - p.pack_circumdiameter) / 2.0 == pytest.approx(
        1.215, abs=1e-3
    )
    with pytest.raises(ValueError, match="does not fit the bore"):
        replace(p, bore_diameter=40.0)


def test_all_sixteen_cover_extension_holes_carry_an_m3_through_hole() -> None:
    """Catch a fastener pattern that no longer uses every side through-hole."""

    p = BatteryGripParameters()
    centers = mount_hole_centers(p)
    assert len(centers) == 16
    assert sorted({x for x, _ in centers}) == [-59.0, 59.0]
    assert sorted({y for _, y in centers}) == [
        -35.0,
        -25.0,
        -15.0,
        -5.0,
        5.0,
        15.0,
        25.0,
        35.0,
    ]
    # The flange holes are plain Ø3.4 clearance, the same size as the lower
    # cover's extension holes: an M3 passes both plates freely.
    assert p.mount_hole_diameter == 3.4
    # The hole cuts clean through the one uniform 6 mm flange slab.
    assert p.mount_hole_depth == p.flange_thickness == 6.0
    # The four Ø6.5 holes are clearance for the cover's own screws, not fasteners.
    assert board_screw_centers(p) == (
        (-50.0, -35.0),
        (-50.0, 35.0),
        (50.0, -35.0),
        (50.0, 35.0),
    )
    assert p.board_screw_clearance_diameter == 6.5


def test_three_cap_posts_fuse_into_the_bore_wall() -> None:
    """Catch cap posts that miss the bore wall or punch through the tube."""

    p = BatteryGripParameters()
    posts = cap_screw_centers(p)
    assert len(posts) == 3
    assert p.post_radius == 20.0
    bore_radius = p.bore_diameter / 2.0
    post_radius = p.post_diameter / 2.0
    for _post_x, _post_y in posts:
        # Each post deliberately overlaps the bore wall so the fuse is solid...
        assert p.post_radius + post_radius > bore_radius
        # ...without punching through the outside of the tube.
        assert p.post_radius + post_radius < bore_radius + p.wall_thickness
    # The pack seats on the post tops, so no angular clearance to the posts
    # is needed: the pack bottom plane is the post top plane.
    assert p.pack_z0 == p.grip_z0 + p.post_height
    # Each post is tapped over its full height from a Ø2.9 pilot, so that
    # height is the M3 engagement and is independent of the flange thickness.
    assert p.cap_pilot_diameter == 2.9
    assert p.post_height == p.cap_pilot_depth == 5.0
    assert p.cap_pilot_depth >= 5.0
    with pytest.raises(ValueError, match="fuse into the bore wall"):
        replace(p, post_radius=18.0)
    with pytest.raises(ValueError, match="push through the tube wall"):
        replace(p, post_radius=22.0)
    with pytest.raises(ValueError, match="engagement must be at least 5 mm"):
        replace(p, post_height=3.0)


def test_window_keeps_a_plain_wall_band_above_the_pack() -> None:
    """Catch a pack so tall the DC-lead window loses its plain wall."""

    p = BatteryGripParameters()
    # The band between the pack top and the cone fits the window with 2.5 mm
    # of plain wall above it and 0.5 mm below.
    assert p.root_z0 - p.pack_z1 == pytest.approx(16.0)
    assert p.root_z0 - p.pack_z1 > p.window_height
    top_gap = p.root_z0 - (p.window_center_z + p.window_height / 2.0)
    assert top_gap == pytest.approx(p.window_top_gap)
    bottom_gap = (p.window_center_z - p.window_height / 2.0) - p.pack_z1
    assert bottom_gap == pytest.approx(0.5)
    with pytest.raises(ValueError, match="no plain wall band"):
        replace(p, pack_height=95.0)
