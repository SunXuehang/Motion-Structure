"""Shared ray tracing: same O-point central projection as V3."""
import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
import math
ORIGIN=np.array([0.0,0.0,47.0])

def make_locator(vertices,triangles):
    points=vtk.vtkPoints(); points.SetData(numpy_to_vtk(np.ascontiguousarray(vertices,dtype=np.float64),deep=True))
    cells=vtk.vtkCellArray()
    cells.SetData(numpy_to_vtkIdTypeArray(np.arange(0,3*len(triangles)+1,3,dtype=np.int64),deep=True),
                  numpy_to_vtkIdTypeArray(np.ascontiguousarray(triangles.reshape(-1),dtype=np.int64),deep=True))
    poly=vtk.vtkPolyData(); poly.SetPoints(points); poly.SetPolys(cells)
    loc=vtk.vtkStaticCellLocator(); loc.SetDataSet(poly); loc.BuildLocator()
    return loc

def trace(loc,category,directions,origin=ORIGIN):
    endpoint=origin+np.asarray(directions).reshape(-1,3)*5000
    mask=np.zeros(len(endpoint),dtype=np.uint8)
    distance=np.full(len(endpoint),np.nan,dtype=np.float32)
    t=vtk.mutable(0.0); sub=vtk.mutable(0); cell_id=vtk.mutable(0)
    x=[0.,0.,0.]; pc=[0.,0.,0.]; cell=vtk.vtkGenericCell()
    start=tuple(origin)
    for i,end in enumerate(endpoint):
        if loc.IntersectWithLine(start,tuple(end),1e-7,t,x,pc,sub,cell_id,cell):
            mask[i]=category[int(cell_id)]
            distance[i]=float(t)*5000
    return mask.reshape(np.asarray(directions).shape[:-1]),distance.reshape(np.asarray(directions).shape[:-1])

def ray(az,el):
    a,e=math.radians(az),math.radians(el)
    return np.array([math.cos(e)*math.cos(a),math.cos(e)*math.sin(a),math.sin(e)])
