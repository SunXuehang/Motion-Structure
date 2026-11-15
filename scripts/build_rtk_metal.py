"""Build and inspect the finalized metal mount without changing original V6 files."""
from pathlib import Path
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import plotly.graph_objects as go
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS, TopoDS_Iterator
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf

from bracket import rtk_geometry as h
from bracket.rendering import _shaded_faces
from bracket.rtk_metal import METAL_PARAMS, build_metal_mount, cylinder, metal_post_geometry
from bracket.rtk_shadow import make_locator, trace


def solid_volume(shape):
    props = GProp_GProps()
    # Adaptive integration is needed for the reinforcement's trimmed spline faces.
    BRepGProp.VolumeProperties_s(shape, props, 1e-9, True, False)
    return props.Mass()


def overlap(a, b):
    operation = BRepAlgoAPI_Common(a, b)
    operation.Build()
    assert operation.IsDone()
    return abs(solid_volume(operation.Shape()))


def verify_contact_pattern(sensor, p):
    """Check the rib pattern against the actual reference sensor, not a cylinder."""
    m = METAL_PARAMS
    low, high = p['clamp_bottom_z_mm'], p['clamp_bottom_z_mm']+p['clamp_contact_height_mm']
    assert p['ring_cad_cylindrical_band_z_mm'][0] <= low < high <= p['ring_cad_cylindrical_band_z_mm'][1]
    grooves = {}
    faces = TopExp_Explorer(sensor, TopAbs_FACE)
    while faces.More():
        face = TopoDS.Face(faces.Current())
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() == GeomAbs_Cylinder:
            c = surface.Cylinder()
            axis, point = c.Axis().Direction(), c.Axis().Location()
            radius, bounds = math.hypot(point.X(), point.Y()), h.bounds(face)
            if (abs(axis.Z()) > .999 and c.Radius() < 2 and 24 < radius < 28
                    and bounds['min'][2] <= low and bounds['max'][2] >= high):
                angle = math.degrees(math.atan2(point.Y(), point.X())) % 360
                grooves[round(angle, 5) % 360] = (radius, c.Radius())
        faces.Next()
    angles = [round((m['contact_groove_phase_deg']+i*360/m['contact_groove_count']) % 360, 5)
              for i in range(m['contact_groove_count'])]
    assert sorted(grooves) == sorted(angles), 'Contact ribs do not match actual MID-360 groove positions'
    assert all(math.isclose(r, m['contact_groove_center_radius_mm'], abs_tol=1e-6)
               and math.isclose(c, m['contact_groove_radius_mm'], abs_tol=1e-6) for r, c in grooves.values())
    return {'official_groove_count': len(grooves), 'angular_pitch_deg': 360/len(grooves),
        'phase_deg': m['contact_groove_phase_deg'], 'groove_center_radius_mm': m['contact_groove_center_radius_mm'],
        'official_groove_radius_mm': m['contact_groove_radius_mm'],
        'rib_radius_mm': m['contact_groove_radius_mm']-m['contact_groove_clearance_mm'],
        'nominal_profile_clearance_mm': m['contact_groove_clearance_mm'], 'rib_z_mm': [low, high],
        'minimum_rib_tip_radius_mm': m['contact_groove_center_radius_mm']-m['contact_groove_radius_mm']+m['contact_groove_clearance_mm'],
        'note': 'Ribs align with the reference sensor recesses. The rear closing slit interrupts one rib; clock the part to the sensor grooves.'}


def contact_preview(shape, sensor):
    from render_rtk_metal_sections import section
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), dpi=160)
    z = 36.5
    for item, color, label in [(shape, '#23918f', '金属支架'), (sensor, '#273e50', 'MID-360 实际外形')]:
        paths = section(item, [0, 0, z], [0, 0, 1])[0]
        for axis in axes:
            for i, path in enumerate(paths):
                axis.plot(path[:, 0], path[:, 1], color=color, linewidth=1.3, label=label if i == 0 else None)
    for axis in axes:
        axis.set_aspect('equal')
        axis.grid(alpha=.2)
        axis.set_xlabel('X (mm)')
        axis.set_ylabel('Y (mm)')
    axes[0].set(xlim=(-33, 33), ylim=(-37, 34), title='接触带水平剖面 · 收紧缝 2.0 mm')
    axes[0].legend(loc='upper right', fontsize=9)
    axes[1].set(xlim=(-3, 3), ylim=(24.7, 27.2), title='内纹与真实凹槽对位 · 名义间隙 0.1 mm')
    fig.suptitle('MID-360 匹配内纹：40 个槽位，间隔 9°；后侧收紧开口处断开', fontsize=16)
    fig.text(.07, .035, '真实 STEP 剖切；凸纹 R0.9 对应雷达凹槽 R1.0，位于 Z=34.25～38.25 mm 接触带。实际紧固效果待试装。', fontsize=11)
    fig.tight_layout(rect=[0, .07, 1, .94])
    fig.savefig(ROOT / 'renders/rtk_metal_mid360_contact.png', facecolor='white')
    plt.close(fig)


def add_mesh(axis, vertices, triangles, color):
    faces = vertices[triangles]
    axis.add_collection3d(Poly3DCollection(faces, facecolors=_shaded_faces(faces, color),
                                         edgecolors='none', linewidth=0, antialiased=False, zsort='average'))


def preview(shape, top, p, report):
    vertices, triangles, _ = h.mesh(shape, deflection=.12, angular=.2)
    top_v, top_t, _ = h.mesh(top, deflection=.06, angular=.15)
    fonts = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    plt.rcParams['font.family'] = [f for f in ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'] if f in fonts]
    plt.rcParams['axes.unicode_minus'] = False
    fig = plt.figure(figsize=(16, 10), dpi=150, facecolor='#f5f7f9')
    fig.text(.045, .94, 'V6 · 金属天线支架定稿', fontsize=27, weight='bold', color='#253e50')
    fig.text(.045, .895, '圆滑加宽柱根  /  收紧缝 2 mm  /  内纹对应 MID-360 接触凹槽', fontsize=15, color='#5b7180')
    ax = fig.add_axes([.015, .125, .55, .73], projection='3d', facecolor='#f5f7f9')
    faces = vertices[triangles]
    colors = _shaded_faces(faces, '#9baeba')
    top_faces = faces.mean(axis=1)[:, 2] >= p['antenna_mount_face_z_mm']-2.001
    colors[top_faces] = _shaded_faces(faces[top_faces], '#2a9996')
    ax.add_collection3d(Poly3DCollection(faces, facecolors=colors, edgecolors='none', linewidth=0, antialiased=False))
    ax.set(xlim=(-34, 34), ylim=(-42, 34), zlim=(30, 87))
    ax.set_box_aspect((68, 73, 57), zoom=1.1)
    ax.view_init(elev=27, azim=-54)
    ax.set_proj_type('ortho')
    ax.set_axis_off()
    fig.text(.07, .19, 'Ø3.1 原内收圆芯 × 3\n外侧名义加厚 2 mm，切向宽度不变\n孔位与柱头同圆 · 每隔 60° 交替', fontsize=13, color='#546c7d', linespacing=1.7)

    top_ax = fig.add_axes([.57, .505, .39, .315], projection='3d', facecolor='#eef3f4')
    add_mesh(top_ax, top_v, top_t, '#2a9996')
    a = np.linspace(0, 2*np.pi, 180)
    top_ax.plot(24*np.cos(a), 24*np.sin(a), np.full_like(a, p['antenna_mount_face_z_mm']+.05),
                color='#a9b6be', linestyle='--', linewidth=1.3)
    top_ax.set(xlim=(-26, 26), ylim=(-26, 26), zlim=(79, 84))
    top_ax.set_box_aspect((52, 52, 5))
    top_ax.view_init(elev=90, azim=-90)
    top_ax.set_proj_type('ortho')
    top_ax.set_axis_off()
    fig.text(.59, .84, '顶部：厚 2 mm · 4 mm 宽连接圆环 · Ø9 孔位台', fontsize=14, color='#277c7a')
    fig.text(.62, .505, '虚线为原 Ø48 圆盘；连接圆环中央保持敞开', fontsize=11, color='#637985')

    base_ax = fig.add_axes([.57, .205, .39, .255], projection='3d', facecolor='#eef3f4')
    base_faces = faces.max(axis=1)[:, 2] <= 43
    add_mesh(base_ax, vertices, triangles[base_faces], '#9baeba')
    base_ax.plot([-15, 15], [METAL_PARAMS['clamp_screw_y_mm']]*2, [37.65]*2, color='#d28a3e', linestyle='--', linewidth=2)
    base_ax.set(xlim=(-34, 34), ylim=(-42, 34), zlim=(32, 44))
    base_ax.set_box_aspect((62, 71, 12))
    base_ax.view_init(elev=66, azim=-90)
    base_ax.set_proj_type('ortho')
    base_ax.set_axis_off()
    fig.text(.59, .465, '柱根：约 17 mm 宽、与圆箍相切的长缓肩部', fontsize=14, color='#405f74')
    fig.text(.59, .165, '两耳均 Ø3.4 通孔；每耳厚 2.6 mm；收紧缝 2 mm\n内侧圆弧纹按 40 槽对位；螺母旋转包络 Ø7 mm',
             fontsize=12, color='#546c7d', linespacing=1.7)
    fig.text(.045, .085, f"CAD 体积减少 {report['volume_reduction_percent']:.1f}%  ·  本图未显示天线，便于检查孔位与开放区域", fontsize=14, color='#315a6c')
    fig.text(.045, .045, '几何定稿：316L / TC4 方向；制造支撑、公差、装配、夹紧力与强度仍需核验。单位 mm。', fontsize=11, color='#6b7e8b')
    output = ROOT / 'renders/rtk_antenna_mount_v6_metal.png'
    fig.savefig(output, facecolor=fig.get_facecolor())
    plt.close(fig)

    interactive = go.Figure()
    interactive.add_trace(go.Mesh3d(x=vertices[:, 0], y=vertices[:, 1], z=vertices[:, 2],
        i=triangles[:, 0], j=triangles[:, 1], k=triangles[:, 2], name='金属支架',
        facecolor=['#2a9996' if selected else '#a3b2bd' for selected in top_faces],
        flatshading=False, lighting=dict(ambient=.45, diffuse=.75, specular=.6, roughness=.35), showlegend=True))
    antenna = cylinder(p['antenna_diameter_mm']/2, p['antenna_height_mm'], z=p['antenna_mount_face_z_mm'])
    av, at, _ = h.mesh(antenna)
    interactive.add_trace(go.Mesh3d(x=av[:, 0], y=av[:, 1], z=av[:, 2], i=at[:, 0], j=at[:, 1], k=at[:, 2],
        name='天线外形包络（点击显示）', visible='legendonly', opacity=.35, color='#d8ad63', showlegend=True))
    interactive.update_layout(title='V6 金属天线支架定稿｜拖动旋转、滚轮缩放｜单位 mm',
        scene=dict(aspectmode='data', xaxis_title='X', yaxis_title='Y', zaxis_title='Z',
                   camera=dict(eye=dict(x=1.4, y=-1.8, z=1.1))), margin=dict(l=10, r=10, t=65, b=10))
    interactive.write_html(ROOT / 'renders/rtk_antenna_mount_v6_metal.html', include_plotlyjs=True, full_html=True)


def optical_check(shape):
    vertices, triangles, _ = h.mesh(shape, deflection=.025, angular=.1)
    loc = make_locator(vertices, triangles)
    baseline_path = ROOT / 'tests/rtk_mount_metal_cone_baseline_20261115.step'
    baseline = h.read_step(baseline_path)
    bv, bt, _ = h.mesh(baseline, deflection=.025, angular=.1)
    baseline_loc = make_locator(bv, bt)
    runs = []
    for step in [.5, .25, .125]:
        edges = np.linspace(-7, 52, round(59/step)+1)
        az = np.deg2rad(np.arange(step/2, 360, step))
        el = np.deg2rad((edges[:-1]+edges[1:])/2)
        aa, ee = np.meshgrid(az, el)
        directions = np.stack([np.cos(ee)*np.cos(aa), np.cos(ee)*np.sin(aa), np.sin(ee)], axis=-1)
        mask, _ = trace(loc, np.ones(len(triangles), dtype=np.uint8), directions)
        previous, _ = trace(baseline_loc, np.ones(len(bt), dtype=np.uint8), directions)
        weights = np.diff(np.sin(np.deg2rad(edges)))[:, None]
        percentage = float(((mask > 0)*weights).sum()/(weights.sum()*mask.shape[1])*100)
        prior_percentage = float(((previous > 0)*weights).sum()/(weights.sum()*mask.shape[1])*100)
        added = int(np.count_nonzero((mask > 0) & (previous == 0)))
        assert percentage <= prior_percentage+1e-9, 'Occlusion increased against the frozen symmetric metal baseline'
        assert added == 0, 'Some sampled directions gained occlusion; refine the outer reinforcement before release'
        runs.append({'angular_step_deg': step, 'rays': int(mask.size),
                     'blocked_solid_angle_percent': percentage, 'baseline_blocked_solid_angle_percent': prior_percentage,
                     'newly_blocked_ray_count': added, 'cleared_ray_count': int(np.count_nonzero((mask == 0) & (previous > 0)))})
    return {'method': 'New metal STEP geometry, independent O-point projection from (0,0,47), nominal 360/-7..52 deg FOV',
            'mesh_deflection_mm': .025, 'runs': runs, 'comparison_baseline_step': baseline_path.relative_to(ROOT).as_posix(),
            'comparison_baseline_sha256': hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
            'limitations': 'Not measured point loss. Real optical aperture, screws, cable, reflections and metal finish not modelled.'}


def main():
    p = json.loads((ROOT / 'reports/rtk_mount_v6_parameters.json').read_text(encoding='utf-8'))
    original_path = ROOT / 'step/rtk_antenna_mount_v6.step'
    original = h.read_step(original_path)
    shape, top = build_metal_mount(p)
    part_path = ROOT / 'step/rtk_antenna_mount_v6_metal.step'
    h.export_compound([shape], part_path)
    reread = h.read_step(part_path)
    roundtrip_delta = abs(solid_volume(reread)-solid_volume(shape))
    # STEP's surface conversion changes integrated volume slightly at curved joins.
    assert math.isclose(solid_volume(reread), solid_volume(shape), rel_tol=1e-6, abs_tol=1e-3)
    assert np.allclose(h.bounds(reread)['min']+h.bounds(reread)['max'],
                       h.bounds(shape)['min']+h.bounds(shape)['max'], rtol=0, atol=1e-5)
    source_assembly = h.read_step(ROOT / 'step/standing_device_with_rtk_v6.step')
    iterator = TopoDS_Iterator(source_assembly)
    parts = []
    while iterator.More():
        parts.append(iterator.Value())
        iterator.Next()
    assert len(parts) == 8
    mid_local = h.placed(parts[5], y=5, z=-73.1522)
    contact_pattern = verify_contact_pattern(mid_local, p)
    mount_mid = overlap(shape, mid_local)
    assert mount_mid < 1e-3, mount_mid
    parts[6] = h.placed(shape, y=-5, z=73.1522)
    antenna_local = cylinder(p['antenna_diameter_mm']/2, p['antenna_height_mm'], z=p['antenna_mount_face_z_mm'])
    antenna_overlap = overlap(shape, antenna_local)
    assert antenna_overlap < 1e-3
    rotation_checks = []
    screw_y = METAL_PARAMS['clamp_screw_y_mm']
    for x in [-METAL_PARAMS['lug_half_x_mm']-12, METAL_PARAMS['lug_half_x_mm']]:
        envelope = cylinder(METAL_PARAMS['clamp_rotation_envelope_diameter_mm']/2, 12, x, screw_y, 37.65, (1, 0, 0))
        value = overlap(shape, envelope)
        assert value < 1e-3
        rotation_checks.append({'rotation_envelope_diameter_mm': METAL_PARAMS['clamp_rotation_envelope_diameter_mm'],
                                'axial_approach_mm': 12, 'start_x_mm': x, 'overlap_mm3': value})
    rear_collar_radius = p['clamp_inner_diameter_mm']/2+METAL_PARAMS['clamp_radial_wall_mm']
    nut_clearance = math.hypot(METAL_PARAMS['lug_half_x_mm'], abs(screw_y)-METAL_PARAMS['clamp_nut_max_diameter_mm']/2)-rear_collar_radius
    rotation_clearance = math.hypot(METAL_PARAMS['lug_half_x_mm'], abs(screw_y)-METAL_PARAMS['clamp_rotation_envelope_diameter_mm']/2)-rear_collar_radius
    assert nut_clearance >= METAL_PARAMS['clamp_nut_rotation_clearance_mm']
    assert rotation_clearance >= 0
    shaft_overlap = overlap(shape, cylinder(1.5, 12, -6, screw_y, 37.65, (1, 0, 0)))
    assert shaft_overlap < 1e-3
    nut_overlap = overlap(shape, cylinder(METAL_PARAMS['clamp_nut_max_diameter_mm']/2, 2.4, METAL_PARAMS['lug_half_x_mm'], screw_y, 37.65, (1, 0, 0)))
    assert nut_overlap < 1e-3
    screw_access = []
    r = 23/math.sqrt(3)
    for angle in METAL_PARAMS['antenna_hole_angles_deg']:
        x, y = r*math.cos(math.radians(angle)), r*math.sin(math.radians(angle))
        value = overlap(shape, cylinder(3, 8, x, y, p['antenna_mount_face_z_mm']-10))
        assert value < 1e-3
        screw_access.append({'xy_mm': [x, y], 'nominal_screw_head_diameter_mm': 6, 'depth_mm': 8, 'overlap_mm3': value})
    tilt = []
    for angle in [0, 20, 40]:
        transform = gp_Trsf()
        transform.SetRotation(gp_Ax1(gp_Pnt(0, 33, 70.1522), gp_Dir(1, 0, 0)), math.radians(-angle))
        rotated = BRepBuilderAPI_Transform(parts[6], transform, True).Shape()
        value = overlap(rotated, parts[1])
        assert value < 1e-3
        tilt.append({'angle_deg': angle, 'mount_vs_base_mm3': value})
    installation = []
    for dz in [0, .5, 1, 1.5, 2, 3, 4, 5, 10, 20, 30]:
        value = overlap(h.placed(shape, z=dz), mid_local)
        assert value < 1e-3
        installation.append({'upward_offset_mm': dz, 'overlap_mm3': value})
    assembly_path = ROOT / 'step/standing_device_with_rtk_v6_metal.step'
    h.export_compound(parts, assembly_path)
    volume = solid_volume(shape)
    report = {'status': METAL_PARAMS['status'], 'units': 'mm', 'base_parameters': p, 'metal_parameters': METAL_PARAMS,
        'effective_post_geometry': metal_post_geometry(p),
        'source_v6_sha256': hashlib.sha256(original_path.read_bytes()).hexdigest(),
        'part_step': part_path.relative_to(ROOT).as_posix(), 'part_step_sha256': hashlib.sha256(part_path.read_bytes()).hexdigest(),
        'assembly_step': assembly_path.relative_to(ROOT).as_posix(), 'mount_bounds_mm': h.bounds(shape),
        'mount_solid_count': h.count(shape, TopAbs_SOLID), 'step_roundtrip_valid': BRepCheck_Analyzer(reread).IsValid(),
        'step_roundtrip_volume_difference_mm3': roundtrip_delta,
        'step_roundtrip_volume_tolerance': {'relative': 1e-6, 'absolute_mm3': 1e-3},
        'volume_integration': 'Adaptive Gauss, relative tolerance 1e-9, closed shells only',
        'mount_volume_mm3': volume, 'original_v6_volume_mm3': solid_volume(original),
        'volume_reduction_percent': (1-volume/solid_volume(original))*100,
        'top_support_volume_mm3': solid_volume(top), 'top_support_count': h.count(top, TopAbs_SOLID),
        'antenna_mount_face_z_mm': p['antenna_mount_face_z_mm'], 'top_bottom_z_mm': p['antenna_mount_face_z_mm']-2,
        'central_clear_opening_at_top_mm': 2*(23/math.sqrt(3)-4.5),
        'clamp_clearance_holes_mm': [3.4, 3.4], 'clamp_lug_thickness_each_mm': 2.6,
        'clamp_split_gap_mm': METAL_PARAMS['clamp_split_gap_mm'], 'matched_contact_pattern': contact_pattern,
        'M3_shaft_passage_overlap_mm3': shaft_overlap,
        'external_nut_envelope_overlap_mm3': nut_overlap,
        'nominal_nut_to_rear_collar_clearance_mm': nut_clearance,
        'rotation_envelope_to_rear_collar_clearance_mm': rotation_clearance,
        'clamp_screw_rearward_shift_mm': abs(screw_y)-p['lug_y_center_mm'],
        'radar_nominal_overlap_mm3': mount_mid, 'antenna_nominal_overlap_mm3': antenna_overlap,
        'external_nut_rotation_access': rotation_checks, 'antenna_screw_head_access': screw_access,
        'tilt_vs_base_checks': tilt, 'installation_path_samples': installation,
        'optical_check': optical_check(reread),
        'material_note': 'Geometry shared for 316L/TC4 candidates; supplier process, final grade, tolerances and structural loads are not qualified.',
        'manufacturing': ['Both ears have coaxial 3.4 mm CLEARANCE holes for an M3 through-bolt and separate exterior nut. DO NOT tap.',
            'Top three 3 mm holes are CLEARANCE holes for original antenna screws; DO NOT tap them M3.',
            'No printed threads or inserts. Confirm clearance-hole sizing after printing, deburr and finish mating surfaces.',
            'Supplier to determine orientation, removable supports, stress relief and dimensional compensation.',
            'Nominal base bore is 51.2 mm with a 2.0 mm closing slit; inward ribs follow the actual MID-360 recesses with nominal 0.1 mm profile clearance. Clock ribs to the grooves.',
            'Contact dimensions remain trial-fit values; no clamp torque or friction increase is certified.'],
        'limitations': ['No structural, fatigue, clamp-compliance, thread-strength or physical test performed.',
            'Nut rotation uses the user-specified 6 mm maximum diameter plus 0.5 mm radial allowance (7 mm envelope). This is not a guarantee for larger tools.',
            'Antenna screw pitch and SMA extension inherit user-supplied V6 dimensions; verify actual screw length after thinning.',
            'Metal clamp contact, RF/multipath effects and real LiDAR reflections were not tested.',
            'Full sensor/camera/cable assemblies and all-pairs interference are outside these checks.']}
    preview(shape, top, p, report)
    contact_preview(reread, mid_local)
    output = ROOT / 'reports/rtk_mount_v6_metal_20261115.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    final_path = ROOT / 'exports/rtk_antenna_mount_metal_final.step'
    h.export_compound([reread], final_path)
    final_shape = h.read_step(final_path)
    assert math.isclose(solid_volume(final_shape), solid_volume(reread), rel_tol=1e-6, abs_tol=1e-3)
    assert h.bounds(final_shape) == h.bounds(reread)
    final_report = {'status': METAL_PARAMS['status'], 'geometry_finalized_date': METAL_PARAMS['geometry_finalized_date'],
        'design_approved_by_user': True, 'geometry_revision': METAL_PARAMS['geometry_revision'], 'units': 'mm',
        'part_step': final_path.relative_to(ROOT).as_posix(), 'part_step_sha256': hashlib.sha256(final_path.read_bytes()).hexdigest(),
        'source_step': part_path.relative_to(ROOT).as_posix(), 'source_step_sha256': report['part_step_sha256'],
        'geometry_report': output.relative_to(ROOT).as_posix(), 'solid_count': h.count(final_shape, TopAbs_SOLID),
        'step_readback_valid': BRepCheck_Analyzer(final_shape).IsValid(), 'bounds_mm': h.bounds(final_shape),
        'volume_mm3': solid_volume(final_shape), 'export_volume_difference_mm3': abs(solid_volume(final_shape)-solid_volume(reread)),
        'coordinate_frame': 'Original radar assembly coordinates preserved; radar mounting plane Z=0',
        'clamp_split_gap_mm': METAL_PARAMS['clamp_split_gap_mm'], 'matched_contact_pattern': contact_pattern,
        'nut_rotation_envelope_diameter_mm': METAL_PARAMS['clamp_rotation_envelope_diameter_mm'],
        'nut_maximum_diameter_mm': METAL_PARAMS['clamp_nut_max_diameter_mm'],
        'nut_radial_clearance_mm': METAL_PARAMS['clamp_nut_rotation_clearance_mm']}
    for key, relative in [('preview', 'renders/rtk_antenna_mount_v6_metal.png'),
                          ('viewer', 'renders/rtk_antenna_mount_v6_metal.html'),
                          ('contact_section', 'renders/rtk_metal_mid360_contact.png')]:
        final_report[key] = relative
        final_report[key+'_sha256'] = hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
    (ROOT / 'reports/rtk_metal_final_export_20261115.json').write_text(
        json.dumps(final_report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['mount_volume_mm3', 'volume_reduction_percent', 'mount_solid_count',
        'radar_nominal_overlap_mm3', 'antenna_nominal_overlap_mm3', 'clamp_clearance_holes_mm', 'optical_check']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
