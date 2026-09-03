"""Generate browser-review PNGs for the UAV V3 board-cover design."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import colors as mpl_colors
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import Mesh
import numpy as np

from bracket.board_covers import (
    BoardCoverParameters,
    make_bottom_cover,
    make_top_cover,
    place_in_reference_coordinates,
)


def _shape_triangles(shape, deflection: float = 0.35) -> np.ndarray:
    vertices, indices = shape.tessellate(deflection)
    points = np.asarray([(point.x, point.y, point.z) for point in vertices])
    return points[np.asarray(indices, dtype=int)]


def _reference_triangles(path: Path, maximum_facets: int = 80_000) -> np.ndarray:
    mesh = Mesh.Mesh(str(path))
    facets = mesh.Facets
    stride = max(1, len(facets) // maximum_facets)
    return np.asarray(
        [
            [tuple(point) for point in facet.Points]
            for facet in facets[::stride]
        ],
        dtype=float,
    )


def _shaded_faces(triangles: np.ndarray, color: str, alpha: float) -> np.ndarray:
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths == 0.0] = 1.0
    normals /= lengths[:, None]
    light = np.asarray((0.35, -0.45, 0.82), dtype=float)
    light /= np.linalg.norm(light)
    brightness = np.clip(0.55 + 0.45 * np.maximum(0.0, normals @ light), 0.45, 1.0)
    base = np.asarray(mpl_colors.to_rgb(color), dtype=float)
    return np.column_stack((brightness[:, None] * base[None, :], np.full(len(triangles), alpha)))


def _add_mesh(axis, triangles: np.ndarray, color: str, alpha: float = 1.0) -> None:
    axis.add_collection3d(
        Poly3DCollection(
            triangles,
            facecolors=_shaded_faces(triangles, color, alpha),
            edgecolor="none",
            linewidth=0.0,
        )
    )


def _render_scene(
    path: Path,
    title: str,
    subtitle: str,
    meshes: tuple[tuple[np.ndarray, str, float], ...],
    elevation: float,
    azimuth: float,
) -> None:
    figure = plt.figure(figsize=(16, 10), dpi=100, facecolor="#f5f7fa")
    axis = figure.add_subplot(111, projection="3d", facecolor="#f5f7fa")
    all_points = []
    for triangles, color, alpha in meshes:
        _add_mesh(axis, triangles, color, alpha)
        all_points.append(triangles.reshape(-1, 3))

    points = np.vstack(all_points)
    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    center = (minimum + maximum) / 2.0
    half_span = max(maximum - minimum) * 0.58
    axis.set_xlim(center[0] - half_span, center[0] + half_span)
    axis.set_ylim(center[1] - half_span, center[1] + half_span)
    axis.set_zlim(center[2] - half_span, center[2] + half_span)
    axis.set_box_aspect((1.0, 1.0, 0.72))
    axis.set_proj_type("ortho")
    axis.view_init(elev=elevation, azim=azimuth)
    axis.set_axis_off()
    axis.set_title(title, fontsize=24, pad=18)
    figure.text(0.5, 0.035, subtitle, ha="center", fontsize=15, color="#3f4f61")
    figure.savefig(path, pad_inches=0.2)
    plt.close(figure)


def render_board_cover_images(root: Path) -> tuple[Path, ...]:
    """Render the placed assembly and isolated upper/lower cover views."""

    root = Path(root).resolve()
    render_dir = root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    paths = (
        render_dir / "UAV_V3_board_covers_assembly.png",
        render_dir / "UAV_V3_top_cover.png",
        render_dir / "UAV_V3_bottom_cover.png",
        render_dir / "UAV_V3_bottom_cover_assembled.png",
    )

    parameters = BoardCoverParameters()
    top_local = make_top_cover(parameters)
    bottom_local = make_bottom_cover(parameters)
    top_placed = _shape_triangles(place_in_reference_coordinates(top_local, parameters))
    bottom_placed = _shape_triangles(place_in_reference_coordinates(bottom_local, parameters))
    assembly_meshes = [
        (top_placed, "#f08a24", 1.0),
        (bottom_placed, "#328bc4", 1.0),
    ]
    bottom_assembly_meshes = [(bottom_placed, "#328bc4", 1.0)]
    reference_path = render_dir / "UAV_V3_compute_carrier_reference_clean.stl"
    if reference_path.is_file():
        reference_triangles = _reference_triangles(reference_path)
        assembly_meshes.insert(0, (reference_triangles, "#7b818a", 1.0))
        bottom_assembly_meshes.insert(0, (reference_triangles, "#7b818a", 1.0))
    _render_scene(
        paths[0],
        "UAV V3 compute carrier · upper and lower PLA covers",
        "Orange: Ø6 × 8 mm top standoffs   Blue: Ø6 × 13 mm bottom standoffs   "
        "Ø3.4 mm M3 holes   Gray: opaque board CAD",
        tuple(assembly_meshes),
        24.0,
        -58.0,
    )
    _render_scene(
        paths[1],
        "UAV V3 upper cover",
        "128 × 78 mm · 60 × 41 mm fan/heatsink · 16 × Ø3.4 mm M3 extension holes",
        ((_shape_triangles(top_local), "#f08a24", 1.0),),
        70.0,
        -70.0,
    )
    _render_scene(
        paths[2],
        "UAV V3 lower cover",
        "128 × 78 mm · 24 × 24 mm fan + 14 × 18 mm IMU · 16 × Ø3.4 mm M3 extension holes",
        ((_shape_triangles(bottom_local), "#328bc4", 1.0),),
        -70.0,
        110.0,
    )
    _render_scene(
        paths[3],
        "UAV V3 compute carrier · bottom view from below",
        "Blue: lower PLA cover   Gray: opaque board CAD   16 × Ø3.4 mm M3 extension holes",
        tuple(bottom_assembly_meshes),
        -90.0,
        170.0,
    )
    return paths
