"""OCP UWB shelf and conservative reference envelopes (millimetres, board frame)."""
import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from bracket.standing_handle import StandingHandleParameters, uwb_hole_centers

BODY_WIDTH = 56.0
BODY_HEIGHT = 46.26
BODY_THICKNESS = 12.0
# Datasheet p43: straight length 85.5 +/-1, distal segment 63, diameter 9.30 +/-0.05.
# The exact hinge axis is not dimensioned. Add 3.5 mm to 85.5-63 axially,
# 1 mm to the horizontal arm, and round the maximum diameter up to 9.4.
ANTENNA_AXIAL_ENVELOPE = 26.0
ANTENNA_ARM_ENVELOPE = 64.0
ANTENNA_RADIUS_ENVELOPE = 4.7


def box(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def cylinder(radius, height, x, y, z, direction=(0, 0, 1)):
    return BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(x, y, z), gp_Dir(*direction)), radius, height).Shape()


def boolean(operation, a, b):
    result = operation(a, b)
    result.Build()
    if not result.IsDone():
        raise RuntimeError(f'{operation.__name__} failed')
    result.SimplifyResult(True, True)
    return result.Shape()


def overlap(a, b):
    return abs(solid_volume(boolean(BRepAlgoAPI_Common, a, b)))


def solid_volume(shape):
    """Adaptive integration avoids STEP-converted spline quadrature drift."""
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, 1e-9, True, False)
    return props.Mass()


def clearance(a, b):
    distance = BRepExtrema_DistShapeShape(a, b)
    distance.Perform()
    if not distance.IsDone():
        raise RuntimeError('Distance computation failed')
    return distance.Value()


def add_uwb_shelf(baseline, p: StandingHandleParameters):
    """Add the same shelf as the FreeCAD source to a frozen original handle STEP."""
    half, y0, z = p.uwb_shelf_width/2, p.flange_width/2, p.flange_z0
    end, t = y0+p.uwb_shelf_projection, p.flange_thickness
    shelf = box(-half, y0, z, 2*half, p.uwb_shelf_projection, t)
    r = p.uwb_shelf_corner_radius
    for side in (-1, 1):
        corner = box(half-r if side > 0 else -half, end-r, z, r, r, t)
        circle = cylinder(r, t, side*(half-r), end-r, z)
        shelf = boolean(BRepAlgoAPI_Cut, shelf, boolean(BRepAlgoAPI_Cut, corner, circle))
    r = p.uwb_shelf_root_radius
    for side in (-1, 1):
        square = box(half if side > 0 else -half-r, y0, z, r, r, t)
        circle = cylinder(r, t, side*(half+r), y0+r, z)
        shelf = boolean(BRepAlgoAPI_Fuse, shelf, boolean(BRepAlgoAPI_Cut, square, circle))
    result = boolean(BRepAlgoAPI_Fuse, baseline, shelf)
    for x, y in uwb_hole_centers(p):
        result = boolean(BRepAlgoAPI_Cut, result,
                         cylinder(p.uwb_hole_diameter/2, t+.2, x, y, z-.1))
    return result


def make_uwb_reference(p: StandingHandleParameters):
    """Conservative full bounding box including SMA; thread depth is not modelled."""
    y = uwb_hole_centers(p)[0][1]
    return box(-BODY_WIDTH/2, y-BODY_THICKNESS/2, p.flange_z0-BODY_HEIGHT,
               BODY_WIDTH, BODY_THICKNESS, BODY_HEIGHT)


def make_antenna_envelope(p: StandingHandleParameters, bend_deg=90):
    """Conservative elbow envelope; +Y is forward, 0=straight down, 90=forward."""
    if not math.isfinite(bend_deg) or not 0 <= bend_deg <= 90:
        raise ValueError('Antenna bend must be between 0 and 90 degrees')
    y, z = uwb_hole_centers(p)[0][1], p.flange_z0-BODY_HEIGHT
    pivot_z = z-ANTENNA_AXIAL_ENVELOPE
    r = ANTENNA_RADIUS_ENVELOPE
    stem = cylinder(r, ANTENNA_AXIAL_ENVELOPE, 0, y, z, (0, 0, -1))
    a = math.radians(bend_deg)
    arm = cylinder(r, ANTENNA_ARM_ENVELOPE, 0, y, pivot_z,
                   (0, math.sin(a), -math.cos(a)))
    elbow = BRepPrimAPI_MakeSphere(gp_Pnt(0, y, pivot_z), r).Shape()
    return boolean(BRepAlgoAPI_Fuse, boolean(BRepAlgoAPI_Fuse, stem, elbow), arm)
