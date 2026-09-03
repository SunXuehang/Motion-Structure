"""Smoke checks for browser-review board-cover PNGs."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import FreeCAD as App
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import matplotlib.image as mpimg
import Mesh
import numpy as np

PROJECT_SRC = str(Path(__file__).resolve().parents[2] / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

from bracket.board_cover_rendering import render_board_cover_images


def _record_rendered_labels() -> tuple[list[str], callable]:
    """Capture real Matplotlib labels while preserving image rendering."""

    labels: list[str] = []
    original_set_title = Axes.set_title
    original_figure_text = Figure.text

    def record_set_title(axis, text, *args, **kwargs):
        labels.append(str(text))
        return original_set_title(axis, text, *args, **kwargs)

    def record_figure_text(figure, x, y, text, *args, **kwargs):
        labels.append(str(text))
        return original_figure_text(figure, x, y, text, *args, **kwargs)

    Axes.set_title = record_set_title
    Figure.text = record_figure_text

    def restore() -> None:
        Axes.set_title = original_set_title
        Figure.text = original_figure_text

    return labels, restore


def test_board_cover_renderer_writes_bottom_assembly_preview() -> None:
    """Catch omitting the board-plus-bottom-cover review image."""

    with TemporaryDirectory(prefix="uav-v3-cover-renders-") as temporary:
        root = Path(temporary)
        render_dir = root / "renders"
        render_dir.mkdir()
        reference = Mesh.Mesh()
        reference.addFacet(
            App.Vector(0.0, 0.0, 0.0),
            App.Vector(10.0, 0.0, 0.0),
            App.Vector(0.0, 10.0, 5.0),
        )
        reference.write(str(render_dir / "UAV_V3_compute_carrier_reference_clean.stl"))

        labels, restore = _record_rendered_labels()
        try:
            paths = render_board_cover_images(root)
        finally:
            restore()
        assert tuple(path.name for path in paths) == (
            "UAV_V3_board_covers_assembly.png",
            "UAV_V3_top_cover.png",
            "UAV_V3_bottom_cover.png",
            "UAV_V3_bottom_cover_assembled.png",
        )
        for path in paths:
            payload = path.read_bytes()
            assert payload.startswith(b"\x89PNG\r\n\x1a\n")
            assert len(payload) > 20_000

        assert (
            "Orange: Ø6 × 8 mm top standoffs   Blue: Ø6 × 13 mm bottom "
            "standoffs   Ø3.4 mm M3 holes   Gray: opaque board CAD"
        ) in labels

        assembled = mpimg.imread(paths[3])[:, :, :3]
        height, width, _ = assembled.shape
        plot_region = assembled[
            int(height * 0.15) : int(height * 0.85),
            int(width * 0.10) : int(width * 0.90),
        ]
        neutral_gray = np.ptp(plot_region, axis=2) < 0.08
        dark_surface = plot_region.mean(axis=2) < 0.55
        assert np.count_nonzero(neutral_gray & dark_surface) > 200

        blue_cover = (
            (assembled[:, :, 2] > assembled[:, :, 1] * 1.15)
            & (assembled[:, :, 1] > assembled[:, :, 0] * 1.35)
            & (assembled[:, :, 2] > 0.35)
        )
        # The two approved component openings reduce the visible face area,
        # while a true bottom-facing view still keeps well over 80k pixels.
        assert np.count_nonzero(blue_cover) > 80_000


if __name__ == "__main__":
    test_board_cover_renderer_writes_bottom_assembly_preview()
    print("1 board-cover rendering test passed")
