"""Render an exploded view of the complete MID-360 handheld stack.

The scene is the same board-local geometry the combined assembly exports, but
every part is pushed away from the compute carrier along the assembly axis so
each printed piece and each bought component reads separately.  Output is a
web-ready PNG plus an SVG of the same figure.
"""

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import colors as mpl_colors
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from PIL import Image

import FreeCAD as App
import Mesh
import Part

from .board_bracket_assembly import build_board_bracket_assembly
from .board_covers import BoardCoverParameters


# Gap left between neighbouring parts once exploded, and the sideways march
# that turns a 500 mm tall stack into a roughly square picture.
EXPLODE_GAP_MM = 24.0
EXPLODE_X_STEP_MM = 30.0
CARRIER_DECIMATION_TOLERANCE_MM = 0.6
CARRIER_DECIMATION_REDUCTION = 0.985
TESSELLATION_DEFLECTION_MM = 0.30

@dataclass(frozen=True)
class ExplodedPart:
    """One part in the exploded scene, ordered from the top of the stack down."""

    key: str
    label: str
    note: str
    color: str
    printed: bool


# Assembly order, top of the stack first.  ``carrier`` is the anchor and stays
# put; everything above it moves up, everything below it moves down.
EXPLODED_PARTS = (
    ExplodedPart("sensor", "Livox MID-360", "激光雷达，航插朝后", "#5b6472", False),
    ExplodedPart("part_a", "结构 A · 雷达托板", "69×85×6 PLA", "#e8913a", True),
    ExplodedPart("part_b", "结构 B · 倾斜底座", "128×78×4 PLA · R45 · 0–40°", "#3b7ea1", True),
    ExplodedPart("d435i", "RealSense D435i", "装在 B 前端托板", "#8a94a3", False),
    ExplodedPart("top_cover", "开发板上盖板", "128×78×3 PLA · 隔柱 8", "#2f9e8f", True),
    ExplodedPart("carrier", "UAV V3 开发板", "整机算料参考 CAD", "#b9c0c9", False),
    ExplodedPart("bottom_cover", "开发板下盖板", "128×78×3 PLA · 隔柱 13", "#1f6f66", True),
    ExplodedPart("grip_body", "电池手柄本体", "Ø50 圆筒 · 16×M3 上吊", "#c2553f", True),
    ExplodedPart("cell_pack", "三角柱电池包", "边长 40 · 高 90", "#4caf50", False),
    ExplodedPart("bottom_cap", "手柄底盖", "Ø50×4 PLA · 3×M3", "#8f3a2b", True),
)
ANCHOR_KEY = "carrier"
# The camera-facing D435i rides with Part B rather than getting its own step.
RIDES_WITH = {"d435i": "part_b"}

def _shape_triangles(shape: Part.Shape, deflection: float) -> np.ndarray:
    """Tessellate a Part shape into an (n, 3, 3) triangle array."""

    vertices, facets = shape.tessellate(deflection)
    points = np.asarray([(p.x, p.y, p.z) for p in vertices], dtype=float)
    return points[np.asarray(facets, dtype=int)]


def _carrier_triangles(root: Path) -> np.ndarray:
    """Load the compute-carrier reference mesh, decimated to a legible shell."""

    source = root / "renders/UAV_V3_compute_carrier_reference_clean.stl"
    if not source.is_file():
        raise FileNotFoundError(f"board reference mesh missing: {source}")
    mesh = Mesh.Mesh(str(source))
    mesh.decimate(CARRIER_DECIMATION_TOLERANCE_MM, CARRIER_DECIMATION_REDUCTION)
    return np.asarray(
        [[tuple(point) for point in facet.Points] for facet in mesh.Facets],
        dtype=float,
    )


def _in_board_frame(triangles: np.ndarray, p: BoardCoverParameters) -> np.ndarray:
    """Map reference-frame carrier triangles back into the board-local frame."""

    placement = App.Placement(
        App.Vector(p.reference_center_x, p.reference_center_y, 0.0),
        App.Rotation(App.Vector(0.0, 0.0, 1.0), p.reference_rotation_deg),
    ).inverse()
    matrix = np.asarray(placement.Matrix.A, dtype=float).reshape(4, 4)
    flat = triangles.reshape(-1, 3)
    moved = flat @ matrix[:3, :3].T + matrix[:3, 3]
    return moved.reshape(triangles.shape)


def _shaded_faces(triangles: np.ndarray, color: str, alpha: float = 1.0) -> np.ndarray:
    """Return stable directional shading for one triangle array."""

    normals = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths == 0.0] = 1.0
    normals /= lengths[:, None]
    light = np.asarray((0.42, -0.52, 0.75), dtype=float)
    light /= np.linalg.norm(light)
    brightness = np.clip(0.52 + 0.48 * np.abs(normals @ light), 0.45, 1.0)
    base = np.asarray(mpl_colors.to_rgb(color), dtype=float)
    rgb = np.clip(brightness[:, None] * base[None, :], 0.0, 1.0)
    return np.column_stack((rgb, np.full(len(triangles), alpha)))


def _explosion_offsets(
    raw: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Push each part clear of its neighbour, anchored on the compute carrier.

    Offsets are derived from the real bounding boxes rather than hard-coded, so
    a part that grows cannot silently start overlapping the next one.
    """

    order = [part.key for part in EXPLODED_PARTS]
    anchor = order.index(ANCHOR_KEY)
    span = {key: (float(t[..., 2].min()), float(t[..., 2].max())) for key, t in raw.items()}

    dz: dict[str, float] = {ANCHOR_KEY: 0.0}
    # Upward: nearest neighbour above the carrier first.
    frontier = span[ANCHOR_KEY][1]
    for key in reversed(order[:anchor]):
        if key in RIDES_WITH:
            continue
        low, high = span[key]
        dz[key] = frontier + EXPLODE_GAP_MM - low
        frontier = high + dz[key]
    # Downward: nearest neighbour below the carrier first.
    frontier = span[ANCHOR_KEY][0]
    for key in order[anchor + 1 :]:
        if key in RIDES_WITH:
            continue
        low, high = span[key]
        dz[key] = frontier - EXPLODE_GAP_MM - high
        frontier = low + dz[key]
    for rider, host in RIDES_WITH.items():
        dz[rider] = dz[host]

    offsets: dict[str, np.ndarray] = {}
    for index, key in enumerate(order):
        host_index = order.index(RIDES_WITH.get(key, key))
        dx = (host_index - anchor) * EXPLODE_X_STEP_MM
        offsets[key] = np.asarray((dx, 0.0, dz[key]), dtype=float)
    return offsets


def build_assembled_parts(
    project_root: Path,
    deflection: float = TESSELLATION_DEFLECTION_MM,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Return the assembled triangle soup per part plus its explosion offset."""

    root = Path(project_root).resolve()
    assembly = build_board_bracket_assembly(root)
    raw = {
        "sensor": _shape_triangles(assembly.sensor, deflection),
        "part_a": _shape_triangles(assembly.part_a, deflection),
        "part_b": _shape_triangles(assembly.part_b, deflection),
        "d435i": _shape_triangles(assembly.d435i_reference, deflection),
        "top_cover": _shape_triangles(assembly.top_cover, deflection),
        "carrier": _in_board_frame(
            _carrier_triangles(root), BoardCoverParameters()
        ),
        "bottom_cover": _shape_triangles(assembly.bottom_cover, deflection),
        "grip_body": _shape_triangles(assembly.grip_body, deflection),
        "cell_pack": _shape_triangles(assembly.pack_reference, deflection),
        "bottom_cap": _shape_triangles(assembly.grip_bottom_cap, deflection),
    }
    missing = {part.key for part in EXPLODED_PARTS} - set(raw)
    if missing:
        raise ValueError(f"exploded scene is missing parts: {sorted(missing)}")
    return raw, _explosion_offsets(raw)


def scene_at(
    raw: dict[str, np.ndarray],
    offsets: dict[str, np.ndarray],
    factor: float,
) -> tuple[tuple[ExplodedPart, np.ndarray], ...]:
    """Return the stack part-way between assembled (0.0) and exploded (1.0)."""

    return tuple(
        (part, raw[part.key] + offsets[part.key] * factor)
        for part in EXPLODED_PARTS
    )


VIEW_ELEVATION_DEG = 16.0
# Turned 180 degrees from the original -62: the D435i sits at +Y, so the eye
# has to be on the +Y side or Part B hides the camera entirely.
VIEW_AZIMUTH_DEG = 118.0
TITLE = "手持式 MID-360 扫描装置 · 结构爆炸图"


def _subtitle() -> str:
    """Count the printed and bought parts instead of hard-coding the split."""

    printed = sum(1 for part in EXPLODED_PARTS if part.printed)
    bought = len(EXPLODED_PARTS) - printed
    return (
        f"{printed} 个 PLA 打印件 + {bought} 个外购/参考件"
        " · 全部尺寸由参数化 CAD 代码生成"
    )


def _draw_scene(
    axis, scene: tuple[tuple[ExplodedPart, np.ndarray], ...]
) -> np.ndarray:
    """Draw every part in one depth-sorted collection and return all vertices."""

    # A single Poly3DCollection lets matplotlib depth-sort across parts; one
    # collection per part would paint them in insertion order instead.
    triangles = np.concatenate([mesh for _part, mesh in scene])
    colors = np.concatenate(
        [
            _shaded_faces(mesh, part.color, 1.0 if part.printed else 0.92)
            for part, mesh in scene
        ]
    )
    collection = Poly3DCollection(
        triangles,
        facecolors=colors,
        edgecolors="none",
        linewidths=0.0,
        shade=False,
    )
    # Rasterise the ~200k triangles: a fully vector SVG of them is >100 MB,
    # while this keeps the file small and leaves every label as crisp text.
    collection.set_rasterized(True)
    axis.add_collection3d(collection)
    return triangles.reshape(-1, 3)


def camera_limits(points: np.ndarray) -> dict[str, tuple[float, float]]:
    """Fit an orthographic isometric camera tightly around a point cloud."""

    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    center = (minimum + maximum) / 2.0
    extent = maximum - minimum
    half = max(extent[0], extent[1], extent[2] * 0.62) * 0.48
    return {
        "x": (center[0] - half, center[0] + half),
        "y": (center[1] - half, center[1] + half),
        "z": (center[2] - extent[2] * 0.52, center[2] + extent[2] * 0.52),
    }


def _apply_camera(axis, limits: dict[str, tuple[float, float]]) -> None:
    """Point the camera the same way for a still frame and every movie frame."""

    axis.set_xlim(*limits["x"])
    axis.set_ylim(*limits["y"])
    axis.set_zlim(*limits["z"])
    axis.set_box_aspect((1.0, 1.0, 2.0))
    axis.set_proj_type("ortho")
    axis.view_init(elev=VIEW_ELEVATION_DEG, azim=VIEW_AZIMUTH_DEG)
    axis.set_axis_off()



ANIMATION_FIGSIZE = (7.6, 9.2)
ANIMATION_DPI = 100
ANIMATION_DEFLECTION_MM = 0.85
ANIMATION_HOLD_FRAMES = 7
ANIMATION_MOVE_FRAMES = 22
ANIMATION_FRAME_MS = 55
ANIMATION_MARGIN_PX = 12


def explosion_timeline() -> tuple[float, ...]:
    """0 = assembled, 1 = exploded: ease apart, hold, ease back, hold, loop."""

    span = ANIMATION_MOVE_FRAMES - 1
    move = tuple(
        (lambda u: u * u * (3.0 - 2.0 * u))(index / span)
        for index in range(ANIMATION_MOVE_FRAMES)
    )
    return (
        (0.0,) * ANIMATION_HOLD_FRAMES
        + move
        + (1.0,) * ANIMATION_HOLD_FRAMES
        + move[::-1]
    )


def _legend(figure, parts: tuple[ExplodedPart, ...]) -> None:
    """Name every part once, statically, so the frames stay uncluttered."""

    from matplotlib.patches import Patch

    figure.legend(
        handles=[
            Patch(facecolor=part.color, edgecolor="none", label=part.label)
            for part in parts
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=9.5,
        labelspacing=0.45,
        columnspacing=1.6,
        handlelength=1.3,
        bbox_to_anchor=(0.5, -0.004),
    )


def _animation_frame(
    scene: tuple[tuple[ExplodedPart, np.ndarray], ...],
    limits: dict[str, tuple[float, float]],
) -> "Image.Image":
    """Render one movie frame at a fixed camera and a fixed figure size."""

    plt.rcParams["font.family"] = ["Microsoft YaHei", "Droid Sans Fallback"]
    figure = plt.figure(
        figsize=ANIMATION_FIGSIZE, dpi=ANIMATION_DPI, facecolor="#f7f9fc"
    )
    axis = figure.add_subplot(111, projection="3d", facecolor="#f7f9fc")
    _draw_scene(axis, scene)
    _apply_camera(axis, limits)
    figure.suptitle(TITLE, fontsize=17, y=0.990, color="#16202c")
    figure.text(0.5, 0.951, _subtitle(), ha="center", fontsize=9.5, color="#4a5a6e")
    _legend(figure, tuple(part for part, _mesh in scene))
    figure.subplots_adjust(left=0.0, right=1.0, top=0.945, bottom=0.145)
    figure.canvas.draw()
    image = Image.fromarray(
        np.asarray(figure.canvas.buffer_rgba(), dtype=np.uint8)[..., :3].copy()
    )
    plt.close(figure)
    return image


def _content_box(image: "Image.Image", margin_px: int) -> tuple[int, int, int, int]:
    """Return an even-sized crop box around everything that is not background."""

    pixels = np.asarray(image, dtype=np.int16)
    occupied = np.abs(pixels - pixels[0, 0]).sum(axis=2) > 12
    rows = np.flatnonzero(occupied.any(axis=1))
    columns = np.flatnonzero(occupied.any(axis=0))
    if rows.size == 0 or columns.size == 0:
        return (0, 0, image.width, image.height)
    height, width = occupied.shape
    left = max(int(columns[0]) - margin_px, 0)
    top = max(int(rows[0]) - margin_px, 0)
    right = min(int(columns[-1]) + margin_px + 1, width)
    bottom = min(int(rows[-1]) + margin_px + 1, height)
    # libx264 needs even dimensions.
    right -= (right - left) % 2
    bottom -= (bottom - top) % 2
    return (left, top, right, bottom)


def _write_mp4(frames: list["Image.Image"], path: Path) -> bool:
    """Encode the frames with ffmpeg; return False when ffmpeg is unavailable."""

    import shutil
    import subprocess
    import tempfile

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    with tempfile.TemporaryDirectory(prefix="mid360-exploded-") as temporary:
        staging = Path(temporary)
        for index, frame in enumerate(frames):
            frame.save(staging / f"frame_{index:04d}.png")
        completed = subprocess.run(
            (
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                f"{1000.0 / ANIMATION_FRAME_MS:.4f}",
                "-i",
                str(staging / "frame_%04d.png"),
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(path),
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {completed.stderr.strip()}")
    return True


def render_exploded_animation(
    project_root: Path,
    output_dir: Path | None = None,
) -> tuple[Path, ...]:
    """Write the explode/collapse loop as a looping GIF and an MP4.

    The camera and the crop box are both derived once from the fully exploded
    state, so nothing jumps between frames and every frame is the same size.
    """

    root = Path(project_root).resolve()
    destination = Path(output_dir).resolve() if output_dir else root / "renders"
    destination.mkdir(parents=True, exist_ok=True)

    raw, offsets = build_assembled_parts(root, ANIMATION_DEFLECTION_MM)
    exploded = scene_at(raw, offsets, 1.0)
    limits = camera_limits(
        np.concatenate([mesh for _part, mesh in exploded]).reshape(-1, 3)
    )
    box = _content_box(_animation_frame(exploded, limits), ANIMATION_MARGIN_PX)
    frames = [
        _animation_frame(scene_at(raw, offsets, factor), limits).crop(box)
        for factor in explosion_timeline()
    ]

    mp4_path = destination / "handheld_stack_exploded.mp4"
    if not _write_mp4(frames, mp4_path):
        raise RuntimeError("ffmpeg is required to write the exploded-view MP4")
    return (mp4_path,)
