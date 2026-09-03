"""Framework-free planar kinematics for the bracket lock axis."""

from math import cos, radians, sin

from .parameters import BracketParameters


def arc_point_yz(p: BracketParameters, angle_deg: float) -> tuple[float, float]:
    """Return the B-frame YZ coordinates of the lock-axis arc at *angle_deg*."""

    angle_rad = radians(angle_deg)
    return (
        p.b_pivot_y - p.lock_radius * cos(angle_rad),
        p.pivot_z_above_base + p.lock_radius * sin(angle_rad),
    )


def transform_yz_about_pivot(
    p: BracketParameters, y: float, z: float, angle_deg: float
) -> tuple[float, float]:
    """Rotate an A-local YZ point around A's pivot by a positive pitch angle."""

    angle_rad = radians(-angle_deg)
    offset_y = y - p.a_pivot_y
    offset_z = z - p.a_pivot_z
    return (
        p.a_pivot_y + offset_y * cos(angle_rad) - offset_z * sin(angle_rad),
        p.a_pivot_z + offset_y * sin(angle_rad) + offset_z * cos(angle_rad),
    )
