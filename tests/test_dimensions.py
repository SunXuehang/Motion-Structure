from dataclasses import FrozenInstanceError
from math import isclose

import pytest

from bracket.parameters import BracketParameters, derive


def test_r50_primary_dimensions_and_side_clearance():
    p = BracketParameters()
    d = derive(p)

    assert (p.a_plate_width, p.a_plate_depth, p.a_plate_thickness) == (
        69.0,
        85.0,
        6.0,
    )
    assert (p.b_base_width, p.b_base_depth, p.b_base_thickness) == (
        128.0,
        78.0,
        4.0,
    )
    assert p.b_inner_width == 69.8
    assert (p.lock_radius, p.sector_outer_radius) == (45.0, 53.0)
    assert (p.a_pivot_y, p.a_pivot_z, p.b_pivot_y) == (38.0, -3.0, 33.0)
    assert p.working_angle_deg == 40.0
    assert p.sector_bridge_length == 4.0
    assert p.sector_pivot_lobe_radius == 6.0
    assert p.track_recess_depth == 1.0
    assert (p.root_rib_extension, p.root_rib_depth, p.root_rib_height) == (
        10.0,
        8.0,
        6.0,
    )
    assert p.root_rib_y_center == 16.0
    assert (p.a_insert_hole_diameter, p.a_insert_hole_depth) == (4.0, 3.0)
    assert isclose(d.main_side_gap, 0.4, abs_tol=1e-9)
    assert isclose(d.plate_base_clearance, 7.0, abs_tol=1e-9)


def test_r50_preserves_the_approved_slot_travel():
    d = derive(BracketParameters())

    assert isclose(d.slot_overrun_deg, 1.909859317103, abs_tol=1e-9)
    assert isclose(d.slot_total_arc_length, 34.415926535898, abs_tol=1e-9)
    assert isclose(d.sector_profile_extension_deg, 9.167324722093, abs_tol=1e-9)
    assert 50.1 < d.sector_top_above_base < 50.2


def test_r50_sector_wall_stays_inside_the_78_mm_top_cover_width():
    p = BracketParameters()

    assert p.b_pivot_y <= 39.0
    assert p.b_pivot_y - p.sector_outer_radius >= -39.0


def test_sensor_mount_pitches_match_the_official_step_evidence():
    p = BracketParameters()

    assert p.sensor_mount_pitch_x == 36.0
    assert p.sensor_mount_pitch_y == 48.0


def test_m3_hole_parameters_preserve_mid360_mounting_holes() -> None:
    p = BracketParameters()

    assert p.a_insert_hole_diameter == 4.0
    assert p.a_insert_hole_depth == 3.0
    assert p.b_clearance_hole_diameter == 3.4
    assert p.b_base_mount_hole_diameter == 3.4
    assert p.slot_width == 3.4
    assert p.sensor_mount_hole_diameter == 3.5


def test_d435i_shelf_and_screw_clearance_parameters() -> None:
    """Catch an unrounded D435i shelf or changed 1/4-20 clearance.

    This fails if the production shelf-corner radius stops protecting the
    required 92 x 20 mm D435i support footprint.
    """

    p = BracketParameters()

    assert (p.d435i_shelf_width, p.d435i_shelf_depth) == (92.0, 20.0)
    assert p.d435i_shelf_corner_radius == 4.0
    assert p.d435i_mount_clearance_diameter == 6.8
    assert p.d435i_screw_shaft_diameter == 6.35
    assert (p.d435i_screw_head_diameter, p.d435i_screw_head_height) == (12.0, 7.0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"sensor_mount_pitch_x": 0.0},
        {"sensor_mount_pitch_x": -0.1},
        {"sensor_mount_pitch_y": 0.0},
        {"sensor_mount_pitch_y": -0.1},
    ],
)
def test_sensor_mount_pitches_reject_non_positive_values(overrides):
    with pytest.raises(ValueError):
        BracketParameters(**overrides)


def test_parameters_are_immutable_after_construction():
    p = BracketParameters()

    with pytest.raises(FrozenInstanceError):
        p.lock_radius = 41.0


@pytest.mark.parametrize(
    "overrides",
    [
        {"working_angle_deg": -0.1},
        {"working_angle_deg": 40.1},
        {"b_inner_width": 69.0},
        {"b_inner_width": 69.6},
        {"a_insert_hole_depth": 40.0},
        {"pivot_z_above_base": 4.9},
        {"sector_outer_radius": 52.9},
        {"track_recess_depth": 4.0},
        {"sector_pivot_lobe_radius": 6.1},
        {"root_rib_extension": 0.0},
        {"root_rib_depth": 0.0},
        {"root_rib_height": 0.0},
        {"root_rib_y_center": 0.0},
        {"a_insert_hole_diameter": 0.0},
        {"a_insert_hole_diameter": -0.1},
        {"b_clearance_hole_diameter": 0.0},
        {"b_clearance_hole_diameter": -0.1},
        {"b_base_mount_hole_diameter": 0.0},
        {"b_base_mount_hole_diameter": -0.1},
        {"sensor_mount_hole_diameter": 0.0},
        {"sensor_mount_hole_diameter": -0.1},
        {"slot_width": 0.0},
        {"slot_width": -0.1},
        {"d435i_shelf_width": 0.0},
        {"d435i_shelf_width": -0.1},
        {"d435i_shelf_depth": 0.0},
        {"d435i_shelf_depth": -0.1},
        {"d435i_shelf_corner_radius": 0.0},
        {"d435i_shelf_corner_radius": -0.1},
        {"d435i_mount_clearance_diameter": 0.0},
        {"d435i_mount_clearance_diameter": -0.1},
        {"d435i_screw_shaft_diameter": 0.0},
        {"d435i_screw_shaft_diameter": -0.1},
        {"d435i_screw_head_diameter": 0.0},
        {"d435i_screw_head_diameter": -0.1},
        {"d435i_screw_head_height": 0.0},
        {"d435i_screw_head_height": -0.1},
    ],
)
def test_invalid_parameter_sets_are_rejected(overrides):
    with pytest.raises(ValueError):
        BracketParameters(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"d435i_shelf_width": 128.1},
        {"d435i_shelf_corner_radius": 10.1},
        {"d435i_mount_clearance_diameter": 6.35},
        {"d435i_screw_head_diameter": 6.8},
        {"d435i_screw_head_height": 20.1},
    ],
)
def test_invalid_d435i_shelf_clearance_relationships_are_rejected(overrides):
    with pytest.raises(ValueError):
        BracketParameters(**overrides)
