"""Import and deterministically normalize the official Livox MID-360 STEP."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

import FreeCAD as App
import Import
import Part


OFFICIAL_SOURCE_URL = (
    "https://terra-1-g.djicdn.com/65c028cd298f4669a7f0e40e50ba1131/"
    "Mid360/mid-360-asm.stp"
)
OFFICIAL_SHA256 = "b93e9b51282ed319b6aa755e76a132c0eb03306da5f3b9676bcabf2e2ae25f02"


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bbox_dict(box: App.BoundBox) -> dict[str, list[float]]:
    return {
        "min": [round(box.XMin, 9), round(box.YMin, 9), round(box.ZMin, 9)],
        "max": [round(box.XMax, 9), round(box.YMax, 9), round(box.ZMax, 9)],
        "size": [round(box.XLength, 9), round(box.YLength, 9), round(box.ZLength, 9)],
    }


def _center_of_mass(shape: Part.Shape) -> App.Vector:
    total_volume = sum(solid.Volume for solid in shape.Solids)
    if total_volume <= 0.0:
        raise ValueError("official MID-360 assembly has no solid volume")
    weighted = sum(
        (solid.CenterOfMass * solid.Volume for solid in shape.Solids),
        App.Vector(),
    )
    return weighted / total_volume


def _load_top_level_assembly(path: Path) -> Part.Shape:
    document = App.newDocument("OfficialMID360Import")
    try:
        Import.insert(str(path), document.Name)
        document.recompute()
        candidates = [
            obj.Shape
            for obj in document.Objects
            if hasattr(obj, "Shape")
            and not obj.Shape.isNull()
            and len(obj.Shape.Solids) > 0
        ]
        if not candidates:
            raise ValueError("official MID-360 STEP contains no solid assembly")
        assembly = max(candidates, key=lambda shape: (len(shape.Solids), shape.Volume))
        if len(assembly.Solids) != 7:
            raise ValueError(
                "official MID-360 topology changed: "
                f"expected 7 top-level solids, found {len(assembly.Solids)}"
            )
        return assembly.copy()
    finally:
        App.closeDocument(document.Name)


def _normalize(raw: Part.Shape) -> tuple[Part.Shape, dict[str, Any]]:
    """Apply the one rigid transform derived from the official 2024 STEP."""

    raw_box = raw.BoundBox
    center_of_mass = _center_of_mass(raw)

    # The official file uses raw +Y as vertical.  Of the two horizontal axes,
    # raw X has the longer complete envelope.  Its mass center is displaced
    # toward -X relative to the envelope center, so the connector is at +X.
    horizontal_lengths = {"X": raw_box.XLength, "Z": raw_box.ZLength}
    connector_axis = max(horizontal_lengths, key=horizontal_lengths.get)
    if connector_axis != "X":
        raise ValueError(
            "official MID-360 orientation changed: longest horizontal axis is "
            f"{connector_axis}, not X"
        )
    mass_offset = center_of_mass.x - raw_box.Center.x
    if abs(mass_offset) < 1e-6:
        raise ValueError("cannot determine official connector sign from mass offset")
    connector_sign = -1.0 if mass_offset > 0.0 else 1.0

    # Right-handed rotation: raw connector +X -> normalized -Y,
    # raw vertical +Y -> normalized +Z, and raw +Z -> normalized -X.
    matrix = App.Matrix()
    matrix.A11 = 0.0
    matrix.A12 = 0.0
    matrix.A13 = -connector_sign
    matrix.A21 = -connector_sign
    matrix.A22 = 0.0
    matrix.A23 = 0.0
    matrix.A31 = 0.0
    matrix.A32 = 1.0
    matrix.A33 = 0.0
    rotation = App.Rotation(matrix)
    # The official four-hole bottom pattern is centered at raw X=0, Z=0.
    # Rotation therefore centers it in normalized XY without either XY offset.
    translation = App.Vector(0.0, 0.0, -raw_box.YMin)
    transform = App.Placement(translation, rotation)

    normalized = raw.copy()
    normalized.Placement = transform * normalized.Placement
    box = normalized.BoundBox
    if not normalized.isValid():
        raise ValueError("normalized official MID-360 shape is invalid")
    if min(box.XLength, box.YLength, box.ZLength) <= 0.0:
        raise ValueError("normalized official MID-360 shape is empty")
    if box.XLength >= 75.0 or box.YLength >= 75.0 or box.ZLength >= 70.0:
        raise ValueError("normalized official MID-360 exceeds the accepted envelope")
    if abs(box.ZMin) >= 1e-6:
        raise ValueError("normalized official MID-360 bottom is not at Z=0")
    if -box.YMin <= box.YMax:
        raise ValueError(
            "normalized official MID-360 connector does not reach rearward"
        )

    metadata: dict[str, Any] = {
        "source_url": OFFICIAL_SOURCE_URL,
        "solid_count": len(normalized.Solids),
        "raw_bbox_mm": _bbox_dict(raw_box),
        "raw_center_of_mass_mm": [
            round(center_of_mass.x, 9),
            round(center_of_mass.y, 9),
            round(center_of_mass.z, 9),
        ],
        "connector_axis_raw": "+X" if connector_sign > 0.0 else "-X",
        "connector_direction": "-Y",
        "transform": {
            "rotation_matrix": [
                [0.0, 0.0, -connector_sign],
                [-connector_sign, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            "translation_mm": [
                round(translation.x, 9),
                round(translation.y, 9),
                round(translation.z, 9),
            ],
            "mapping": "raw +X -> -Y, raw +Y -> +Z, raw +Z -> -X",
            "mount_pattern_center_raw_xz_mm": [0.0, 0.0],
        },
        "normalized_bbox_mm": _bbox_dict(box),
    }
    return normalized, metadata


def load_normalized_mid360_with_metadata(
    path: Path,
) -> tuple[Part.Shape, dict[str, Any]]:
    """Load the pinned official model and return its normalized shape and audit data."""

    official_path = Path(path)
    if not official_path.is_file():
        raise FileNotFoundError(
            f"official MID-360 STEP is missing: {official_path}; "
            "run scripts/fetch_mid360.sh"
        )
    actual_sha = _file_sha256(official_path)
    if actual_sha != OFFICIAL_SHA256:
        raise ValueError(
            "official MID-360 STEP SHA-256 mismatch: "
            f"expected {OFFICIAL_SHA256}, got {actual_sha}"
        )
    normalized, metadata = _normalize(_load_top_level_assembly(official_path))
    metadata["sha256"] = actual_sha
    return normalized, metadata


def load_normalized_mid360(path: Path) -> Part.Shape:
    """Load exact official geometry with its bottom at Z=0 and connector at -Y."""

    normalized, _ = load_normalized_mid360_with_metadata(path)
    return normalized
