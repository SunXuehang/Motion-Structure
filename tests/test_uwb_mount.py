"""Check real UWB shelf holes and preservation of the existing standing handle."""
from dataclasses import replace
from pathlib import Path

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN, TopAbs_OUT, TopAbs_SOLID
from OCP.gp import gp_Pnt

from bracket import rtk_geometry as h
from bracket.standing_handle import StandingHandleParameters

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def model():
    from bracket.uwb_mount import add_uwb_shelf
    p = StandingHandleParameters()
    baseline = h.read_step(ROOT / 'tests/standing_handle_baseline_20261117.step')
    return p, baseline, add_uwb_shelf(baseline, p)


def state(shape, x, y, z):
    return BRepClass3d_SolidClassifier(shape, gp_Pnt(x, y, z), 1e-6).State()


def test_shelf_has_two_twelve_mm_pitch_clearance_holes(model):
    p, baseline, shape = model
    assert BRepCheck_Analyzer(shape).IsValid()
    assert h.count(shape, TopAbs_SOLID) == 1
    assert h.bounds(shape)['max'][1] == pytest.approx(59)
    assert h.bounds(shape)['size'][2] == pytest.approx(118)
    for x in [-6, 6]:
        for z in [-11.4, -8.5, -5.6]:
            assert state(shape, x, 51, z) == TopAbs_OUT
            assert state(shape, x+1.6, 51, z) == TopAbs_OUT
            assert state(shape, x+1.8, 51, z) == TopAbs_IN
    assert state(shape, 0, 58, -8.5) == TopAbs_IN
    assert state(shape, 17, 39.2, -8.5) == TopAbs_IN
    assert state(shape, 17, 43.2, -8.5) == TopAbs_OUT


def test_extension_preserves_original_handle_and_legacy_interfaces(model):
    p, baseline, shape = model
    assert abs(h.volume(BRepAlgoAPI_Cut(baseline, shape).Shape())) < 1e-3
    assert h.bounds(shape)['min'] == h.bounds(baseline)['min']
    for x, y, z in [(59, 35, -8), (50, 35, -8), (0, 0, -50), (0, 34, -120)]:
        assert state(shape, x, y, z) == state(baseline, x, y, z) == TopAbs_OUT


def test_uwb_holes_cannot_run_off_the_shelf():
    p = StandingHandleParameters()
    with pytest.raises(ValueError, match='UWB'):
        replace(p, uwb_shelf_projection=10)
    with pytest.raises(ValueError, match='UWB'):
        replace(p, uwb_shelf_width=12)


def test_folded_antenna_is_clear_but_straight_antenna_reaches_below_floor(model):
    from bracket.uwb_mount import make_uwb_reference, make_antenna_envelope, overlap, clearance
    p, _, handle = model
    body = make_uwb_reference(p)
    folded = make_antenna_envelope(p, bend_deg=90)
    straight = make_antenna_envelope(p, bend_deg=0)
    assert overlap(handle, body) < 1e-3
    assert overlap(handle, folded) < 1e-3
    assert clearance(handle, folded) > 15
    assert h.bounds(folded)['min'][2] - p.base_z0 > 35
    assert h.bounds(straight)['min'][2] < p.base_z0


def test_roundtrip_preserves_curved_metal_reference_with_adaptive_volume():
    from bracket.uwb_mount import solid_volume
    from OCP.TopoDS import TopoDS_Iterator
    def part(path, index):
        assembly = h.read_step(path)
        iterator = TopoDS_Iterator(assembly)
        for _ in range(index):
            iterator.Next()
        return iterator.Value()
    original = part(ROOT/'step/standing_device_with_rtk_v6_metal.step', 6)
    exported = part(ROOT/'step/standing_device_with_uwb.step', 6)
    assert solid_volume(exported) == pytest.approx(solid_volume(original), rel=1e-6, abs=1e-3)
