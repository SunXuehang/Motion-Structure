"""V6: lower the tray to 0.9 mm clearance while keeping total projection <=8%.

Same reference O, FOV and occluder scope as V5. Independent 0.5, 0.25 and
0.125 degree grids are used; only the final fine-grid result is the headline.
"""
from pathlib import Path
import sys,json,math,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
from bracket import rtk_geometry as h
from bracket.rtk_shadow import ORIGIN,make_locator,trace,ray

P=json.loads((ROOT/'reports/rtk_mount_v6_parameters.json').read_text(encoding='utf-8'))

def scene(version):
    if version=='v5':
        parameter_path=ROOT/'tests/rtk_mount_baseline_v5_parameters.json'
        step_path=ROOT/'tests/rtk_mount_baseline_v5.step'
    else:
        assert version=='v6'
        parameter_path=ROOT/'reports/rtk_mount_v6_parameters.json'
        step_path=ROOT/'step/rtk_antenna_mount_v6.step'
    params=json.loads(parameter_path.read_text(encoding='utf-8'))
    shape=h.read_step(step_path)
    vertices,triangles,_=h.mesh(shape,deflection=.025,angular=.10)
    heights=vertices[triangles].mean(axis=1)[:,2]
    category=np.where(heights>=params['plate_bottom_z_mm']-.001,2,np.where(heights>params['clamp_bottom_z_mm']+params['lug_height_mm']+.001,1,3)).astype(np.uint8)
    antenna=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0,0,params['antenna_mount_face_z_mm']),gp_Dir(0,0,1)),params['antenna_diameter_mm']/2,params['antenna_height_mm']).Shape()
    av,at,_=h.mesh(antenna,deflection=.025,angular=.10)
    classes=np.concatenate([category,np.full(len(at),4,dtype=np.uint8)])
    v=np.concatenate([vertices,av]);t=np.concatenate([triangles,at+len(vertices)])
    return make_locator(v,t),classes,len(t)

def evaluate(locator,category,step):
    ae=np.arange(0,360+step/2,step);ee=np.arange(-7,52+step/2,step)
    a,e=np.meshgrid(np.deg2rad((ae[:-1]+ae[1:])/2),np.deg2rad((ee[:-1]+ee[1:])/2))
    d=np.stack([np.cos(e)*np.cos(a),np.cos(e)*np.sin(a),np.sin(e)],axis=-1)
    mask,distance=trace(locator,category,d)
    weights=np.diff(np.sin(np.deg2rad(ee)))[:,None]*np.deg2rad(step)
    total=weights.sum()*mask.shape[1]
    result={'angular_step_deg':step,'rays':int(mask.size),
            'blocked_solid_angle_percent':float(((mask>0)*weights).sum()/total*100),
            'first_hit_class_percent':{str(i):float(((mask==i)*weights).sum()/total*100) for i in range(1,5)}}
    return result,mask,distance,ae,ee

results={};arrays={};fine_step=.125
boundary_results={}
for version in ['v5','v6']:
    locator,category,triangles=scene(version)
    check,_=trace(locator,category,np.array([ray(90,0),ray(0,0),ray(0,51)]))
    assert check.tolist()==[1,0,0],(version,check.tolist())
    runs=[]
    for step in [.5,.25,fine_step]:
        result,mask,distance,ae,ee=evaluate(locator,category,step)
        runs.append(result)
        print(json.dumps({'version':version,**result},ensure_ascii=False),flush=True)
    results[version]={'triangles':triangles,'runs':runs,'fine_result':runs[-1]}
    arrays[version+'_mask']=mask;arrays[version+'_distance_mm']=distance
    arrays['azimuth_edges_deg']=ae;arrays['elevation_edges_deg']=ee
    # Also test the exact published upper boundary, not only cell centres.
    boundary_az=np.arange(0,360,.125)
    boundary_dirs=np.column_stack([math.cos(math.radians(52))*np.cos(np.deg2rad(boundary_az)),
                                  math.cos(math.radians(52))*np.sin(np.deg2rad(boundary_az)),
                                  np.full(len(boundary_az),math.sin(math.radians(52)))])
    boundary_mask,_=trace(locator,category,boundary_dirs)
    boundary_results[version]={str(i):int(np.sum(boundary_mask==i)) for i in range(5)}

v6=results['v6']['fine_result']['blocked_solid_angle_percent']
tray_zero=all(r['first_hit_class_percent']['2']==0 and r['first_hit_class_percent']['4']==0 for r in results['v6']['runs'])
criteria={'requested_max_percent':8.0,'fine_grid_passed':v6<=8.0,
          'all_independent_grids_passed':all(r['blocked_solid_angle_percent']<=8 for r in results['v6']['runs']),
          'fine_vs_quarter_degree_difference_pp':abs(v6-results['v6']['runs'][-2]['blocked_solid_angle_percent']),
          'tray_and_antenna_zero_hits_all_grids':tray_zero,
          'exact_52deg_tray_and_antenna_zero_hits':boundary_results['v6']['2']==0 and boundary_results['v6']['4']==0,
          'analytic_tray_clearance_mm':P['tray_clearance_above_52deg_at_outer_edge_mm'],
          'requested_max_vertical_clearance_mm':1.0,
          'vertical_clearance_passed':0 < P['tray_clearance_above_52deg_at_outer_edge_mm'] <= 1.0,
          'upper_fov_entirely_clear':False}
assert tray_zero and criteria['exact_52deg_tray_and_antenna_zero_hits']
assert criteria['vertical_clearance_passed']
assert abs(P['tray_clearance_above_52deg_at_outer_edge_mm']-.9)<1e-8
report={'method':'Central projection from manual reference O; same FOV, components and solid-angle weighting as V5',
        'origin_mm':ORIGIN.tolist(),'fov_azimuth_deg':[0,360],'fov_elevation_deg':[-7,52],
        'mesh_deflection_mm':.025,'mesh_angular_deflection_rad':.10,'versions':results,'criteria':criteria,
        'post_diameter_mm':P['post_diameter_mm'],'base_and_root_strengthening_unchanged':True,
        'class_codes':{'0':'no new-hardware hit','1':'posts','2':'tray','3':'lower clamp/ears','4':'antenna envelope'},
        'source_manual':'https://terra-1-g.djicdn.com/851d20f7b9f64838a34cd02351370894/Livox/Livox_Mid-360_User_Manual_EN.pdf',
        'source_specs':'https://www.livoxtech.com/mid-360/specs',
        'upper_boundary_52deg_hits_by_class':boundary_results,
        'tray_min_elevation_deg':P['tray_min_elevation_from_O_deg'],
        'height_reduction_from_v5_mm':P['height_reduction_from_v5_mm'],
        'v6_step_sha256':hashlib.sha256((ROOT/'step/rtk_antenna_mount_v6.step').read_bytes()).hexdigest(),
        'limitations':['The 8 percent condition applies only to this sampled geometric solid-angle model, not measured point loss.',
                       'O is a point-cloud coordinate reference, not a verified emitting/receiving pupil.',
                       'Beam divergence, refraction and non-repetitive dwell distribution are not modelled.',
                       'Only new support and antenna envelope are included; cable, SMA connector, fasteners and existing rig are excluded.',
                       'Zero tray/antenna hits does not mean zero upper-FOV obstruction: three post sectors remain.',
                       'Raising the narrow posts reduces stiffness; no strength, creep or physical trial-fit validation is claimed.']}
(ROOT/'reports/rtk_scan_occlusion_v6_20261028.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
np.savez_compressed(ROOT/'reports/rtk_mount_v6_angular_shadow.npz',**arrays)
print(json.dumps({'criteria':criteria,'post_diameter_mm':P['post_diameter_mm']},ensure_ascii=False),flush=True)
