"""HX-CUX623A / MID-360 revision 6: lower the tray to 0.9 mm FOV clearance.

Selected geometry, still pending physical trial fit. This independent OCP
entry point does not replace the project's standard FreeCAD generator.
Install requirements_rtk.txt before running.
"""
from pathlib import Path
import hashlib
import json
import math
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT/'src'))
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
from OCP.GC import GC_MakeArcOfCircle
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeCone
from OCP.TopAbs import TopAbs_SOLID, TopAbs_OUT, TopAbs_IN
from OCP.TopExp import TopExp_Explorer
from OCP.gp import gp_Pnt, gp_Dir, gp_Trsf, gp_Ax1, gp_Ax2, gp_Circ
from bracket import rtk_geometry as h
from bracket.parameters import BracketParameters

bracket_parameters = BracketParameters()

PARAMS = {
    'status': 'REVIEW PROTOTYPE - NOT A RELEASED PRINT DESIGN',
    'ring_nominal_diameter_mm': 51.0,
    'ring_cad_cylindrical_band_z_mm': [34.0171, 38.4991],
    'clamp_inner_diameter_mm': 51.2,
    'clamp_radial_wall_mm': 3.5,
    'clamp_bottom_z_mm': 34.25,
    'clamp_contact_height_mm': 4.0,
    'split_gap_mm': 0.8,
    'clamp_screw_hole_diameter_mm': 3.4,
    'clamp_screw_count': 1,
    'printed_part_count': 1,
    'heatset_pilot_diameter_mm': bracket_parameters.a_insert_hole_diameter,
    'heatset_pilot_depth_mm': bracket_parameters.a_insert_hole_depth,
    'heatset_specification': 'M3 brass insert; pilot dimensions reused directly from Part A parameters',
    'lug_half_x_mm': 7.0,
    'lug_y_center_mm': 30.8,
    'lug_y_width_mm': 9.0,
    'lug_height_mm': 6.8,
    'post_count': 3,
    'post_center_radius_mm': 28.3,
    'post_top_center_radius_mm': 11.0,
    'post_profile': 'circular arc, vertical tangent at fixed lower endpoint',
    'post_angles_deg': [90.0, 210.0, 330.0],
    'post_diameter_mm': 3.1,
    'post_root_diameter_mm': 5.0,
    'post_root_tip_diameter_mm': 4.0,
    'post_root_blend_height_mm': 3.0,
    'antenna_diameter_mm': 43.6,
    'antenna_height_mm': 40.8,
    'antenna_mount_thread': '#3-48 UNC (3 screws, Harxon official specification)',
    'antenna_hole_triangle_side_mm': 23.0,
    'antenna_hole_pitch_source': 'User supplied; not independently verified in a manufacturer mechanical drawing',
    'antenna_screw_clearance_diameter_mm': 3.0,
    'plate_diameter_mm': 48.0,
    'plate_thickness_mm': 4.0,
    'sma_center_opening_diameter_mm': 14.0,
    'sma_downward_height_user_mm': 16.5,
    'target_tray_vertical_fov_clearance_mm': 0.9,
    'height_control': 'Tray underside outer edge, vertical distance above the nominal 52 degree cone from O',
    'reference_origin_z_mm': 47.0,
    'published_upper_fov_deg': 52.0,
    'sma_width_and_cable_bend_radius': 'Unspecified; central opening and rear under-plate path require trial fit',
}
P = PARAMS


def box(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def cylinder(radius, height, x=0, y=0, z=0, direction=(0, 0, 1)):
    from OCP.gp import gp_Ax2
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(*direction)), radius, height).Shape()


def fuse_all(shapes):
    result = shapes[0]
    for shape in shapes[1:]:
        op = BRepAlgoAPI_Fuse(result, shape)
        op.Build(); assert op.IsDone()
        result = op.Shape()
    return result


def cut(shape, cutter):
    op = BRepAlgoAPI_Cut(shape, cutter)
    op.Build(); assert op.IsDone()
    return op.Shape()


def move(shape, x=0, y=0, z=0):
    tr = gp_Trsf(); tr.SetValues(1,0,0,x,0,1,0,y,0,0,1,z)
    return BRepBuilderAPI_Transform(shape, tr, True).Shape()


def rotate_z(shape, degrees):
    tr=gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)),math.radians(degrees))
    return BRepBuilderAPI_Transform(shape,tr,True).Shape()


def interference(a, b):
    ab,bb=h.bounds(a),h.bounds(b)
    if any(ab['min'][i]>bb['max'][i] or bb['min'][i]>ab['max'][i] for i in range(3)):
        return 0.0
    op=BRepAlgoAPI_Common(a,b); op.Build(); assert op.IsDone()
    return abs(h.volume(op.Shape()))


source = ROOT / 'vendor/livox/mid-360-asm.stp'
assert hashlib.sha256(source.read_bytes()).hexdigest() == 'b93e9b51282ed319b6aa755e76a132c0eb03306da5f3b9676bcabf2e2ae25f02'
raw_mid = h.read_step(source)
raw_box = h.bounds(raw_mid)
tr=gp_Trsf(); tr.SetValues(0,0,-1,0,-1,0,0,0,0,1,0,-raw_box['min'][1])
mid = BRepBuilderAPI_Transform(raw_mid,tr,True).Shape()
glass_top = h.bounds(mid)['max'][2]
plate_z = (P['reference_origin_z_mm']
           + P['plate_diameter_mm']/2*math.tan(math.radians(P['published_upper_fov_deg']))
           + P['target_tray_vertical_fov_clearance_mm'])
mount_z = plate_z + P['plate_thickness_mm']
P['mount_face_above_glass_apex_mm'] = mount_z-glass_top
P['sma_nominal_vertical_clearance_mm'] = P['mount_face_above_glass_apex_mm']-P['sma_downward_height_user_mm']
P['height_increase_from_v4_mm'] = P['mount_face_above_glass_apex_mm']-20.0
P['height_reduction_from_v5_mm'] = 25.0-P['mount_face_above_glass_apex_mm']
P['glass_apex_z_mm'] = glass_top
P['antenna_mount_face_z_mm'] = mount_z
P['plate_bottom_z_mm'] = plate_z
top_edge_angle=math.degrees(math.atan2(plate_z-P['reference_origin_z_mm'],P['plate_diameter_mm']/2))
top_clearance=plate_z-P['reference_origin_z_mm']-P['plate_diameter_mm']/2*math.tan(math.radians(P['published_upper_fov_deg']))
assert 0 < top_clearance <= 1.0
assert abs(top_clearance-P['target_tray_vertical_fov_clearance_mm']) < 1e-8
P['tray_min_elevation_from_O_deg']=top_edge_angle
P['tray_clearance_above_52deg_at_outer_edge_mm']=top_clearance

ri=P['clamp_inner_diameter_mm']/2
ro=ri+P['clamp_radial_wall_mm']
z0=P['clamp_bottom_z_mm']; ch=P['clamp_contact_height_mm']
ring=cut(cylinder(ro,ch,z=z0), cylinder(ri,ch+2,z=z0-1))
plate=cylinder(P['plate_diameter_mm']/2,P['plate_thickness_mm'],z=plate_z)
pieces=[ring,plate]
post_axes=[]
post_top_axes=[]
root_z=z0+ch/2
rise=mount_z-root_z
inward=P['post_center_radius_mm']-P['post_top_center_radius_mm']
arc_radius=(rise*rise+inward*inward)/(2*inward)
arc_angle=2*math.atan(inward/rise)
P['post_arc_radius_mm']=arc_radius
P['post_arc_angle_deg']=math.degrees(arc_angle)
P['post_root_z_mm']=root_z

def arc_point(theta, fraction):
    a=arc_angle*fraction
    r=P['post_center_radius_mm']-arc_radius*(1-math.cos(a))
    return gp_Pnt(r*math.cos(theta),r*math.sin(theta),root_z+arc_radius*math.sin(a))

for angle in P['post_angles_deg']:
    theta=math.radians(angle)
    x=P['post_center_radius_mm']*math.cos(theta)
    y=P['post_center_radius_mm']*math.sin(theta)
    post_axes.append((x,y))
    post_top_axes.append((P['post_top_center_radius_mm']*math.cos(theta),P['post_top_center_radius_mm']*math.sin(theta)))
    curve=GC_MakeArcOfCircle(arc_point(theta,0),arc_point(theta,.5),arc_point(theta,1)).Value()
    spine=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(curve).Edge()).Wire()
    circle=gp_Circ(gp_Ax2(gp_Pnt(x,y,root_z),gp_Dir(0,0,1)),P['post_diameter_mm']/2)
    profile=BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()).Face()
    pipe=BRepOffsetAPI_MakePipe(spine,profile); pipe.Build(); assert pipe.IsDone()
    pieces.append(pipe.Shape())
    pieces.append(BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(x,y,root_z),gp_Dir(0,0,1)),
                   P['post_root_diameter_mm']/2,P['post_root_tip_diameter_mm']/2,P['post_root_blend_height_mm']).Shape())
# Inward post tips join directly inside the tray, so the old radial tabs are omitted.
# A single pair of ears closes the rear (-Y) slit.
lug_y=-P['lug_y_center_mm']
pieces.append(box(-P['lug_half_x_mm'],lug_y-P['lug_y_width_mm']/2,z0,
                  2*P['lug_half_x_mm'],P['lug_y_width_mm'],P['lug_height_mm']))
full=fuse_all(pieces)
# A swept tube has a tilted end face; trim it flush with the antenna seat.
full=cut(full,box(-60,-60,mount_z,120,120,20))
# The opening is for the SMA connector; the cable exits rearward below the tray.
full=cut(full,cylinder(P['sma_center_opening_diameter_mm']/2,6,z=plate_z-1))
hole_radius=P['antenna_hole_triangle_side_mm']/math.sqrt(3)
antenna_axes=[(hole_radius*math.cos(math.radians(a)),hole_radius*math.sin(math.radians(a))) for a in [0,120,240]]
for x,y in antenna_axes:
    full=cut(full,cylinder(P['antenna_screw_clearance_diameter_mm']/2,6,x,y,plate_z-1))
screw_z=z0+P['lug_height_mm']/2
full=cut(full,cylinder(P['clamp_screw_hole_diameter_mm']/2,20,-10,lug_y,screw_z,(1,0,0)))
# The right outer ear takes the same nominal Ø4 x 3 insert seat as Part A.
insert_start=P['lug_half_x_mm']-P['heatset_pilot_depth_mm']
full=cut(full,cylinder(P['heatset_pilot_diameter_mm']/2,P['heatset_pilot_depth_mm']+.2,
                       insert_start,lug_y,screw_z,(1,0,0)))
clamp_axes=[(lug_y,screw_z)]
gap=P['split_gap_mm']
mount=cut(full,box(-gap/2,-50,z0-1,gap,50,P['lug_height_mm']+2))
assert BRepCheck_Analyzer(mount).IsValid()
assert h.count(mount,TopAbs_SOLID)==1
assert h.volume(mount)>100
assert all(abs(math.dist(a,b)-23)<1e-8 for i,a in enumerate(antenna_axes) for b in antenna_axes[i+1:])
# Check all three antenna axes against real solid geometry, with nearby material.
for x,y in antenna_axes:
    assert BRepClass3d_SolidClassifier(mount,gp_Pnt(x,y,plate_z+2),1e-6).State()==TopAbs_OUT
    assert BRepClass3d_SolidClassifier(mount,gp_Pnt(x+3 if x>0 else x-3,y,plate_z+2),1e-6).State()==TopAbs_IN
# Distinguish the Ø3.4 passage from the larger, 3 mm deep heat-set seat.
for x,y,z,state in [(-3,lug_y,screw_z,TopAbs_OUT),(3,lug_y,screw_z,TopAbs_OUT),
                     (insert_start-.1,lug_y+1.85,screw_z,TopAbs_IN),
                     (insert_start+.1,lug_y+1.85,screw_z,TopAbs_OUT),
                     (5.5,lug_y+2.15,screw_z,TopAbs_IN),
                     (0,lug_y,screw_z,TopAbs_OUT),(0,28,z0+2,TopAbs_IN)]:
    assert BRepClass3d_SolidClassifier(mount,gp_Pnt(x,y,z),1e-6).State()==state,(x,y,z)
# Check the true normal section of each curved tube, rather than a horizontal cut.
for angle in P['post_angles_deg']:
    theta=math.radians(angle); center=arc_point(theta,.5)
    normal=[math.cos(arc_angle/2)*math.cos(theta),math.cos(arc_angle/2)*math.sin(theta),math.sin(arc_angle/2)]
    assert BRepClass3d_SolidClassifier(mount,center,1e-6).State()==TopAbs_IN
    inside_radius=P['post_diameter_mm']/2-.1
    inside=gp_Pnt(center.X()+inside_radius*normal[0],center.Y()+inside_radius*normal[1],center.Z()+inside_radius*normal[2])
    assert BRepClass3d_SolidClassifier(mount,inside,1e-6).State()==TopAbs_IN
    outside_radius=P['post_diameter_mm']/2+.1
    outside=gp_Pnt(center.X()+outside_radius*normal[0],center.Y()+outside_radius*normal[1],center.Z()+outside_radius*normal[2])
    assert BRepClass3d_SolidClassifier(mount,outside,1e-6).State()==TopAbs_OUT

# Verify that the clamping band and tightening ears match V2 geometrically.
v2=h.read_step(ROOT/'tests/rtk_mount_baseline_v2.step')
base_box=box(-45,-45,z0-1,90,90,ch+1)
v2_base=BRepAlgoAPI_Common(v2,base_box).Shape()
v3_base=BRepAlgoAPI_Common(mount,base_box).Shape()
base_difference=h.volume(cut(v2_base,v3_base))+h.volume(cut(v3_base,v2_base))
assert abs(base_difference)<1e-3,base_difference
ear_box=box(-8,lug_y-5,z0-1,16,10,P['lug_height_mm']+2)
v2_ear=BRepAlgoAPI_Common(v2,ear_box).Shape()
v3_ear=BRepAlgoAPI_Common(mount,ear_box).Shape()
ear_difference=h.volume(cut(v2_ear,v3_ear))+h.volume(cut(v3_ear,v2_ear))
assert abs(ear_difference)<1e-3,ear_difference

nominal_interference={'mount_mid_mm3':interference(mount,mid)}
assert max(nominal_interference.values())<1e-3,nominal_interference
installation_checks=[]
for offset in [0,5,10,20,30]:
    overlap=interference(move(mount,z=offset),mid)
    assert overlap<1e-3,(offset,overlap)
    installation_checks.append({'upward_offset_mm':offset,'overlap_mm3':overlap})

antenna=cylinder(P['antenna_diameter_mm']/2,P['antenna_height_mm'],z=mount_z)
assert interference(antenna,mount)<1e-4
h.export_compound([mount],ROOT/'step/rtk_antenna_mount_v6.step')

# Restore the existing standing device structure to the board-local frame.
radar_z=73.1522; radar_y=-5.0; base_z=56.1522
old_parts={
    'a':h.placed(h.read_step(ROOT/'step/part_a_radar_plate.step'),y=radar_y,z=radar_z),
    'b':h.placed(h.read_step(ROOT/'step/part_b_tilt_base.step'),z=base_z),
    'upper':h.read_step(ROOT/'step/board_cover_upper.step'),
    'lower':h.read_step(ROOT/'step/board_cover_lower.step'),
    'standing':h.read_step(ROOT/'step/standing_handle_body.step'),
}
tilt_checks=[]
for angle in [0,20,40]:
    tr=gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(0,33,70.1522),gp_Dir(1,0,0)),math.radians(-angle))
    collision=[]
    for shape in [mount,antenna]:
        placed=move(shape,y=radar_y,z=radar_z)
        rotated=BRepBuilderAPI_Transform(placed,tr,True).Shape()
        collision.append(interference(rotated,old_parts['b']))
    assert max(collision)<1e-3,(angle,collision)
    tilt_checks.append({'angle_deg':angle,'new_parts_vs_B_overlap_mm3':collision})

full_machine=list(old_parts.values())+[move(s,y=radar_y,z=radar_z) for s in [mid,mount,antenna]]
h.export_compound(full_machine,ROOT/'step/standing_device_with_rtk_v6.step')

evidence={
    'parameters':P,
    'units':'mm',
    'reference_frame':'MID-360 bottom mount plane Z=0, rear connector along -Y',
    'antenna_axes_xy_mm':antenna_axes,
    'clamp_axes_yz_mm':clamp_axes,
    'post_axes_xy_mm':post_axes,
    'post_top_axes_xy_mm':post_top_axes,
    'base_region_symmetric_difference_vs_v2_mm3':base_difference,
    'ear_region_symmetric_difference_vs_v2_mm3':ear_difference,
    'mount_bounds_mm':h.bounds(mount),
    'mount_volume_mm3':h.volume(mount),
    'mount_solid_count':h.count(mount,TopAbs_SOLID),
    'heatset_dimension_source':{'file':'src/bracket/parameters.py','diameter_parameter':'a_insert_hole_diameter','depth_parameter':'a_insert_hole_depth'},
    'heatset_layout':'Right ear outer face: Ø4 x 3 seat; coaxial Ø3.4 passage; left ear Ø3.4 through-hole.',
    'nominal_interference':nominal_interference,
    'installation_path_samples':installation_checks,
    'compliance_note':'Undeformed nominal geometry only. Ring expansion, the stiffening effect of the three columns and top tray, clamping pressure, friction and creep are not simulated.',
    'tilt_checks':tilt_checks,
    'sources':{
        'antenna_official':'https://www.harxon.com/product/detail/2',
        'user_link':'https://www.indianhobbycenter.com/products/harxon-hx-cux623a-low-profile-high-performance-helix-antenna-for-uavs-and-surveying',
        'mid360_download':'https://www.livoxtech.com/mid-360/downloads',
        'mid360_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'manual':'https://terra-1-g.djicdn.com/851d20f7b9f64838a34cd02351370894/Livox/Livox_Mid-360_User_Manual_EN.pdf',
    },
    'limitations':[
        'Official Livox manual states MID-360 must not bear extra payload; this clamp is not a manufacturer-approved load-bearing interface.',
        'Ring material identification is inferred from the manual figure and CAD location, not certified material metadata.',
        'Ring diameter, exposed band height and clamping force require physical verification; the 0.1 mm clearance is provisional.',
        'Antenna triangle pitch and SMA height were supplied by the user; no official drawing with thread depth was found.',
        'Antenna solid is only a cylindrical envelope. Screws, nuts and the SMA cable are not modelled.',
        'The three supports and local screw ears may obstruct LiDAR rays. No zero-occlusion claim is made.',
        'No camera-reference interference, full optical analysis, structural load analysis, or physical trial fit was performed.',
        'A continuous top tray links all three columns; actual elastic opening and clamping compliance require physical trial fit.',
        'Heat-set pilot diameter and depth match Part A defaults; actual brass insert fit and screw engagement remain to be verified.',
        'PLA print orientation, supports, threaded-fastener lengths and screw engagement depth are not released manufacturing specifications.',
    ],
}
(ROOT/'reports/rtk_mount_v6_parameters.json').write_text(json.dumps(P,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'reports/rtk_mount_review_v6_20261028.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'step_directory':str(ROOT/'step'),'parameters':P,'nominal_interference':nominal_interference,'tilt_checks':tilt_checks},ensure_ascii=False,indent=2),flush=True)
