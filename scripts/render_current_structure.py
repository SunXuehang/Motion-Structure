"""Render the selected standing-device STEP for the README, without FreeCAD."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopoDS import TopoDS_Iterator

from bracket import rtk_geometry as h
from bracket.rendering import _shaded_faces
from bracket.rtk_shadow import make_locator


def display_mesh(shape, limit=2800):
    vertices, triangles, _ = h.mesh(shape, deflection=.15, angular=.22)
    if len(triangles) > limit:
        decimate = vtk.vtkQuadricDecimation()
        decimate.SetInputData(make_locator(vertices, triangles).GetDataSet())
        decimate.SetTargetReduction(1 - limit / len(triangles))
        decimate.Update()
        mesh = decimate.GetOutput()
        assert np.all(np.diff(vtk_to_numpy(mesh.GetPolys().GetOffsetsArray())) == 3)
        vertices = vtk_to_numpy(mesh.GetPoints().GetData())
        triangles = vtk_to_numpy(mesh.GetPolys().GetConnectivityArray()).reshape(-1, 3)
    return vertices, triangles


def add_scene(axis, meshes, colors):
    # One collection sorts faces across touching parts instead of whole solids.
    triangles = [vertices[faces] for vertices, faces in meshes]
    facecolors = np.concatenate([_shaded_faces(t, c) for t, c in zip(triangles, colors)])
    axis.add_collection3d(Poly3DCollection(
        np.concatenate(triangles), facecolors=facecolors,
        edgecolors='none', linewidth=0, zsort='average'))


def main():
    source = ROOT / 'step/standing_device_with_rtk_v6.step'
    shape = h.read_step(source)
    bounds = h.bounds(shape)
    explorer = TopoDS_Iterator(shape)
    parts = []
    while explorer.More():
        parts.append(explorer.Value())
        explorer.Next()
    solid_count = h.count(shape, TopAbs_SOLID)
    assert len(parts) == 8 and solid_count == 14
    # STEP compound order comes from build_rtk_mount.py's full_machine list.
    assert h.bounds(parts[4])['min'][2] < -120
    assert abs(h.bounds(parts[6])['max'][2] - 155.770799) < 1e-5
    meshes = [display_mesh(s) for s in parts[:5]]
    # Keep radar shell faces as well as solids: its case includes open surfaces.
    rv, rt = display_mesh(parts[5], limit=10500)
    window = rv[rt].mean(axis=1)[:, 2] > 111.65
    meshes += [(rv, rt[~window]), (rv, rt[window])]
    meshes += [display_mesh(s) for s in parts[6:]]
    colors = ['#d58b51', '#7299b7', '#b2c9d7', '#91adbf', '#4e6e86']
    colors += ['#a2afb5', '#647b88', '#279795', '#d6a33d']
    assert len(colors) == len(meshes)

    available = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    plt.rcParams['font.family'] = [name for name in ['Microsoft YaHei', 'Noto Sans CJK SC', 'DejaVu Sans'] if name in available]
    plt.rcParams['axes.unicode_minus'] = False
    fig = plt.figure(figsize=(20, 14), dpi=110, facecolor='#fbfcfd')
    fig.text(.055, .947, '当前完整结构', fontsize=32, weight='bold', color='#243d4d')
    fig.text(.055, .908, '站立手柄 + V6 RTK 天线支架  /  已确认结构 · 倾角 0°',
             fontsize=20, color='#567181')
    main_axis = fig.add_axes([.015, .105, .63, .765], projection='3d', facecolor='#fbfcfd')
    add_scene(main_axis, meshes, colors)
    main_axis.set(xlim=(-90, 90), ylim=(-85, 90), zlim=(-132, 205))
    main_axis.set_box_aspect((180, 175, 337), zoom=1.12)
    main_axis.set_proj_type('ortho')
    main_axis.view_init(elev=17, azim=-56)
    main_axis.set_axis_off()

    detail = fig.add_axes([.655, .445, .31, .405], projection='3d', facecolor='#f0f5f7')
    add_scene(detail, meshes[5:], colors[5:])
    detail.set(xlim=(-44, 44), ylim=(-48, 40), zlim=(70, 200))
    detail.set_box_aspect((88, 88, 130), zoom=1.05)
    detail.set_proj_type('ortho')
    detail.view_init(elev=16, azim=44)
    detail.set_axis_off()
    fig.text(.695, .858, '顶部安装细节 · 反向视角', fontsize=20, color='#315766')

    fig.canvas.draw()

    def label(text, point, xy, color, align='left'):
        x, y, _ = proj3d.proj_transform(*point, main_axis.get_proj())
        main_axis.annotate(text, xy=(x, y), xycoords='data', xytext=xy,
                           textcoords=fig.transFigure, ha=align, va='center',
                           fontsize=19, color=color, zorder=100,
                           bbox={'facecolor': '#fbfcfd', 'edgecolor': 'none', 'pad': 3},
                           arrowprops={'arrowstyle': '-', 'color': color, 'linewidth': 1.4,
                                       'connectionstyle': 'angle,angleA=0,angleB=90,rad=4'})

    label('HX-CUX623A\nGNSS 天线包络', (0, -5, 177), (.075, .815), '#9b701d')
    label('V6 一体天线支架\n3 根内收圆弧柱', (22, -18, 145), (.465, .745), '#187f7c')
    label('MID-360 雷达', (-23, -21, 111), (.065, .655), '#526b79')
    label('雷达活动托板 A\n+ 倾斜底座 B', (47, 24, 82), (.475, .573), '#426e8b')
    label('开发板上 / 下盖板', (-58, -15, 25), (.055, .485), '#5e7e94')
    label('站立手柄', (-16, -8, -62), (.105, .325), '#395d78')
    label('一体支脚', (38, -20, -120), (.475, .19), '#395d78')

    fig.text(.695, .42, 'V6 顶部结构', fontsize=22, weight='bold', color='#243d4d')
    fig.text(.695, .387, 'Ø3.1 mm 圆弧柱 × 3\n单颗 M3 收紧抱箍\nØ4 × 深 3 mm 热熔螺母底孔',
             fontsize=19, color='#496574', linespacing=1.7, va='top')
    fig.text(.695, .245, '6 个打印件', fontsize=24, weight='bold', color='#243d4d')
    x, y, z = bounds['size']
    fig.text(.695, .213, f'装配包络  {x:g} × {y:g} × {z:.1f} mm\n顶部扫描边界竖向余量  0.90 mm',
             fontsize=18, color='#496574', linespacing=1.8, va='top')
    fig.text(.055, .063, '依据已提交的 STEP 装配绘制；颜色仅区分零部件。天线为圆柱外形包络。',
             fontsize=16, color='#647c8a')
    fig.text(.055, .035, '相机、开发板、线缆和金属紧固件未显示；打印姿态、实物试装和强度仍需确认。',
             fontsize=16, color='#647c8a')
    out = ROOT / 'renders/current_structure_v6.png'
    fig.savefig(out, facecolor=fig.get_facecolor(), dpi=110)
    plt.close(fig)
    evidence = {'source_step': source.relative_to(ROOT).as_posix(),
                'source_step_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'png': out.relative_to(ROOT).as_posix(), 'pixel_size': [2200, 1540],
                'solid_count': solid_count, 'top_level_parts': len(parts), 'printed_part_count': 6,
                'assembly_bounds_mm': bounds, 'display_triangles': sum(len(m[1]) for m in meshes),
                'geometry_changed': False, 'display_only_decimation': True,
                'includes_radar_non_solid_faces': True}
    (ROOT / 'reports/current_structure_v6_render.json').write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == '__main__':
    main()
