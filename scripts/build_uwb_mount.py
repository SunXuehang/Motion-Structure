"""Build the approved UWB handle, check conservative envelopes, export and render."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopoDS import TopoDS_Iterator

from bracket import rtk_geometry as h
from bracket.rendering import _shaded_faces
from bracket.standing_handle import StandingHandleParameters, uwb_hole_centers
from bracket.uwb_mount import (add_uwb_shelf, make_uwb_reference, make_antenna_envelope,
    cylinder, overlap, clearance, solid_volume, BODY_WIDTH, BODY_HEIGHT, BODY_THICKNESS,
    ANTENNA_AXIAL_ENVELOPE, ANTENNA_ARM_ENVELOPE, ANTENNA_RADIUS_ENVELOPE)

BASELINE = ROOT / 'tests/standing_handle_baseline_20261117.step'
ASSEMBLY = ROOT / 'step/standing_device_with_rtk_v6_metal.step'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def children(shape):
    iterator, parts = TopoDS_Iterator(shape), []
    while iterator.More():
        parts.append(iterator.Value())
        iterator.Next()
    return parts


def mesh(shape):
    vertices, triangles, _ = h.mesh(shape, deflection=.28, angular=.28)
    return vertices, triangles


def add_scene(axis, meshes, colors):
    faces = [v[t] for v, t in meshes]
    axis.add_collection3d(Poly3DCollection(np.concatenate(faces),
        facecolors=np.concatenate([_shaded_faces(f, c) for f, c in zip(faces, colors)]),
        linewidth=0, edgecolors='none', zsort='average'))


def render(parts, p, report):
    fonts = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    plt.rcParams['font.family'] = [f for f in ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'] if f in fonts]
    plt.rcParams['axes.unicode_minus'] = False
    meshes = [mesh(s) for s in parts]
    colors = ['#d39862', '#7799b0', '#b3c8d1', '#96afbb', '#547990',
              '#a5b1b8', '#289b98', '#d5a04a', '#ebaa47', '#3b4650']
    fig = plt.figure(figsize=(22, 13), dpi=130, facecolor='#f6f8fa')
    fig.text(.04, .945, '手柄前伸 UWB 托耳 · LinkTrack P-A', fontsize=27, weight='bold', color='#243f50')
    fig.text(.04, .902, '一体打印托耳 32 × 20 × 6 mm   /   2 × Ø3.4，孔距 12 mm   /   手柄总高仍为 118 mm',
             fontsize=16, color='#536f7e')

    ax = fig.add_axes([.015, .15, .39, .72], projection='3d', facecolor='#f6f8fa')
    add_scene(ax, meshes, colors)
    ax.set(xlim=(-80, 80), ylim=(-65, 130), zlim=(-130, 205))
    ax.set_box_aspect((160, 195, 335), zoom=1.03)
    ax.view_init(elev=15, azim=53)
    ax.set_proj_type('ortho')
    ax.set_axis_off()
    fig.text(.06, .84, '整机装配 · 当前金属 RTK 支架', fontsize=16, color='#36596e')

    detail = fig.add_axes([.38, .36, .33, .48], projection='3d', facecolor='#eef3f6')
    selection = [4, 8, 9]
    add_scene(detail, [meshes[i] for i in selection], [colors[i] for i in selection])
    detail.set(xlim=(-70, 70), ylim=(-45, 120), zlim=(-130, 0))
    detail.set_box_aspect((140, 165, 130), zoom=1.05)
    detail.view_init(elev=27, azim=52)
    detail.set_proj_type('ortho')
    detail.set_axis_off()
    fig.text(.40, .84, '安装细节 · UWB 在托耳下方', fontsize=16, color='#36596e')
    fig.text(.40, .29, '橙色：UWB 壳体保守包络\n深灰：向 +Y 前方折弯 90° 的天线包络\n机身后缘距圆筒名义外壁 24 mm',
             fontsize=13, color='#526d7b', linespacing=1.8, va='top')

    side = fig.add_axes([.735, .37, .24, .44], facecolor='#eef3f6')
    for i in selection:
        v, t = meshes[i]
        side.add_collection(PolyCollection(v[t][:, :, [1, 2]],
            facecolors=colors[i], edgecolors='none', linewidth=0, alpha=.95))
    side.axhline(p.base_z0, color='#536772', linewidth=2)
    bottom = report['folded_antenna_floor_clearance_mm'] + p.base_z0
    side.annotate('', xy=(124, p.base_z0), xytext=(124, bottom),
                  arrowprops={'arrowstyle': '<->', 'color': '#147b75', 'lw': 1.6})
    side.text(128, (p.base_z0+bottom)/2, f"{report['folded_antenna_floor_clearance_mm']:.1f} mm",
              fontsize=13, color='#147b75', va='center', rotation=90)
    side.text(5, p.base_z0-8, '桌面 / 支脚底面', fontsize=11, color='#536772', ha='center')
    side.set(xlim=(-52, 145), ylim=(-137, 2), xlabel='前后 Y (mm)', ylabel='高度 Z (mm)')
    side.set_aspect('equal')
    side.grid(alpha=.16)
    side.spines[['top', 'right']].set_visible(False)
    fig.text(.745, .84, '侧视：折弯后离桌间隙', fontsize=16, color='#36596e')
    fig.text(.745, .29, f"天线与手柄最短几何距离\n{report['folded_antenna_to_handle_clearance_mm']:.1f} mm",
             fontsize=15, color='#147b75', linespacing=1.8, va='top')

    fig.text(.04, .103, '依据导出 STEP 绘制。UWB 和天线为官方尺寸构建的参考包络，非厂商精确 CAD；螺钉未显示。',
             fontsize=13, color='#5e7584')
    fig.text(.04, .068, '天线包络：轴向 26 mm + 折弯臂 64 mm，Ø9.4 mm；已增加尺寸余量，精确铰链尺寸仍需实物核验。',
             fontsize=13, color='#5e7584')
    fig.text(.04, .033, '几何检查不代表抗倾覆、打印强度或 UWB 通信性能验证；相机、开发板、线缆和紧固件实体未纳入整机参考。',
             fontsize=12, color='#71848f')
    output = ROOT / 'renders/standing_handle_uwb.png'
    fig.savefig(output, facecolor=fig.get_facecolor(), dpi=130)
    plt.close(fig)

    # A separate close view exposes both clearance holes instead of hiding them under the unit.
    fig = plt.figure(figsize=(12, 8), dpi=150, facecolor='#f6f8fa')
    top = fig.add_axes([.02, .17, .65, .70], projection='3d', facecolor='#f6f8fa')
    v, t = meshes[4]
    visible = v[t].min(axis=1)[:, 2] > p.flange_z0-.01
    add_scene(top, [(v, t[visible])], [colors[4]])
    top.set(xlim=(-29, 29), ylim=(30, 64), zlim=(-12, -3))
    top.set_box_aspect((58, 34, 9), zoom=1.10)
    top.view_init(elev=54, azim=60)
    top.set_proj_type('ortho')
    top.set_axis_off()
    top.plot([-6, 6], [51, 51], [-5.35, -5.35], color='#df8f28', lw=2)
    fig.text(.05, .92, '托耳与 M3 安装孔 · 无设备遮挡', fontsize=23, color='#243f50', weight='bold')
    fig.text(.70, .75, '宽 32 mm\n前伸 20 mm\n厚 6 mm\n\n2 × Ø3.4 通孔\n孔距 12 mm\n根部 R4',
             fontsize=17, color='#446575', va='top', linespacing=1.7)
    fig.text(.05, .10, '孔轴坐标 (±6, 51) mm；从托耳上方穿入 M3 螺钉，连接 UWB 自带螺孔。', fontsize=13, color='#5e7584')
    fig.text(.05, .05, '螺钉长度须按设备实际螺纹深度选择，官方尺寸图未标注有效啮合深度。', fontsize=12, color='#71848f')
    fig.savefig(ROOT / 'renders/uwb_shelf_detail.png', facecolor=fig.get_facecolor(), dpi=150)
    plt.close(fig)


def main():
    p = StandingHandleParameters()
    baseline = h.read_step(BASELINE)
    handle = add_uwb_shelf(baseline, p)
    assert BRepCheck_Analyzer(handle).IsValid() and h.count(handle, TopAbs_SOLID) == 1
    assert abs(h.volume(BRepAlgoAPI_Cut(baseline, handle).Shape())) < 1e-3
    assert h.bounds(handle)['size'][2] == p.total_height == 118
    parts = children(h.read_step(ASSEMBLY))
    assert len(parts) == 8
    assert h.bounds(parts[4]) == h.bounds(baseline)
    assert abs(h.volume(BRepAlgoAPI_Cut(parts[4], baseline).Shape())) < 1e-3
    parts[4] = handle
    body = make_uwb_reference(p)
    antenna = make_antenna_envelope(p)
    names = ['radar_plate', 'tilt_base', 'upper_cover', 'lower_cover', 'standing_handle',
             'MID360', 'metal_RTK_mount', 'GNSS_antenna']
    collisions = []
    for name, part in zip(names, parts):
        for reference_name, reference in [('uwb_body', body), ('antenna_90deg', antenna)]:
            value = overlap(part, reference)
            assert value < 1e-3, (name, reference_name, value)
            collisions.append({'part': name, 'reference': reference_name, 'overlap_mm3': value,
                               'distance_mm': clearance(part, reference)})
    sweep = []
    for angle in range(0, 91, 5):
        reference = make_antenna_envelope(p, angle)
        value = overlap(handle, reference)
        assert value < 1e-3, (angle, value)
        sweep.append({'bend_deg': angle, 'handle_overlap_mm3': value,
                      'floor_clearance_mm': h.bounds(reference)['min'][2]-p.base_z0})
    screw_checks = []
    for x, y in uwb_hole_centers(p):
        shaft = cylinder(1.5, p.flange_thickness, x, y, p.flange_z0)
        tool = cylinder(3.2, 20, x, y, p.cover_underside_z+.01)
        assert overlap(handle, shaft) < 1e-3
        maximum = max(overlap(part, tool) for part in parts)
        assert maximum < 1e-3
        screw_checks.append({'xy_mm': [x, y], 'shaft_diameter_mm': 3,
                             'above_shelf_tool_envelope_diameter_mm': 6.4,
                             'above_shelf_access_height_mm': 20, 'maximum_overlap_mm3': maximum})
    floor_clearance = h.bounds(antenna)['min'][2]-p.base_z0
    assert floor_clearance > 35
    destinations = {'canonical_handle': ROOT/'step/standing_handle_body.step',
                    'print_handle': ROOT/'exports/standing_handle_uwb.step',
                    'assembly': ROOT/'step/standing_device_with_uwb.step'}
    h.export_compound([handle], destinations['canonical_handle'])
    print_handle = h.placed(handle, y=-7.5, z=-p.base_z0)
    h.export_compound([print_handle], destinations['print_handle'])
    h.export_compound(parts+[body, antenna], destinations['assembly'])
    reread = h.read_step(destinations['canonical_handle'])
    assert abs(h.volume(reread)-h.volume(handle)) < .01
    reread_print = h.read_step(destinations['print_handle'])
    assert abs(h.volume(reread_print)-h.volume(handle)) < .01
    assert h.bounds(reread_print)['min'][2] == 0
    assembly_parts = children(h.read_step(destinations['assembly']))
    assert len(assembly_parts) == 10
    assert h.bounds(assembly_parts[4]) == h.bounds(handle)
    original_parts = children(h.read_step(ASSEMBLY))
    preserved_parts = []
    for i in [0, 1, 2, 3, 5, 6, 7]:
        assert h.bounds(assembly_parts[i]) == h.bounds(original_parts[i])
        delta = abs(solid_volume(assembly_parts[i])-solid_volume(original_parts[i]))
        assert delta < .001, (names[i], delta)
        assert h.count(assembly_parts[i], TopAbs_SOLID) == h.count(original_parts[i], TopAbs_SOLID)
        preserved_parts.append({'part': names[i], 'adaptive_closed_shell_volume_delta_mm3': delta,
                                'bounds_preserved': True, 'solid_count_preserved': True})
    report = {'design_approved_by_user': True, 'date': '2026-11-17', 'units': 'mm',
        'source_baseline_step': str(BASELINE.relative_to(ROOT)), 'source_baseline_sha256': sha(BASELINE),
        'source_metal_assembly_sha256': sha(ASSEMBLY), 'handle_parameters': asdict(p),
        'shelf_dimensions_mm': [p.uwb_shelf_width, p.uwb_shelf_projection, p.flange_thickness],
        'hole_axes_board_xy_mm': uwb_hole_centers(p), 'handle_height_mm': p.total_height,
        'handle_bounds_board_mm': h.bounds(reread), 'handle_solid_count': h.count(reread, TopAbs_SOLID),
        'print_export_translation_yz_mm': [-7.5, -p.base_z0], 'print_export_bounds_mm': h.bounds(reread_print),
        'assembly_part_count': len(assembly_parts), 'assembly_solid_count': h.count(h.read_step(destinations['assembly']), TopAbs_SOLID),
        'uwb_reference_body_dimensions_mm': [BODY_WIDTH, BODY_HEIGHT, BODY_THICKNESS],
        'antenna_reference': {'fold_deg': 90, 'fold_direction': '+Y forward',
            'axial_envelope_mm': ANTENNA_AXIAL_ENVELOPE, 'arm_envelope_mm': ANTENNA_ARM_ENVELOPE,
            'diameter_envelope_mm': 2*ANTENNA_RADIUS_ENVELOPE,
            'basis': 'Datasheet p43: 85.5 +/-1 mm total, 63 mm arm, diameter 9.30 +/-0.05 mm. Axial 26 adds 3.5 mm to 85.5-63; arm adds 1 mm; diameter rounded up.',
            'uncertainty': 'Exact hinge axis, connector seating and rotating joint shape are not fully dimensioned; conservative reference envelope is not certified manufacturer CAD.'},
        'folded_antenna_floor_clearance_mm': floor_clearance,
        'folded_antenna_to_handle_clearance_mm': clearance(handle, antenna),
        'uwb_body_to_grip_nominal_y_gap_mm': uwb_hole_centers(p)[0][1]-BODY_THICKNESS/2-p.grip_outer_diameter/2,
        'pairwise_new_vs_existing': collisions, 'bend_sweep': sweep, 'screw_access': screw_checks,
        'preserved_assembly_parts': preserved_parts,
        'step_roundtrip_valid': True,
        'sources': ['https://ftp.nooploop.com/downloads/linktrack/LinkTrack_Datasheet_V2.3_zh.pdf#page=43',
                    'https://ftp.nooploop.com/downloads/linktrack/LinkTrack_Datasheet_V2.3_zh.pdf#page=44'],
        'limitations': ['UWB and antenna are reference envelopes, not official detailed CAD.',
            'M3 engagement depth is unspecified; choose screw length after measuring actual device.',
            'No physical print/assembly, mechanical strength, tipping stability or RF test performed.',
            'The represented assembly excludes camera, compute board, cables and metal fasteners.',
            'The FreeCAD source was updated but cannot be run in this Windows environment; exported models were built and verified using OCP against the preserved original STEP.',
            'Fold the antenna before resting on a table; the straight-down envelope extends below the feet.']}
    render(assembly_parts, p, report)
    report['outputs'] = {name: {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
                         for name, path in destinations.items()}
    for name in ['standing_handle_uwb', 'uwb_shelf_detail']:
        path = ROOT / f'renders/{name}.png'
        report['outputs'][name] = {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
    (ROOT/'reports/uwb_mount_20261117.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['handle_solid_count', 'handle_height_mm',
        'folded_antenna_floor_clearance_mm', 'folded_antenna_to_handle_clearance_mm', 'assembly_solid_count']}, indent=2))


if __name__ == '__main__':
    main()
