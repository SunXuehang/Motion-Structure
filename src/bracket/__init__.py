"""Pure-Python dimensions and motion helpers for the MID-360 tilt bracket."""

from .kinematics import arc_point_yz, transform_yz_about_pivot
from .parameters import BracketParameters, DerivedDimensions, derive

__all__ = [
    "BracketParameters",
    "DerivedDimensions",
    "arc_point_yz",
    "derive",
    "transform_yz_about_pivot",
]
