from pathlib import Path
import subprocess
import sys

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from PIL import Image

from bracket.rendering import render_pivot_section_images, render_review_images


ROOT = Path(__file__).resolve().parents[1]


def _record_rendered_labels(monkeypatch) -> list[str]:
    """Capture labels while preserving the real Matplotlib render path."""

    labels: list[str] = []
    original_annotate = Axes.annotate
    original_axis_text = Axes.text
    original_set_title = Axes.set_title
    original_figure_text = Figure.text

    def record_annotate(axis, text, *args, **kwargs):
        labels.append(str(text))
        return original_annotate(axis, text, *args, **kwargs)

    def record_axis_text(axis, x, y, text, *args, **kwargs):
        labels.append(str(text))
        return original_axis_text(axis, x, y, text, *args, **kwargs)

    def record_set_title(axis, text, *args, **kwargs):
        labels.append(str(text))
        return original_set_title(axis, text, *args, **kwargs)

    def record_figure_text(figure, x, y, text, *args, **kwargs):
        labels.append(str(text))
        return original_figure_text(figure, x, y, text, *args, **kwargs)

    monkeypatch.setattr(Axes, "annotate", record_annotate)
    monkeypatch.setattr(Axes, "text", record_axis_text)
    monkeypatch.setattr(Axes, "set_title", record_set_title)
    monkeypatch.setattr(Figure, "text", record_figure_text)
    return labels


def test_r45_review_pngs_are_full_size_real_geometry_renders(monkeypatch):
    labels = _record_rendered_labels(monkeypatch)
    paths = render_review_images(ROOT)

    assert [path.name for path in paths] == [
        "assembly_r45_0deg.png",
        "assembly_r45_20deg.png",
        "assembly_r45_40deg.png",
    ]
    for path in paths:
        assert path.stat().st_size > 100_000
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        with Image.open(path) as image:
            assert image.size == (1600, 1000)
    joined_labels = "\n".join(labels)
    assert "3.4 mm M3弧槽" in joined_labels
    assert {
        label for label in labels if label.startswith("MID-360 PLA俯仰支架")
    } == {
        "MID-360 PLA俯仰支架 R45 · 后端向上 0°",
        "MID-360 PLA俯仰支架 R45 · 后端向上 20°",
        "MID-360 PLA俯仰支架 R45 · 后端向上 40°",
    }
    for stale_label in ("R2", "15°", "30°"):
        assert stale_label not in joined_labels


def test_render_entry_point_runs_from_repo_without_pythonpath():
    result = subprocess.run(
        (sys.executable, "scripts/render_model.py"),
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "assembly_r45_0deg.png" in result.stdout
    assert "part_a_pivot_section.png" in result.stdout
    assert "part_b_pivot_section.png" in result.stdout


def test_separate_a_and_b_pivot_sections_are_full_size_pngs(monkeypatch):
    """Catch omitting either part's independently reviewable pivot section."""

    labels = _record_rendered_labels(monkeypatch)
    paths = render_pivot_section_images(ROOT)

    assert [path.name for path in paths] == [
        "part_a_pivot_section.png",
        "part_b_pivot_section.png",
    ]
    for path in paths:
        assert path.stat().st_size > 50_000
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        with Image.open(path) as image:
            assert image.size == (1600, 1000)
    assert "Ø2.9 mm\nM3×0.5 PLA攻丝底孔" in labels
    assert "Ø3.4 mm M3贯穿孔" in labels
    assert "M2.5" not in "\n".join(labels)
