from math import isclose

import pytest

from bracket.kinematics import arc_point_yz, transform_yz_about_pivot
from bracket.parameters import BracketParameters


def test_rear_lock_axis_follows_the_r45_arc_to_forty_degrees():
    p = BracketParameters()

    assert arc_point_yz(p, 0.0) == (-12.0, 10.0)
    y, z = arc_point_yz(p, 40.0)
    assert isclose(y, -1.4719999404, abs_tol=1e-9)
    assert isclose(z, 38.9254424359, abs_tol=1e-9)


def test_a_rear_edge_rises_while_front_pivot_stays_fixed():
    p = BracketParameters()

    pivot = transform_yz_about_pivot(p, p.a_pivot_y, p.a_pivot_z, 40.0)
    rear = transform_yz_about_pivot(p, -42.5, 0.0, 40.0)

    assert pivot == (38.0, -3.0)
    assert isclose(rear[0], -21.7382148420, abs_tol=1e-9)
    assert isclose(rear[1], 51.0425359091, abs_tol=1e-9)


@pytest.mark.parametrize("angle", [0.0, 20.0, 40.0])
def test_required_review_angles_align_lock_axis(angle):
    p = BracketParameters()
    y, z = arc_point_yz(p, angle)

    transformed = transform_yz_about_pivot(
        p, p.a_pivot_y - p.lock_radius, p.a_pivot_z, angle
    )

    assert isclose(transformed[0] + p.b_pivot_y - p.a_pivot_y, y, abs_tol=1e-9)
    assert isclose(
        transformed[1] + p.b_base_thickness + p.pivot_z_above_base - p.a_pivot_z,
        z + p.b_base_thickness,
        abs_tol=1e-9,
    )
