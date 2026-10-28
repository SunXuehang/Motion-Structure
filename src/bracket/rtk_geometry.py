"""OCP STEP validation, placement and meshing for the selected RTK mount."""
import base64
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool, BRep_Builder
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.gp import gp_Trsf

def count(shape, kind):
    e, n = TopExp_Explorer(shape, kind), 0
    while e.More():
        n += 1
        e.Next()
    return n

def bounds(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    low, high = box.CornerMin(), box.CornerMax()
    values = np.array([low.X(), low.Y(), low.Z(), high.X(), high.Y(), high.Z()])
    return {"min": values[:3].round(6).tolist(), "max": values[3:].round(6).tolist(),
            "size": (values[3:] - values[:3]).round(6).tolist()}

def volume(shape):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return props.Mass()

def read_step(path):
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone, path
    assert reader.TransferRoots() > 0, path
    shape = reader.OneShape()
    assert BRepCheck_Analyzer(shape).IsValid(), path
    return shape

def placed(shape, *, flip=False, y=0.0, z=0.0):
    s = -1.0 if flip else 1.0
    tr = gp_Trsf()
    tr.SetValues(1, 0, 0, 0, 0, s, 0, y, 0, 0, s, z)
    return BRepBuilderAPI_Transform(shape, tr, True).Shape()

def mesh(shape, deflection=0.35, angular=0.4):
    BRepMesh_IncrementalMesh(shape, deflection, False, angular, True).Perform()
    vertices, triangles, lookup = [], [], {}
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face(exp.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is not None:
            local = {}
            for i in range(1, triangulation.NbNodes() + 1):
                p = triangulation.Node(i).Transformed(location.Transformation())
                key = tuple(round(v, 3) for v in (p.X(), p.Y(), p.Z()))
                if key not in lookup:
                    lookup[key] = len(vertices)
                    vertices.append(key)
                local[i] = lookup[key]
            for i in range(1, triangulation.NbTriangles() + 1):
                a, b, c = triangulation.Triangle(i).Get()
                if face.Orientation() == TopAbs_REVERSED:
                    b, c = c, b
                triangles.append([local[a], local[b], local[c]])
        exp.Next()
    vertices, triangles = np.array(vertices), np.array(triangles, dtype=np.uint32)
    assert len(vertices) > 0
    assert triangles.max() < len(vertices)
    encoded = {"vertices": base64.b64encode(np.rint(vertices * 100).astype('<i2').tobytes()).decode(),
               "triangles": base64.b64encode(triangles.astype('<u4').tobytes()).decode()}
    return vertices, triangles, encoded

def export_compound(parts, path):
    compound, builder = TopoDS_Compound(), BRep_Builder()
    builder.MakeCompound(compound)
    for item in parts:
        builder.Add(compound, item)
    writer = STEPControl_Writer()
    assert writer.Transfer(compound, STEPControl_AsIs) == IFSelect_RetDone
    assert writer.Write(str(path)) == IFSelect_RetDone
    reread = read_step(path)
    assert count(reread, TopAbs_SOLID) == sum(count(part, TopAbs_SOLID) for part in parts)
    return bounds(reread)
