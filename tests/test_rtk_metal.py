"""Real-solid checks for the thin, open metal-print variant."""
import json
import math
from pathlib import Path

import pytest
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN, TopAbs_OUT, TopAbs_SOLID
from OCP.gp import gp_Pnt

from bracket import rtk_geometry as h

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def model():
    from bracket.rtk_metal import build_metal_mount
    params = json.loads((ROOT / 'reports/rtk_mount_v6_parameters.json').read_text())
    original = h.read_step(ROOT / 'step/rtk_antenna_mount_v6.step')
    shape, top = build_metal_mount(params)
    return shape, top, original


def state(shape, x, y, z):
    return BRepClass3d_SolidClassifier(shape, gp_Pnt(x, y, z), 1e-6).State()


def test_open_top_is_two_mm_thick_with_three_usable_holes(model):
    shape, top, _ = model
    assert BRepCheck_Analyzer(shape).IsValid()
    assert h.count(shape, TopAbs_SOLID) == 1
    assert h.count(top, TopAbs_SOLID) == 1
    assert h.bounds(top)['min'][2] == pytest.approx(80.618599, abs=1e-6)
    assert h.bounds(top)['max'][2] == pytest.approx(82.618599, abs=1e-6)
    # Three holes rotate 30 degrees so the posts and holes alternate every 60 degrees.
    for x, y in [(11.5, 6.6395280957), (-11.5, 6.6395280957), (0, -13.2790561914)]:
        assert state(shape, x, y, 81.618599) == TopAbs_OUT
        radial = math.hypot(x, y)
        assert state(shape, x + 3*x/radial, y + 3*y/radial, 81.618599) == TopAbs_IN
        assert state(shape, x + 3*x/radial, y + 3*y/radial, 79.618599) == TopAbs_OUT
        # Nominal Ø6 screw-head access below the mounting pad.
        for angle in range(0, 360, 30):
            assert state(shape, x + 3*math.cos(math.radians(angle)),
                         y + 3*math.sin(math.radians(angle)), 79.5) == TopAbs_OUT
    for x, y in [(0, 0), (20, 0), (0, 20), (-20, 0), (0, -20)]:
        assert state(shape, x, y, 81.618599) == TopAbs_OUT
    # The circular link must remain continuous between the screw pads.
    assert state(shape, 0, 13.2790561914, 81.618599) == TopAbs_IN
    assert state(shape, 13.2790561914, 0, 81.618599) == TopAbs_IN
    assert state(shape, -13.2790561914, 0, 81.618599) == TopAbs_IN
    for x in [4, 8, 12, 15, 17]:
        for y in [-16, -12, -8, -4, 0, 4, 8, 12, 16]:
            assert state(top, x, y, 81.618599) == state(top, -x, y, 81.618599)


def test_two_thin_ears_have_equal_m3_clearance_holes_for_bolt_and_nut(model):
    shape, _, _ = model
    for side in [-1, 1]:
        assert state(shape, side*1.5, -30.94, 37.65) == TopAbs_OUT
        assert state(shape, side*1.5, -29.34, 37.65) == TopAbs_OUT
        assert state(shape, side*1.5, -29.14, 37.65) == TopAbs_IN
        assert state(shape, side*3.2, -28.74, 37.65) == TopAbs_OUT
    assert state(shape, 0, -30.94, 37.65) == TopAbs_OUT


def test_clamp_is_thinner_rounded_and_bolt_tools_have_axial_access(model):
    shape, _, original = model
    assert h.volume(shape) < 0.65 * h.volume(original)
    assert state(shape, 26.6, 0, 36.25) == TopAbs_IN
    assert state(shape, 28, 0, 36.25) == TopAbs_OUT
    assert state(shape, 25, 0, 36.25) == TopAbs_OUT
    assert state(shape, 0, 0, 36.25) == TopAbs_OUT
    assert state(shape, 6.9, -38.9, 37.65) == TopAbs_OUT
    # User-specified Ø6 nut plus 0.5 mm radial rotation allowance: Ø7 envelope.
    for x in [-4, -8, -15, 4, 8, 15]:
        for angle in range(0, 360, 30):
            assert state(shape, x, -30.94 + 3.5*math.cos(math.radians(angle)),
                         37.65 + 3.5*math.sin(math.radians(angle))) == TopAbs_OUT


def test_original_inward_core_is_retained_with_extra_outer_material(model):
    shape, _, _ = model
    for angle in [90, 210, 330]:
        a = math.radians(angle)
        assert state(shape, 27.09541945*math.cos(a), 27.09541945*math.sin(a), 50) == TopAbs_IN
        assert state(shape, 30*math.cos(a), 30*math.sin(a), 50) == TopAbs_IN
        assert state(shape, 25.4*math.cos(a), 25.4*math.sin(a), 50) == TopAbs_OUT
        assert state(shape, 25.2*math.cos(a), 25.2*math.sin(a), 36) == TopAbs_OUT
        # Material spreads to both sides along the collar's circumference.
        for side in [-1, 1]:
            x = 27.75*math.cos(a)-side*1.8*math.sin(a)
            y = 27.75*math.sin(a)+side*1.8*math.cos(a)
            assert state(shape, x, y, 36.5) == TopAbs_IN
            # The red sketch calls for long, broad shoulders, beyond a small fillet.
            for u, radial in [(side*4, 29.0), (side*6, 27.4)]:
                x = radial*math.cos(a)-u*math.sin(a)
                y = radial*math.sin(a)+u*math.cos(a)
                assert state(shape, x, y, 36.5) == TopAbs_IN
