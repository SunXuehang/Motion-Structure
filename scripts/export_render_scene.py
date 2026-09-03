"""Export tessellated R45 assembly scenes from FreeCAD to portable JSON."""

import json
from pathlib import Path
import sys

from bracket.assembly import REVIEW_ANGLES, build_assembly
from bracket.official_sensor import load_normalized_mid360
from bracket.parameters import BracketParameters


def _mesh(name, color, shape):
    vertices, triangles = shape.tessellate(0.8)
    return {
        "name": name,
        "color": color,
        "vertices": [[point.x, point.y, point.z] for point in vertices],
        "triangles": [list(triangle) for triangle in triangles],
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: export_render_scene.py OUTPUT_JSON")
    root = Path(__file__).resolve().parents[1]
    p = BracketParameters()
    sensor = load_normalized_mid360(root / "vendor/livox/mid-360-asm.stp")
    scenes = []
    for angle in REVIEW_ANGLES:
        shapes = build_assembly(p, sensor, angle)
        meshes = [
            _mesh("B", "#72a9d3", shapes.part_b),
            _mesh("A", "#f29a3d", shapes.part_a),
            _mesh("MID-360", "#596579", shapes.sensor),
        ]
        for index, screw in enumerate(shapes.m25_screws, start=1):
            meshes.append(_mesh(f"M2.5-{index}", "#b8bec8", screw))
        for index, screw in enumerate(shapes.m3_screws, start=1):
            meshes.append(_mesh(f"M3-{index}", "#b8bec8", screw))
        scenes.append({"angle_deg": angle, "meshes": meshes})
    Path(sys.argv[1]).write_text(
        json.dumps({"scenes": scenes}, separators=(",", ":")),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
