"""Render FreeCAD-tessellated R45 review scenes without a GUI display."""

import json
from pathlib import Path
import subprocess
import tempfile

import matplotlib

matplotlib.use("Agg")
from matplotlib import colors as mpl_colors
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

from .parameters import BracketParameters, derive


def _shaded_faces(triangles: np.ndarray, color: str) -> np.ndarray:
    """Return stable directional shading for one triangle array."""

    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths == 0.0] = 1.0
    normals /= lengths[:, None]
    light = np.asarray((0.35, -0.45, 0.82), dtype=float)
    light /= np.linalg.norm(light)
    brightness = np.clip(0.48 + 0.52 * np.maximum(0.0, normals @ light), 0.42, 1.0)
    base = np.asarray(mpl_colors.to_rgb(color), dtype=float)
    return np.column_stack((brightness[:, None] * base[None, :], np.ones(len(triangles))))


def _render_scene(scene: dict[str, object], path: Path) -> None:
    """Render one serialized assembly scene at a fixed camera and resolution."""

    plt.rcParams["font.family"] = ["Microsoft YaHei", "Droid Sans Fallback"]
    figure = plt.figure(figsize=(16, 10), dpi=100, facecolor="#f6f8fb")
    axis = figure.add_subplot(111, projection="3d", facecolor="#f6f8fb")
    all_vertices: list[np.ndarray] = []
    for mesh in scene["meshes"]:
        vertices = np.asarray(mesh["vertices"], dtype=float)
        faces = np.asarray(mesh["triangles"], dtype=int)
        triangles = vertices[faces]
        all_vertices.append(vertices)
        collection = Poly3DCollection(
            triangles,
            facecolors=_shaded_faces(triangles, mesh["color"]),
            edgecolor="#27364a",
            linewidth=0.10,
        )
        axis.add_collection3d(collection)

    points = np.vstack(all_vertices)
    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    center = (minimum + maximum) / 2.0
    half_span = max(maximum - minimum) * 0.60
    axis.set_xlim(center[0] - half_span, center[0] + half_span)
    axis.set_ylim(center[1] - half_span, center[1] + half_span)
    axis.set_zlim(center[2] - half_span, center[2] + half_span)
    axis.set_box_aspect((1.0, 1.0, 0.78))
    axis.set_proj_type("ortho")
    axis.view_init(elev=22.0, azim=-52.0)
    axis.set_axis_off()
    angle = int(scene["angle_deg"])
    axis.set_title(
        f"MID-360 PLA俯仰支架 R45 · 后端向上 {angle}°",
        fontsize=24,
        pad=18,
    )
    figure.text(
        0.5,
        0.035,
        "A 69×85×6 mm · B 128×78×4 mm · 3.4 mm M3弧槽 R45 · 外轮廓R53",
        ha="center",
        fontsize=16,
    )
    figure.savefig(path, pad_inches=0.2)
    plt.close(figure)


def render_review_images(root: Path) -> tuple[Path, ...]:
    """Generate the 0, 20, and 40 degree browser-review PNGs."""

    project_root = Path(root).resolve()
    render_dir = project_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mid360-r45-render-") as temp_dir:
        scene_path = Path(temp_dir) / "scenes.json"
        subprocess.run(
            (
                str(project_root / "scripts/run_freecad.sh"),
                str(project_root / "scripts/export_render_scene.py"),
                str(scene_path),
            ),
            cwd=project_root,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        scenes = json.loads(scene_path.read_text(encoding="utf-8"))["scenes"]

    paths: list[Path] = []
    for scene in scenes:
        path = render_dir / f"assembly_r45_{scene['angle_deg']:g}deg.png"
        _render_scene(scene, path)
        paths.append(path)
    return tuple(paths)


def _section_axis(title: str, subtitle: str):
    """Create one consistently styled engineering-section canvas."""

    plt.rcParams["font.family"] = ["Microsoft YaHei", "Droid Sans Fallback"]
    figure, axis = plt.subplots(figsize=(16, 10), dpi=100, facecolor="#f6f8fb")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal")
    axis.set_title(title, fontsize=25, pad=18)
    figure.text(0.5, 0.925, subtitle, ha="center", fontsize=15, color="#42536a")
    axis.set_xlabel("X / mm", fontsize=13)
    axis.set_ylabel("Z / mm", fontsize=13)
    axis.grid(True, color="#d8e0ea", linewidth=0.7, alpha=0.65)
    axis.tick_params(labelsize=11)
    return figure, axis


def _material(axis, x: float, z: float, width: float, height: float) -> None:
    axis.add_patch(
        Rectangle(
            (x, z),
            width,
            height,
            facecolor="#77a9cc",
            edgecolor="#17324d",
            linewidth=2.0,
            hatch="///",
        )
    )


def _horizontal_dimension(axis, x0: float, x1: float, z: float, label: str) -> None:
    axis.annotate(
        "",
        xy=(x0, z),
        xytext=(x1, z),
        arrowprops={"arrowstyle": "<->", "color": "#b02a37", "linewidth": 1.8},
    )
    axis.text((x0 + x1) / 2.0, z + 0.8, label, ha="center", color="#8d1c28", fontsize=14)


def _render_part_a_pivot_section(p: BracketParameters, path: Path) -> None:
    """Render A's direct side-thread section through its pivot axis."""

    figure, axis = _section_axis(
        "结构 A · 6 mm平板侧面 M3 热熔螺母底孔剖面",
        f"剖切位置 Y=+{p.a_pivot_y:g} mm · 从机器人前方向后看",
    )
    half_width = p.a_plate_width / 2.0
    thread_depth = p.a_insert_hole_depth
    pilot_radius = p.a_insert_hole_diameter / 2.0

    _material(axis, -half_width, -p.a_plate_thickness, p.a_plate_width, p.a_plate_thickness)
    axis.add_patch(Rectangle((-half_width, p.a_pivot_z - pilot_radius), thread_depth, 2.0 * pilot_radius,
                             facecolor="white", edgecolor="#17324d", linewidth=1.5))
    axis.add_patch(Rectangle((half_width - thread_depth, p.a_pivot_z - pilot_radius), thread_depth, 2.0 * pilot_radius,
                             facecolor="white", edgecolor="#17324d", linewidth=1.5))
    axis.axhline(p.a_pivot_z, color="#56697d", linewidth=0.9, linestyle="--")

    _horizontal_dimension(axis, -half_width, -half_width + thread_depth, 3.5, "底孔深 3 mm")
    _horizontal_dimension(axis, half_width - thread_depth, half_width, 3.5, "底孔深 3 mm")
    axis.annotate(
        "Ø4.0 mm\nM3 热熔螺母底孔",
        xy=(-39.5, p.a_pivot_z),
        xytext=(-24.0, 7.0),
        arrowprops={"arrowstyle": "->", "color": "#8d1c28", "linewidth": 1.6},
        fontsize=14,
        color="#8d1c28",
        ha="center",
    )
    axis.text(0.0, -9.0, "两侧盲孔内嵌 M3 热熔螺母，螺钉拧入铜螺母", ha="center", fontsize=15)
    axis.text(0.0, -11.5, "蓝色斜线 = PLA 实体    白色 = 孔", ha="center", fontsize=13, color="#42536a")
    axis.set_xlim(-53.0, 53.0)
    axis.set_ylim(-13.0, 10.0)
    figure.tight_layout(rect=(0.03, 0.04, 0.97, 0.90))
    figure.savefig(path, pad_inches=0.2)
    plt.close(figure)


def _render_part_b_pivot_section(p: BracketParameters, path: Path) -> None:
    """Render B's sector-centre axial section through the current pivot Y."""

    figure, axis = _section_axis(
        "结构 B · 扇形圆心转轴轴向剖面",
        f"剖切位置 Y=+{p.b_pivot_y:g} mm · 从机器人前方向后看",
    )
    half_inner = p.b_inner_width / 2.0
    wall = p.b_wall_thickness
    outer = half_inner + wall
    hole_center_z = p.b_base_thickness + p.pivot_z_above_base
    hole_radius = p.b_clearance_hole_diameter / 2.0
    section_top = 24.0

    _material(axis, -p.b_base_width / 2.0, 0.0, p.b_base_width, p.b_base_thickness)
    _material(axis, -outer, p.b_base_thickness, wall, section_top - p.b_base_thickness)
    _material(axis, half_inner, p.b_base_thickness, wall, section_top - p.b_base_thickness)
    for x in (-outer, half_inner):
        axis.add_patch(
            Rectangle(
                (x, hole_center_z - hole_radius),
                wall,
                2.0 * hole_radius,
                facecolor="white",
                edgecolor="#17324d",
                linewidth=1.5,
            )
        )
    axis.axhline(hole_center_z, color="#56697d", linewidth=0.9, linestyle="--")

    _horizontal_dimension(axis, -outer, -half_inner, 27.0, "侧板 4 mm")
    _horizontal_dimension(axis, half_inner, outer, 27.0, "侧板 4 mm")
    _horizontal_dimension(axis, -half_inner, half_inner, 31.0, "A 件安装净宽 69.8 mm")
    axis.annotate(
        "Ø3.4 mm M3贯穿孔",
        xy=(-44.9, hole_center_z),
        xytext=(-22.0, 21.0),
        arrowprops={"arrowstyle": "->", "color": "#8d1c28", "linewidth": 1.6},
        fontsize=14,
        color="#8d1c28",
        ha="center",
    )
    axis.annotate(
        "Ø3.4 mm M3贯穿孔",
        xy=(44.9, hole_center_z),
        xytext=(25.0, 21.0),
        arrowprops={"arrowstyle": "->", "color": "#8d1c28", "linewidth": 1.6},
        fontsize=14,
        color="#8d1c28",
        ha="center",
    )
    gap = derive(p).main_side_gap
    axis.text(0.0, 7.0, f"A 69.0 mm 居中安装后：左右各 {gap:.1f} mm 间隙", ha="center", fontsize=15)
    axis.text(0.0, -4.8, "蓝色斜线 = PLA 实体    白色 = 贯穿孔", ha="center", fontsize=13, color="#42536a")
    axis.set_xlim(-58.0, 58.0)
    axis.set_ylim(-7.0, 35.0)
    figure.tight_layout(rect=(0.03, 0.04, 0.97, 0.90))
    figure.savefig(path, pad_inches=0.2)
    plt.close(figure)


def render_pivot_section_images(root: Path) -> tuple[Path, ...]:
    """Generate separate A and B front-pivot axial-section PNGs."""

    render_dir = Path(root).resolve() / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    p = BracketParameters()
    paths = (
        render_dir / "part_a_pivot_section.png",
        render_dir / "part_b_pivot_section.png",
    )
    _render_part_a_pivot_section(p, paths[0])
    _render_part_b_pivot_section(p, paths[1])
    return paths
