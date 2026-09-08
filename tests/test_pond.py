from copy import deepcopy
import math
from pathlib import Path
import unittest

from pond import PondSurface, lily_placements, pad_mesh, validate_pond, validate_water_lily, write_ponds
from scene_config import SceneConfig


def pond_recipe():
    return {'name':'test_pond','enabled':True,
            'placement':{'position':[0.,7.,0.], 'rotation_degrees':[0,0,0]},
            'geometry':{'patches':[{'name':'water','enabled':True,'generator':'plane',
                'dimensions':[1000.,1000.], 'subdivisions':[9,9],
                'local_position':[0,0,0], 'local_rotation_degrees':[0,0,0]}]},
            'topography':{'enabled':True,'generator':'pond_surface','parameters':{
                'depth':20.,'ripples':[{'amplitude':.1,'wavelength':40.,
                    'direction_degrees':20.,'phase_degrees':90.}]}},
            'surface':{'material':{'type':'dielectric','eta':1.333,'roughness':.02,
                'absorption':[.01,.005,.007]},'texture':{'enabled':False}},
            'surface_objects':[]}


def lily_recipe():
    return {'name':'lilies','enabled':True,'generator':'water_lily',
            'construction':{'variants':2,'pads_per_cluster':3,'pad_radius':15.,
                'cluster_radius':18.,'pad_segments':24,'pad_rings':3,
                'pad_notch_degrees':24.,'pad_camber':.2,'vein_count':5,'vein_width':.1,
                'pad_color':[.05,.2,.04],'vein_color':[.1,.3,.06],'roughness':.3,
                'flower_radius':10.,'flower_height':7.,'petal_width':2.,
                'petal_layers':2,'petals_per_layer':6,'petal_segments':4,
                'petal_color':[.7,.1,.2],'petal_tip_color':[.9,.8,.8],
                'center_color':[.9,.5,.02],'stamen_count':8},
            'population':{'method':'scatter','count':12,'seed':82,'scale':[.8,1.2],
                'minimum_spacing':70.,'surface_offset':.5,'flower_probability':.7,
                'region':{'center':[0.,0.],'size':[600.,600.]},'instances':[]}}


class PondTests(unittest.TestCase):
    def test_surface_height_and_closed_rim(self):
        pond=PondSurface(pond_recipe())
        self.assertAlmostEqual(pond.height(0,0),7.1)
        for x,z in [(-500,0),(500,120),(0,-500),(100,500)]:
            self.assertAlmostEqual(pond.height(x,z),7.)
        self.assertTrue(pond.contains(400,0,50))
        self.assertFalse(pond.contains(480,0,50))

    def test_pad_notch_is_open_and_faces_up(self):
        c=lily_recipe()['construction'];points,faces=pad_mesh(c,15.)
        self.assertTrue(all(math.isfinite(v) for p in points for v in p))
        for a,b,d in faces:
            p,q,r=points[a],points[b],points[d]
            ny=(q[2]-p[2])*(r[0]-p[0])-(q[0]-p[0])*(r[2]-p[2])
            self.assertGreater(ny,0)
            center=[(p[i]+q[i]+r[i])/3 for i in (0,2)]
            self.assertFalse(center[0]>0 and abs(math.atan2(center[1],center[0]))<math.radians(12))

    def test_scatter_is_repeatable_spaced_and_surface_anchored(self):
        p=PondSurface(pond_recipe());e=lily_recipe();before=deepcopy(e)
        a=lily_placements(p,e);self.assertEqual(a,lily_placements(p,e));self.assertEqual(e,before)
        self.assertEqual(len(a),12)
        for i,item in enumerate(a):
            x,z=item['position'];self.assertAlmostEqual(item['height'],p.height(x,z)+.5)
            for other in a[:i]:self.assertGreaterEqual(math.dist(item['position'],other['position']),70)
        e['population']['region']['center']=[10000,10000]
        with self.assertRaisesRegex(ValueError,'accepted 0 of 12'):lily_placements(p,e)

    def test_explicit_placement_and_whole_cluster_instancing(self):
        p=pond_recipe();e=lily_recipe();e['population']['method']='explicit'
        e['population']['instances']=[{'position':[10.,20.],'scale':1.,'rotation_degrees':30.,'variant':1,'flower':True}]
        p['surface_objects']=[e];lines=[];write_ponds(lines,[p])
        self.assertEqual(sum(s.startswith('ObjectBegin') for s in lines),4)
        self.assertEqual(sum(s.startswith('ObjectInstance') for s in lines),1)
        inside=False
        for line in lines:
            if line.startswith('ObjectBegin'):inside=True
            if line=='ObjectEnd':inside=False
            if line.startswith('ObjectInstance'):self.assertFalse(inside)
        self.assertTrue(any('MakeNamedMedium "pond_0_water"' in s for s in lines))
        e['population']['instances'][0]['position']=[490,0]
        with self.assertRaisesRegex(ValueError,'beyond pond'):write_ponds([], [p])

    def test_validation_and_integration(self):
        p=pond_recipe();e=lily_recipe();p['surface_objects']=[e]
        cfg=SceneConfig(Path(__file__).parent/'fixtures/canonical_config.json')
        cfg.data['scene_description']['landforms'].append(p)
        self.assertEqual(cfg.validate(),[])
        bad=deepcopy(p);bad['topography']['parameters']['depth']=.01
        self.assertTrue(validate_pond(bad))
        for key,value in [('dimensions',None),('subdivisions',4),('local_position',[float('nan'),0,0])]:
            bad=deepcopy(p);bad['geometry']['patches'][0][key]=value
            self.assertTrue(validate_pond(bad))
        bad=deepcopy(p);bad['surface']['material']=[]
        self.assertTrue(validate_pond(bad))
        for key,value in [('variants',0),('pad_radius',-1),('pad_color',[2,0,0]),('petal_segments',3)]:
            c=deepcopy(e['construction']);c[key]=value
            self.assertTrue(validate_water_lily(c,e['population']),key)
        e['population']['flower_probability']=float('nan')
        self.assertTrue(cfg.validate())


if __name__=='__main__':unittest.main()
