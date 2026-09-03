"""Checks for the exploded-view scene maths and its animation frames."""

from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_SRC = str(PROJECT_ROOT / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

from bracket.exploded_view import (
    ANIMATION_HOLD_FRAMES,
    ANIMATION_MOVE_FRAMES,
    ANCHOR_KEY,
    EXPLODE_GAP_MM,
    EXPLODED_PARTS,
    RIDES_WITH,
    _animation_frame,
    _content_box,
    _explosion_offsets,
    camera_limits,
    explosion_timeline,
    scene_at,
)


def _slab(z0: float, z1: float, half_xy: float = 30.0) -> np.ndarray:
    """One triangle spanning a known Z band, enough for the offset maths."""

    return np.asarray(
        [
            [
                (-half_xy, -half_xy, z0),
                (half_xy, -half_xy, z0),
                (0.0, half_xy, z1),
            ]
        ],
        dtype=float,
    )


def _synthetic_raw() -> dict[str, np.ndarray]:
    """A 10 mm slab per part, stacked 12 mm apart, i.e. overlapping nothing."""

    return {
        part.key: _slab(-10.0 * index, -10.0 * index + 8.0)
        for index, part in enumerate(EXPLODED_PARTS)
    }


def test_explosion_timeline_eases_out_holds_and_returns() -> None:
    """Catch a timeline that jumps, never fully explodes, or fails to loop."""

    timeline = explosion_timeline()
    assert len(timeline) == 2 * (ANIMATION_HOLD_FRAMES + ANIMATION_MOVE_FRAMES)
    assert timeline[0] == 0.0 and max(timeline) == 1.0
    # It must come back to the assembled state so the GIF loop is seamless.
    assert timeline[-1] == 0.0
    assert all(0.0 <= factor <= 1.0 for factor in timeline)
    # The outward move is monotonic, and no single step is a jump cut.
    outward = timeline[ANIMATION_HOLD_FRAMES : ANIMATION_HOLD_FRAMES + ANIMATION_MOVE_FRAMES]
    assert all(b >= a for a, b in zip(outward, outward[1:]))
    assert max(b - a for a, b in zip(outward, outward[1:])) < 0.12


def test_explosion_offsets_open_a_real_gap_between_every_neighbour() -> None:
    """Catch an explosion that leaves parts touching or reorders the stack."""

    raw = _synthetic_raw()
    offsets = _explosion_offsets(raw)
    assert np.allclose(offsets[ANCHOR_KEY], (0.0, 0.0, 0.0))
    for rider, host in RIDES_WITH.items():
        assert offsets[rider][2] == offsets[host][2]

    exploded = {key: raw[key] + offsets[key] for key in raw}
    spans = [
        (part.key, float(exploded[part.key][..., 2].min()), float(exploded[part.key][..., 2].max()))
        for part in EXPLODED_PARTS
        if part.key not in RIDES_WITH
    ]
    # Listed top-first, so each part must sit entirely above the next one.
    for (upper_key, _upper_min, _upper_max), (lower_key, _lower_min, lower_max) in zip(
        spans, spans[1:]
    ):
        upper_min = next(low for key, low, _high in spans if key == upper_key)
        gap = upper_min - lower_max
        assert gap >= EXPLODE_GAP_MM - 1e-6, f"{upper_key} vs {lower_key}: {gap}"


def test_scene_at_zero_is_assembled_and_one_is_exploded() -> None:
    """Catch an interpolation that drifts at the ends of the animation."""

    raw = _synthetic_raw()
    offsets = _explosion_offsets(raw)
    assembled = scene_at(raw, offsets, 0.0)
    exploded = scene_at(raw, offsets, 1.0)
    half = scene_at(raw, offsets, 0.5)
    for (part, mesh) in assembled:
        assert np.allclose(mesh, raw[part.key])
    for (part, mesh) in exploded:
        assert np.allclose(mesh, raw[part.key] + offsets[part.key])
    for (part, mesh) in half:
        assert np.allclose(mesh, raw[part.key] + offsets[part.key] * 0.5)


def test_camera_limits_contain_the_whole_cloud() -> None:
    """Catch a camera box that would clip the exploded stack."""

    points = np.asarray(
        [(-64.0, -39.0, -250.0), (64.0, 39.0, 270.0), (0.0, 0.0, 0.0)], dtype=float
    )
    limits = camera_limits(points)
    for axis_name, column in (("x", 0), ("y", 1), ("z", 2)):
        low, high = limits[axis_name]
        assert high > low
        if axis_name == "z":
            assert low <= points[:, column].min()
            assert high >= points[:, column].max()


def test_animation_frame_is_even_sized_and_cropped_to_its_content() -> None:
    """Catch frames libx264 cannot encode, or a crop that eats the drawing."""

    raw = _synthetic_raw()
    offsets = _explosion_offsets(raw)
    exploded = scene_at(raw, offsets, 1.0)
    limits = camera_limits(
        np.concatenate([mesh for _part, mesh in exploded]).reshape(-1, 3)
    )
    image = _animation_frame(exploded, limits)
    box = _content_box(image, 12)
    left, top, right, bottom = box
    assert 0 <= left < right <= image.width
    assert 0 <= top < bottom <= image.height
    # libx264 rejects odd dimensions.
    assert (right - left) % 2 == 0 and (bottom - top) % 2 == 0
    cropped = image.crop(box)
    assert cropped.width > 120 and cropped.height > 200
    # The crop must keep the drawing: the background alone would be uniform.
    pixels = np.asarray(cropped, dtype=np.int16)
    assert np.abs(pixels - pixels[0, 0]).sum() > 0


if __name__ == "__main__":
    tests = tuple(
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    )
    for test in tests:
        test()
    print(f"{len(tests)} exploded-view tests passed")
