"""Standalone interactive 3D view of the verified V6 geometric shadow data.

Metric: fine central-projection grid. Display: aggregated angular patches and
sampled shadow-volume side curtains, at stated illustrative radial scales.
"""
from pathlib import Path
import sys,json,math,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Trsf,gp_Ax2,gp_Pnt,gp_Dir
from bracket import rtk_geometry as h
from bracket.rtk_shadow import ORIGIN,make_locator

P=json.loads((ROOT/'reports/rtk_mount_v6_parameters.json').read_text(encoding='utf-8'))
report=json.loads((ROOT/'reports/rtk_scan_occlusion_v6_20261028.json').read_text(encoding='utf-8'))
assert report['post_diameter_mm']==P['post_diameter_mm']
assert report['criteria']['fine_grid_passed'] and report['criteria']['all_independent_grids_passed']
assert report['criteria']['tray_and_antenna_zero_hits_all_grids']
assert report['criteria']['exact_52deg_tray_and_antenna_zero_hits']
assert report['criteria']['vertical_clearance_passed']
assert hashlib.sha256((ROOT/'step/rtk_antenna_mount_v6.step').read_bytes()).hexdigest()==report['v6_step_sha256']
percent=report['versions']['v6']['fine_result']['blocked_solid_angle_percent']
baseline=report['versions']['v5']['fine_result']['blocked_solid_angle_percent']
data=np.load(ROOT/'reports/rtk_mount_v6_angular_shadow.npz')
mask=data['v6_mask'];distance=data['v6_distance_mm']
ae=data['azimuth_edges_deg'];ee=data['elevation_edges_deg']
metric_weights=np.diff(np.sin(np.deg2rad(ee)))[:,None]
render_data_percent=float(((mask>0)*metric_weights).sum()/(metric_weights.sum()*mask.shape[1])*100)
assert abs(render_data_percent-percent)<1e-9,(render_data_percent,percent)
assert not np.any((mask==2)|(mask==4)), 'Rendering data must agree with V6 zero tray/antenna hits'
ac=(ae[:-1]+ae[1:])/2;ec=(ee[:-1]+ee[1:])/2
na,ne=8,4 # 1 degree azimuth, 0.5 degree elevation for display only.
blocks=mask.reshape(mask.shape[0]//ne,ne,mask.shape[1]//na,na)
counts=np.stack([(blocks==i).sum(axis=(1,3)) for i in range(5)])
display=np.argmax(counts,axis=0).astype(np.uint8)
da=ae[::na];de=ee[::ne]
assert display.shape==(118,360) and da[-1]==360 and de[-1]==52

def spherical(azimuth,elevation,radius):
    a=np.deg2rad(azimuth);e=np.deg2rad(elevation)
    return ORIGIN+np.stack([radius*np.cos(e)*np.cos(a),radius*np.cos(e)*np.sin(a),radius*np.sin(e)],axis=-1)

def patch(radius,kind):
    az,el=np.meshgrid(da,de)
    vertices=spherical(az,el,radius).reshape(-1,3)
    row,col=np.where(display==kind)
    a=row*(display.shape[1]+1)+col;b=a+1;c=a+display.shape[1]+1;d=c+1
    triangles=np.concatenate([np.column_stack([a,b,d]),np.column_stack([a,d,c])])
    used,inverse=np.unique(triangles.reshape(-1),return_inverse=True)
    return vertices[used],inverse.reshape(-1,3)

def curtains(radius):
    vertices=[];triangles=[]
    for center in P['post_angles_deg']:
        columns=np.flatnonzero((ac>center-20)&(ac<center+20))
        for side in ['left','right']:
            points=[]
            for row in range(0,len(ec),4):
                hits=columns[mask[row,columns]==1]
                if not len(hits):continue
                col=hits[0] if side=='left' else hits[-1]
                near=float(distance[row,col])
                if not 0<near<radius:continue
                points.append((spherical(ac[col],ec[row],near),spherical(ac[col],ec[row],radius)))
            start=len(vertices)
            for near,far in points:vertices.extend([near,far])
            for i in range(len(points)-1):
                a=start+2*i;triangles.extend([[a,a+1,a+3],[a,a+3,a+2]])
    return np.array(vertices),np.array(triangles,dtype=np.int32)

def display_decimate(vertices,triangles,max_faces):
    if len(triangles)<=max_faces:return vertices,triangles
    poly=make_locator(vertices,triangles).GetDataSet()
    decimate=vtk.vtkQuadricDecimation();decimate.SetInputData(poly)
    decimate.SetTargetReduction(1-max_faces/len(triangles));decimate.Update()
    out=decimate.GetOutput()
    offsets=vtk_to_numpy(out.GetPolys().GetOffsetsArray())
    assert np.all(np.diff(offsets)==3)
    return vtk_to_numpy(out.GetPoints().GetData()),vtk_to_numpy(out.GetPolys().GetConnectivityArray()).reshape(-1,3)

# Real CAD supplies all displayed hardware; only the antenna is an envelope.
mid=h.read_step(ROOT/'vendor/livox/mid-360-asm.stp');raw=h.bounds(mid)
tr=gp_Trsf();tr.SetValues(0,0,-1,0,-1,0,0,0,0,1,0,-raw['min'][1])
mid=BRepBuilderAPI_Transform(mid,tr,True).Shape()
mv,mt,_=h.mesh(mid)
mv,mt=display_decimate(mv,mt,9500)
window=mv[mt].mean(axis=1)[:,2]>38.55
sv,st,_=h.mesh(h.read_step(ROOT/'step/rtk_antenna_mount_v6.step'),deflection=.12,angular=.22)
antenna=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0,0,P['antenna_mount_face_z_mm']),gp_Dir(0,0,1)),P['antenna_diameter_mm']/2,P['antenna_height_mm']).Shape()
av,at,_=h.mesh(antenna)

fig=make_subplots(rows=1,cols=2,specs=[[{'type':'scene'},{'type':'scene'}]],column_widths=[.64,.36],horizontal_spacing=.025,
                  subplot_titles=('全视场与外推阴影 · 显示半径 160 mm','近场结构与阴影 · 显示半径 65 mm'))

def mesh_trace(vertices,triangles,color,name,opacity,col,group=None):
    if not len(triangles):return
    fig.add_trace(go.Mesh3d(x=vertices[:,0].astype(np.float32),y=vertices[:,1].astype(np.float32),z=vertices[:,2].astype(np.float32),
                           i=triangles[:,0].astype(np.int32),j=triangles[:,1].astype(np.int32),k=triangles[:,2].astype(np.int32),
                           color=color,opacity=opacity,flatshading=False,name=name,legendgroup=group or name,
                           showlegend=col==1,hoverinfo='skip',lighting={'ambient':.68,'diffuse':.65,'specular':.1,'roughness':.9}),row=1,col=col)

for col,radius in [(1,160.0),(2,65.0)]:
    mesh_trace(mv,mt[~window],'#a8b2b8','雷达外壳',1,col)
    mesh_trace(mv,mt[window],'#43545f','光学窗（示意透明）',.34,col)
    mesh_trace(sv,st,'#428b8d',f'Ø{P["post_diameter_mm"]:g} 弧柱及抱箍',1,col)
    mesh_trace(av,at,'#d7a33c','天线外形包络',.92,col)
    for kind,color,label in [(1,'#e58a28','立柱阴影'),(2,'#b34e70','托盘上沿阴影')]:
        vertices,triangles=patch(radius,kind)
        mesh_trace(vertices,triangles,color,label,.62,col)
    vertices,triangles=curtains(radius)
    before=len(fig.data)
    mesh_trace(vertices,triangles,'#e58a28','阴影侧边界',.12,col,group='立柱阴影')
    fig.data[-1].showlegend=False
    lines=[]
    for elevation in [-7,0,30,52]:
        lines.append(spherical(np.linspace(0,360,181),np.full(181,elevation),radius))
    for azimuth in range(0,360,30):
        lines.append(spherical(np.full(61,azimuth),np.linspace(-7,52,61),radius))
    xyz=np.concatenate([np.vstack([line,[np.nan,np.nan,np.nan]]) for line in lines])
    fig.add_trace(go.Scatter3d(x=xyz[:,0],y=xyz[:,1],z=xyz[:,2],mode='lines',line={'color':'#8ba8b9','width':1},opacity=.32,
                               name='名义视场边界',legendgroup='名义视场边界',showlegend=col==1,hoverinfo='skip'),row=1,col=col)
    # Sample actual first intersections on each post; each ray continues outward.
    ray_lines=[];first=[]
    for center in P['post_angles_deg']:
        c=int(np.argmin(abs(ac-center)))
        for elevation in [0,20,40]:
            r=int(np.argmin(abs(ec-elevation)))
            if mask[r,c]!=1:continue
            near=spherical(ac[c],ec[r],float(distance[r,c]));far=spherical(ac[c],ec[r],radius)
            first.append(near);ray_lines.extend([near,far,[np.nan,np.nan,np.nan]])
    xyz=np.array(ray_lines);dots=np.array(first)
    fig.add_trace(go.Scatter3d(x=xyz[:,0],y=xyz[:,1],z=xyz[:,2],mode='lines',line={'color':'#b86d22','width':2},opacity=.7,
                               name='被挡方向外推',legendgroup='立柱阴影',showlegend=False,hoverinfo='skip'),row=1,col=col)
    fig.add_trace(go.Scatter3d(x=dots[:,0],y=dots[:,1],z=dots[:,2],mode='markers',marker={'color':'#bd411e','size':2.5},
                               name='几何首交点',legendgroup='几何首交点',showlegend=col==1,hoverinfo='skip'),row=1,col=col)
    fig.add_trace(go.Scatter3d(x=[0],y=[0],z=[47],mode='markers+text',text=['O'],textposition='top center',
                               marker={'color':'#293d4b','size':3},name='投影参考 O',showlegend=False,hoverinfo='skip'),row=1,col=col)

camera={'eye':{'x':1.32,'y':-1.36,'z':.92},'up':{'x':0,'y':0,'z':1}}
for name,span,zmax in [('scene',172,183),('scene2',72,140)]:
    axis={'showbackground':False,'gridcolor':'#dce4e9','zerolinecolor':'#b8c8d3','showspikes':False,'tickfont':{'size':11}}
    fig.update_layout({name:{'xaxis':{**axis,'range':[-span,span],'title':{'text':'X / mm'}},
                             'yaxis':{**axis,'range':[-span,span],'title':{'text':'Y / mm'}},
                             'zaxis':{**axis,'range':[0,zmax],'title':{'text':'Z / mm'}},
                             'aspectmode':'data','camera':camera,'bgcolor':'white'}})
fig.update_layout(width=1800,height=1120,paper_bgcolor='white',font={'family':'Microsoft YaHei, Arial, sans-serif','size':14,'color':'#253b49'},
                  margin={'l':5,'r':5,'t':150,'b':190},
                  title={'text':f'V6 三维扫描遮挡 · 扫描边界竖向余量 {P["tray_clearance_above_52deg_at_outer_edge_mm"]:.2f} mm<br><sup>较 V5 降低 {P["height_reduction_from_v5_mm"]:.2f} mm；几何总阴影 {percent:.2f}%（V5：{baseline:.2f}%）；托盘 / 天线 0%，三条窄柱影保留</sup>',
                         'x':.5,'y':.975,'xanchor':'center','font':{'size':25}},
                  legend={'orientation':'h','x':.5,'xanchor':'center','y':-.035,'yanchor':'top','font':{'size':13},'groupclick':'togglegroup'})
fig.add_annotation(x=.02,y=-.15,xref='paper',yref='paper',xanchor='left',yanchor='top',showarrow=False,align='left',font={'size':13,'color':'#526b7b'},
                   text='余量定义：托盘外缘底面高于 O 点 52° 圆锥面的竖向距离为 0.90 mm。托盘及天线在名义视场内未产生遮挡，橙色为残余立柱阴影。<br>视场 360° / −7°～52°；半径 160 / 65 mm 仅为图示尺度。O 点投影采用 0.125° 网格；未建模真实光学孔径、折射、线缆与紧固件，百分比不是实测丢点率。')
out=ROOT/'renders/rtk_scan_occlusion_3d_v6_20261028.html'
fig.write_html(str(out),full_html=True,include_plotlyjs=True,div_id='shadow3d',config={'responsive':True,'displaylogo':False},
               post_script='window.shadowPlotReady = true;')
manifest={'html':out.relative_to(ROOT).as_posix(),'post_diameter_mm':P['post_diameter_mm'],'projected_percent':percent,
          'fine_grid_deg':.125,'display_grid_deg':[1,.5],'display_radius_mm':[160,65],
          'display_mesh_decimation':'Radar reference only; optical calculations use full refined CAD meshes.',
          'radar_display_triangles':len(mt),'mount_display_triangles':len(st),
          'data_mask_key':'v6_mask','render_data_percent':render_data_percent,
          'tray_vertical_clearance_mm':P['tray_clearance_above_52deg_at_outer_edge_mm'],
          'source_step_sha256':report['v6_step_sha256']}
(ROOT/'reports/rtk_shadow_3d_v6_20261028.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False),flush=True)
