"""Check the selected artifacts and optical data without loading a CAD kernel."""
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def read_report(name):
    return json.loads((ROOT / 'reports' / name).read_text(encoding='utf-8'))


def test_selected_artifacts_and_reports_refer_to_the_same_step():
    selection = read_report('rtk_mount_v6_selection.json')
    assert selection['selected_version'] == 'V6'
    assert selection['design_approved_by_user'] is True
    for relative in selection['key_files']:
        assert (ROOT / relative).is_file(), relative

    step = ROOT / 'step/rtk_antenna_mount_v6.step'
    sha = hashlib.sha256(step.read_bytes()).hexdigest()
    optical = read_report('rtk_scan_occlusion_v6_20261028.json')
    display = read_report('rtk_shadow_3d_v6_20261028.json')
    assert optical['v6_step_sha256'] == display['source_step_sha256'] == sha
    assert display['data_mask_key'] == 'v6_mask'
    assert (ROOT / display['html']).is_file()
    geometry = read_report('rtk_mount_review_v6_20261028.json')
    assert geometry['parameters'] == read_report('rtk_mount_v6_parameters.json')
    assert geometry['mount_solid_count'] == 1


def test_committed_ray_data_matches_both_report_and_display():
    report = read_report('rtk_scan_occlusion_v6_20261028.json')
    display = read_report('rtk_shadow_3d_v6_20261028.json')
    with np.load(ROOT / 'reports/rtk_mount_v6_angular_shadow.npz') as data:
        weights = np.diff(np.sin(np.deg2rad(data['elevation_edges_deg'])))[:, None]
        for version in ['v5', 'v6']:
            mask = data[version + '_mask']
            percentage = float(((mask > 0) * weights).sum() / (weights.sum() * mask.shape[1]) * 100)
            expected = report['versions'][version]['fine_result']['blocked_solid_angle_percent']
            assert abs(percentage - expected) < 1e-9
            if version == 'v6':
                assert percentage <= 8
                assert not np.any((mask == 2) | (mask == 4))
                assert abs(percentage - display['render_data_percent']) < 1e-9

    assert 0 < report['criteria']['analytic_tray_clearance_mm'] <= 1
    assert all(run['blocked_solid_angle_percent'] <= 8 for run in report['versions']['v6']['runs'])
    boundary = report['upper_boundary_52deg_hits_by_class']['v6']
    assert boundary['2'] == boundary['4'] == 0
