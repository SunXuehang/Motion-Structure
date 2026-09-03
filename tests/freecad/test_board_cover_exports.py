"""Round-trip checks for the UAV V3 board-cover CAD package."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import FreeCAD as App
import Import
import Mesh

PROJECT_SRC = str(Path(__file__).resolve().parents[2] / "src")
assert PROJECT_SRC in sys.path, f"repository src missing from sys.path: {sys.path}"

from bracket.board_cover_package import build_board_cover_outputs


def test_board_cover_package_exports_and_reimports_all_cad_files() -> None:
    """Catch missing, empty, corrupt, or incorrectly named cover exports."""

    with TemporaryDirectory(prefix="uav-v3-covers-") as temporary:
        root = Path(temporary)
        report = build_board_cover_outputs(root)
        expected = (
            root / "exports/UAV_V3_top_cover.step",
            root / "exports/UAV_V3_top_cover.stl",
            root / "exports/UAV_V3_bottom_cover.step",
            root / "exports/UAV_V3_bottom_cover.stl",
            root / "exports/UAV_V3_board_covers_assembly.step",
            root / "models/UAV_V3_board_covers.FCStd",
            root / "reports/UAV_V3_board_cover_validation.json",
        )
        assert all(path.is_file() and path.stat().st_size > 500 for path in expected)
        assert report["reference_mesh_included"] is False
        assert report["mounting_hole_diameter_mm"] == 3.4
        assert report["standoff_outer_diameter_mm"] == 6.0
        assert report["top_standoff_height_mm"] == 10.0
        assert report["bottom_standoff_height_mm"] == 13.0
        assert report["reimports"] == {
            "exports/UAV_V3_board_covers_assembly.step": True,
            "exports/UAV_V3_bottom_cover.step": True,
            "exports/UAV_V3_bottom_cover.stl": True,
            "exports/UAV_V3_top_cover.step": True,
            "exports/UAV_V3_top_cover.stl": True,
        }

        document = App.newDocument("BoardCoverRoundTrip")
        try:
            Import.insert(str(expected[0]), document.Name)
            Mesh.insert(str(expected[1]), document.Name)
            document.recompute()
            part_shapes = [
                obj.Shape
                for obj in document.Objects
                if hasattr(obj, "Shape") and not obj.Shape.isNull()
            ]
            meshes = [
                obj.Mesh
                for obj in document.Objects
                if hasattr(obj, "Mesh") and obj.Mesh.CountFacets > 0
            ]
            assert part_shapes and all(shape.isValid() for shape in part_shapes)
            assert meshes and all(mesh.CountFacets > 0 for mesh in meshes)
        finally:
            App.closeDocument(document.Name)


if __name__ == "__main__":
    test_board_cover_package_exports_and_reimports_all_cad_files()
    print("1 board-cover export test passed")
