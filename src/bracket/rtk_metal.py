"""Finalized metal mount with wide root shoulders and bolt-and-nut clamping."""
import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.GC import GC_MakeArcOfCircle
from OCP.Geom import Geom_BezierCurve
from OCP.collections import Array1_gp_Pnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt, gp_Dir, gp_Ax2, gp_Vec

from . import rtk_geometry as h

METAL_PARAMS = {
    'status': 'FINALIZED GEOMETRY - MANUFACTURING AND PHYSICAL VALIDATION PENDING',
    'geometry_finalized_date': '2026-11-15',
    'design_approved_by_user': True,
    'geometry_revision': '2 mm closing gap and MID-360 matched contact ribs',
    'candidate_materials': ['316L stainless steel', 'TC4 titanium alloy'],
    'top_thickness_mm': 2.0,
    'screw_pad_diameter_mm': 9.0,
    'antenna_hole_angles_deg': [30.0, 150.0, 270.0],
    'post_angles_deg': [90.0, 210.0, 330.0],
    'top_pattern': 'Three holes and three post tips alternate every 60 degrees on the same pitch circle',
    'top_ring_width_mm': 4.0,
    'root_profile': 'Original inward circular core, outer-only capsule rib, circumferential collar/root fillet',
    'post_circular_core_diameter_mm': 3.1,
    'outer_rib_max_depth_mm': 2.0,
    'post_tangential_width_mm': 3.1,
    'root_transition_half_width_mm': 8.5,
    'root_peak_outer_radius_mm': 31.9,
    'root_top_blend_radius_mm': 0.6,
    'post_toe_radius_mm': 0.4,
    'clamp_radial_wall_mm': 2.0,
    'clamp_edge_radius_mm': 0.4,
    'lug_plan_corner_radius_mm': 1.2,
    'clamp_split_gap_mm': 2.0,
    'lug_half_x_mm': 3.6,
    'lug_height_mm': 7.0,
    'lug_front_y_mm': -26.3,
    'lug_back_y_mm': -35.44,
    'clamp_screw_y_mm': -30.94,
    'clamp_nut_max_diameter_mm': 6.0,
    'clamp_nut_rotation_clearance_mm': 0.5,
    'clamp_rotation_envelope_diameter_mm': 7.0,
    'clamp_clearance_diameter_mm': 3.4,
    'clamp_fastening': 'M3 through-bolt and separate external M3 nut; no tapped holes',
    'lug_thickness_each_mm': 2.6,
    'contact_groove_count': 40,
    'contact_groove_phase_deg': 0.0,
    'contact_groove_center_radius_mm': 26.3,
    'contact_groove_radius_mm': 1.0,
    'contact_groove_clearance_mm': 0.1,
    'contact_rib_end_radius_mm': 0.15,
}


def cylinder(radius, height, x=0, y=0, z=0, direction=(0, 0, 1)):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(*direction)), radius, height).Shape()


def cut(shape, tool):
    op = BRepAlgoAPI_Cut(shape, tool)
    op.Build()
    assert op.IsDone()
    return op.Shape()


def fuse(shapes):
    result = shapes[0]
    for shape in shapes[1:]:
        op = BRepAlgoAPI_Fuse(result, shape)
        # Merge coincident pad/ring edges without leaving near-zero sliver faces.
        op.SetFuzzyValue(1e-6)
        op.Build()
        assert op.IsDone()
        result = op.Shape()
    return result


def round_edges(shape, radius, *, vertical=False):
    fillet = BRepFilletAPI_MakeFillet(shape)
    edges = TopExp_Explorer(shape, TopAbs_EDGE)
    added = 0
    while edges.More():
        edge = TopoDS.Edge(edges.Current())
        size = h.bounds(edge)['size']
        match = size[2] > 1e-4 and size[0] < 1e-4 and size[1] < 1e-4 if vertical else size[2] < 1e-4
        if match:
            fillet.Add(radius, edge)
            added += 1
        edges.Next()
    assert added
    fillet.Build()
    assert fillet.IsDone(), 'edge rounding failed'
    return fillet.Shape()


def broad_collar(p):
    """Three long tangent shoulders follow the user's horizontal red sketch."""
    m = METAL_PARAMS
    inner = p['clamp_inner_diameter_mm']/2
    outer = inner+m['clamp_radial_wall_mm']
    width = m['root_transition_half_width_mm']
    end_y = math.sqrt(outer*outer-width*width)
    handle = 3.0
    shoulder_y = end_y+handle*width/end_y
    # Symmetric quintic Bezier: exact circle tangents, and the specified crest.
    crest_control = (m['root_peak_outer_radius_mm']-end_y/16-5*shoulder_y/16)/(10/16)
    controls = [(-width, end_y), (-width+handle, shoulder_y), (-1.8, crest_control),
                (1.8, crest_control), (width-handle, shoulder_y), (width, end_y)]

    def point(theta, u, v):
        return gp_Pnt(v*math.cos(theta)-u*math.sin(theta),
                      v*math.sin(theta)+u*math.cos(theta), p['clamp_bottom_z_mm'])

    wire = BRepBuilderAPI_MakeWire()
    angles = m['post_angles_deg']
    for i, angle in enumerate(angles):
        theta = math.radians(angle)
        poles = Array1_gp_Pnt(1, 6)
        for j, (u, v) in enumerate(controls, 1):
            poles.SetValue(j, point(theta, u, v))
        wire.Add(BRepBuilderAPI_MakeEdge(Geom_BezierCurve(poles)).Edge())
        next_angle = angles[(i+1) % 3]+(360 if i == 2 else 0)
        middle = math.radians((angle+next_angle)/2)
        arc = GC_MakeArcOfCircle(point(theta, width, end_y), point(middle, 0, outer),
                                  point(math.radians(next_angle), -width, end_y)).Value()
        wire.Add(BRepBuilderAPI_MakeEdge(arc).Edge())
    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    shape = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, p['clamp_contact_height_mm'])).Shape()
    shape = cut(shape, cylinder(inner, p['clamp_contact_height_mm']+2, z=p['clamp_bottom_z_mm']-1))
    return round_edges(shape, m['clamp_edge_radius_mm'])


def metal_post_geometry(p):
    root_z = p['clamp_bottom_z_mm']+p['clamp_contact_height_mm']/2
    tip_radius = p['antenna_hole_triangle_side_mm']/math.sqrt(3)
    inward = p['post_center_radius_mm']-tip_radius
    rise = p['antenna_mount_face_z_mm']-root_z
    return {'root_z_mm': root_z, 'tip_radius_mm': tip_radius,
            'arc_radius_mm': (rise*rise+inward*inward)/(2*inward),
            'arc_angle_deg': math.degrees(2*math.atan(inward/rise)),
            'root_bottom_z_mm': p['clamp_bottom_z_mm']+METAL_PARAMS['clamp_edge_radius_mm'],
            'reinforcement_rule': 'Keep original circular core and inner contour; add material along outward profile normal only'}


def smooth_post(angle, p):
    geometry = metal_post_geometry(p)
    theta = math.radians(angle)
    binormal = gp_Dir(-math.sin(theta), math.cos(theta), 0)
    radius = geometry['arc_radius_mm']
    arc_angle = math.radians(geometry['arc_angle_deg'])

    def center(fraction):
        a = arc_angle*fraction
        r = p['post_center_radius_mm']-radius*(1-math.cos(a))
        return gp_Pnt(r*math.cos(theta), r*math.sin(theta), geometry['root_z_mm']+radius*math.sin(a))

    lower = gp_Pnt(p['post_center_radius_mm']*math.cos(theta),
                   p['post_center_radius_mm']*math.sin(theta), geometry['root_bottom_z_mm'])
    arc = GC_MakeArcOfCircle(center(0), center(.5), center(1)).Value()
    spine = BRepBuilderAPI_MakeWire()
    spine.Add(BRepBuilderAPI_MakeEdge(lower, center(0)).Edge())
    spine.Add(BRepBuilderAPI_MakeEdge(arc).Edge())

    def profile(origin, a, depth):
        # A capsule is the original Ø3.1 circle plus an outward-only extrusion.
        normal = (math.cos(a)*math.cos(theta), math.cos(a)*math.sin(theta), math.sin(a))
        tangent = (-math.sin(theta), math.cos(theta), 0)
        r = p['post_diameter_mm']/2

        def point(u, v):
            return gp_Pnt(origin.X()+u*normal[0]+v*tangent[0],
                          origin.Y()+u*normal[1]+v*tangent[1], origin.Z()+u*normal[2])

        wire = BRepBuilderAPI_MakeWire()
        wire.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(point(0, -r), point(-r, 0), point(0, r)).Value()).Edge())
        wire.Add(BRepBuilderAPI_MakeEdge(point(0, r), point(depth, r)).Edge())
        wire.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(point(depth, r), point(depth+r, 0), point(depth, -r)).Value()).Edge())
        wire.Add(BRepBuilderAPI_MakeEdge(point(depth, -r), point(0, -r)).Edge())
        return wire.Wire()

    pipe = BRepOffsetAPI_MakePipeShell(spine.Wire())
    pipe.SetMode(binormal)
    pipe.Add(profile(lower, 0, 2.0), False, False)
    for fraction, depth in [(0, 2.0), (.35, 2.0), (.7, 1.8), (.9, .5), (1, .02)]:
        pipe.Add(profile(center(fraction), arc_angle*fraction, depth), False, False)
    pipe.Build()
    assert pipe.IsDone() and pipe.MakeSolid()
    shape = pipe.Shape()
    fillet = BRepFilletAPI_MakeFillet(shape)
    edges = TopExp_Explorer(shape, TopAbs_EDGE)
    unique = []
    while edges.More():
        edge = TopoDS.Edge(edges.Current())
        b = h.bounds(edge)
        if (abs(b['min'][2]-geometry['root_bottom_z_mm']) < 1e-5 and b['size'][2] < 1e-5
                and not any(edge.IsSame(old) for old in unique)):
            fillet.Add(METAL_PARAMS['post_toe_radius_mm'], edge)
            unique.append(edge)
        edges.Next()
    assert len(unique) == 4
    fillet.Build()
    assert fillet.IsDone(), 'Rounded post toe failed'
    return fillet.Shape()


def blend_post_roots(shape, p):
    seeds = []
    edges = TopExp_Explorer(shape, TopAbs_EDGE)
    top_z = p['clamp_bottom_z_mm']+p['clamp_contact_height_mm']
    while edges.More():
        edge = TopoDS.Edge(edges.Current())
        bounds = h.bounds(edge)
        center = [(a+b)/2 for a, b in zip(bounds['min'], bounds['max'])]
        theta = math.degrees(math.atan2(center[1], center[0])) % 360
        near_post = min(abs((theta-a+180) % 360-180) for a in METAL_PARAMS['post_angles_deg']) < 8
        if (abs(bounds['min'][2]-top_z) < 1e-4 and bounds['size'][2] < 1e-4
                and math.hypot(*bounds['size'][:2]) < 5.5
                and 26 < math.hypot(*center[:2]) < 32 and near_post
                and not any(edge.IsSame(old) for old in seeds)):
            seeds.append(edge)
        edges.Next()
    assert len(seeds) == 15, 'Expected the five top junction segments at each broad shoulder'
    fillet = BRepFilletAPI_MakeFillet(shape)
    for edge in seeds:
        fillet.Add(METAL_PARAMS['root_top_blend_radius_mm'], edge)
    fillet.Build()
    assert fillet.IsDone(), 'Continuous root blend failed'
    return fillet.Shape()


def build_metal_mount(p):
    """Return the full solid and its ring-linked top, in radar coordinates."""
    m = METAL_PARAMS
    assert math.isclose(m['lug_half_x_mm']-m['clamp_split_gap_mm']/2, m['lug_thickness_each_mm'])
    seat = p['antenna_mount_face_z_mm']
    bottom = seat - m['top_thickness_mm']
    hole_radius = p['antenna_hole_triangle_side_mm'] / math.sqrt(3)
    holes = [(hole_radius*math.cos(math.radians(a)), hole_radius*math.sin(math.radians(a)))
             for a in m['antenna_hole_angles_deg']]
    supports = [cylinder(m['screw_pad_diameter_mm']/2, m['top_thickness_mm'], x, y, bottom) for x, y in holes]
    top_ring = cut(cylinder(hole_radius+m['top_ring_width_mm']/2, m['top_thickness_mm'], z=bottom),
                   cylinder(hole_radius-m['top_ring_width_mm']/2, m['top_thickness_mm']+2, z=bottom-1))
    top = fuse(supports+[top_ring])
    for x, y in holes:
        top = cut(top, cylinder(p['antenna_screw_clearance_diameter_mm']/2, m['top_thickness_mm']+2, x, y, bottom-1))

    z0 = p['clamp_bottom_z_mm']
    height = p['clamp_contact_height_mm']
    inner = p['clamp_inner_diameter_mm']/2
    ring = broad_collar(p)
    screw_z = z0 + p['lug_height_mm']/2
    ear_z = screw_z-m['lug_height_mm']/2
    ears = BRepPrimAPI_MakeBox(gp_Pnt(-m['lug_half_x_mm'], m['lug_back_y_mm'], ear_z),
                               2*m['lug_half_x_mm'], m['lug_front_y_mm']-m['lug_back_y_mm'], m['lug_height_mm']).Shape()
    ears = round_edges(ears, m['lug_plan_corner_radius_mm'], vertical=True)
    ears = round_edges(ears, m['clamp_edge_radius_mm'])
    pieces = [ring, ears, top]
    above_seat = BRepPrimAPI_MakeBox(gp_Pnt(-60, -60, seat), 120, 120, 60).Shape()
    for angle in m['post_angles_deg']:
        pieces.append(cut(smooth_post(angle, p), above_seat))
    shape = fuse(pieces)
    for x, y in holes:
        shape = cut(shape, cylinder(p['antenna_screw_clearance_diameter_mm']/2, 5, x, y, bottom-1))
    shape = cut(shape, cylinder(m['clamp_clearance_diameter_mm']/2, 2*m['lug_half_x_mm']+2,
                               -m['lug_half_x_mm']-1, m['clamp_screw_y_mm'], screw_z, (1, 0, 0)))
    slit = BRepPrimAPI_MakeBox(gp_Pnt(-m['clamp_split_gap_mm']/2, -60, ear_z-1),
                              m['clamp_split_gap_mm'], 60, m['lug_height_mm']+2).Shape()
    shape = cut(shape, slit)
    shape = blend_post_roots(shape, p)
    ribs = []
    rib_radius = m['contact_groove_radius_mm']-m['contact_groove_clearance_mm']
    for i in range(m['contact_groove_count']):
        angle = math.radians(m['contact_groove_phase_deg']+i*360/m['contact_groove_count'])
        x, y = (m['contact_groove_center_radius_mm']*math.cos(angle),
                m['contact_groove_center_radius_mm']*math.sin(angle))
        ribs.append(round_edges(cylinder(rib_radius, height, x, y, z0), m['contact_rib_end_radius_mm']))
    shape = cut(fuse([shape]+ribs), slit)
    assert BRepCheck_Analyzer(shape).IsValid()
    assert h.count(shape, TopAbs_SOLID) == 1
    return shape, top
