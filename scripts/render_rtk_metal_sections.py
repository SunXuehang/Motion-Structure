"""Render annotation sheets from the current exported STEP, without changing CAD."""
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
from matplotlib.collections import PolyCollection
from matplotlib.ticker import MultipleLocator
import numpy as np
from PIL import Image
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Section
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pln, gp_Pnt, gp_Dir

from bracket import rtk_geometry as h


def section(shape, origin, normal):
    plane = gp_Pln(gp_Pnt(*origin), gp_Dir(*normal))
    operation = BRepAlgoAPI_Section(shape, plane, False)
    operation.Approximation(True)
    operation.Build()
    assert operation.IsDone()
    paths = []
    explorer = TopExp_Explorer(operation.Shape(), TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        sample = GCPnts_QuasiUniformDeflection(BRepAdaptor_Curve(edge), .003)
        assert sample.IsDone() and sample.NbPoints() >= 2
        paths.append(np.array([[sample.Value(i).X(), sample.Value(i).Y(), sample.Value(i).Z()]
                               for i in range(1, sample.NbPoints()+1)]))
        explorer.Next()
    assert paths
    residual = max(float(np.max(np.abs((path-np.array(origin)) @ np.array(normal)))) for path in paths)
    assert residual < 1e-4, residual
    face = BRepBuilderAPI_MakeFace(plane, -150, 150, -150, 150).Face()
    common = BRepAlgoAPI_Common(shape, face)
    common.Build()
    assert common.IsDone() and h.count(common.Shape(), TopAbs_FACE) > 0
    vertices, triangles, _ = h.mesh(common.Shape(), deflection=.01, angular=.12)
    return paths, vertices, triangles, {'origin_mm': origin, 'normal': normal,
        'section_edge_count': len(paths), 'max_plane_residual_mm': residual,
        'material_face_count': h.count(common.Shape(), TopAbs_FACE)}


def draw(axis, data, project, *, major=2):
    paths, vertices, triangles, _ = data
    axis.add_collection(PolyCollection(project(vertices)[triangles], facecolor='#ededed',
                                      edgecolors='none', antialiased=False, zorder=2))
    for path in paths:
        points = project(path)
        axis.plot(points[:, 0], points[:, 1], color='#1b2930', linewidth=1.25, zorder=3)
    axis.set_aspect('equal')
    axis.xaxis.set_major_locator(MultipleLocator(major))
    axis.yaxis.set_major_locator(MultipleLocator(major))
    axis.xaxis.set_minor_locator(MultipleLocator(major/2))
    axis.yaxis.set_minor_locator(MultipleLocator(major/2))
    axis.grid(which='major', color='#e2e6e8', linewidth=.5, zorder=0)
    axis.grid(which='minor', color='#f0f2f3', linewidth=.4, zorder=0)
    axis.tick_params(labelsize=9, color='#9aa5ab')
    for spine in axis.spines.values():
        spine.set_color('#c4ccd0')


def main():
    source = ROOT / 'step/rtk_antenna_mount_v6_metal.step'
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    geometry_report = json.loads((ROOT / 'reports/rtk_mount_v6_metal_20261115.json').read_text(encoding='utf-8'))
    assert geometry_report['part_step_sha256'] == fingerprint
    shape = h.read_step(source)
    fonts = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    plt.rcParams['font.family'] = [font for font in ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'] if font in fonts]
    plt.rcParams['axes.unicode_minus'] = False
    horizontal = section(shape, [0, 0, 36.5], [0, 0, 1])
    names = [('A', 90), ('B', 210), ('C', 330)]
    fig = plt.figure(figsize=(16, 12), dpi=180, facecolor='white')
    fig.text(.045, .955, '当前结构 · 圆箍与三个柱根的水平截面', fontsize=23, color='#1b2930')
    fig.text(.045, .914, '剖切高度 Z = 36.50 mm；浅灰为实体材料，黑线为当前轮廓。右侧放大图可直接手绘。',
             fontsize=13, color='#5d6c75')
    overall = fig.add_axes([.065, .135, .455, .725])
    draw(overall, horizontal, lambda xyz: xyz[:, :2], major=10)
    overall.set(xlim=(-39, 39), ylim=(-44, 38), xlabel='X (mm)', ylabel='Y (mm)')
    overall.set_title('圆箍整体截面与 A / B / C 柱根位置', fontsize=14, pad=15)
    for row, (name, angle) in enumerate(names):
        theta = math.radians(angle)
        radial = np.array([math.cos(theta), math.sin(theta), 0])
        tangent = np.array([-math.sin(theta), math.cos(theta), 0])
        point = 30*radial[:2]
        label = 36*radial[:2]
        overall.annotate(name, xy=point, xytext=label, ha='center', va='center', fontsize=15,
            bbox={'boxstyle': 'circle,pad=.22', 'facecolor': 'white', 'edgecolor': '#8d9ba3'},
            arrowprops={'arrowstyle': '-', 'color': '#8d9ba3', 'linewidth': .8})
        zoom = fig.add_axes([.595, .655-row*.25, .35, .205])
        project = lambda xyz, t=tangent, r=radial: np.column_stack([xyz @ t, xyz @ r])
        draw(zoom, horizontal, project, major=2)
        zoom.set(xlim=(-8, 8), ylim=(23, 35), ylabel='径向 (mm)')
        if row == 2:
            zoom.set_xlabel('沿圆箍周向 (mm)')
        zoom.set_title(f'{name} 柱根 · 水平剖面放大', fontsize=14, pad=10)
    fig.text(.045, .055, '请直接描画你希望保留、增加或去掉的轮廓；此图仅提取现有 STEP，没有修改结构。',
             fontsize=12, color='#5d6c75')
    top_path = ROOT / 'renders/rtk_metal_base_section_markup.png'
    fig.savefig(top_path, facecolor='white')
    plt.close(fig)

    fig = plt.figure(figsize=(16, 8), dpi=180, facecolor='white')
    fig.text(.045, .94, '当前结构 · 三个柱根的径向竖直截面', fontsize=23, color='#1b2930')
    fig.text(.045, .885, '每张图穿过对应支柱中心；横向朝外，纵向为相对圆箍底面的高度。可补充标注根部上下轮廓。',
             fontsize=13, color='#5d6c75')
    evidence = []
    for i, (name, angle) in enumerate(names):
        theta = math.radians(angle)
        radial = np.array([math.cos(theta), math.sin(theta), 0])
        tangent = np.array([-math.sin(theta), math.cos(theta), 0])
        vertical = section(shape, [0, 0, 0], tangent.tolist())
        axis = fig.add_axes([.065+i*.313, .16, .255, .64])
        draw(axis, vertical, lambda xyz, r=radial: np.column_stack([xyz @ r, xyz[:, 2]-34.25]), major=2)
        axis.set(xlim=(23, 35), ylim=(-2, 14), xlabel='向外 → 径向 (mm)', ylabel='距圆箍底面高度 (mm)')
        axis.set_title(f'{name}—{name} · {name} 柱根竖剖', fontsize=15, pad=12)
        evidence.append({'post': name, 'post_angle_deg': angle, **vertical[3]})
    fig.text(.045, .055, '浅灰：材料；白色：空隙。此为真实平面剖切，不是投影视图或修改方案。单位 mm。',
             fontsize=12, color='#5d6c75')
    vertical_path = ROOT / 'renders/rtk_metal_root_vertical_sections_markup.png'
    fig.savefig(vertical_path, facecolor='white')
    plt.close(fig)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == fingerprint
    for path, expected in [(top_path, (2880, 2160)), (vertical_path, (2880, 1440))]:
        with Image.open(path) as png:
            assert png.size == expected
    report = {'source_step': source.relative_to(ROOT).as_posix(), 'source_step_sha256': fingerprint,
        'geometry_modified': False, 'edge_sampling_deflection_mm': .003,
        'horizontal_plane': horizontal[3], 'vertical_planes': evidence,
        'images': [top_path.relative_to(ROOT).as_posix(), vertical_path.relative_to(ROOT).as_posix()]}
    (ROOT / 'reports/rtk_metal_sections_20261115.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
