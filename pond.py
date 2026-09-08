"""Still pond surfaces and instanced water lilies, with explicit JSON controls."""

import math
import random


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _object(value):
    return value if isinstance(value, dict) else {}


def validate_pond(landform):
    errors = []
    patches = _object(landform.get('geometry')).get('patches', [])
    if not isinstance(patches, list):
        patches = []
    active = [p for p in patches if isinstance(p, dict) and p.get('enabled')]
    if len(active) != 1:
        errors.append('pond requires exactly one enabled plane patch')
    else:
        p = active[0]
        dims, res = p.get('dimensions', []), p.get('subdivisions', [])
        if not isinstance(dims, list) or len(dims) != 2 or not all(_finite(v) and v > 0 for v in dims):
            errors.append('pond patch dimensions must be positive')
        if not isinstance(res, list) or len(res) != 2 or not all(type(v) is int and 2 <= v <= 1025 for v in res):
            errors.append('pond subdivisions must be integers in [2, 1025]')
        if p.get('generator') != 'plane':
            errors.append('pond patch generator must be plane')
        if p.get('local_rotation_degrees') != [0, 0, 0]:
            errors.append('pond patch rotation must be zero')
        pos = p.get('local_position')
        if not isinstance(pos, list) or len(pos) != 3 or not all(_finite(v) for v in pos):
            errors.append('pond patch local_position must be three finite numbers')
    placement = _object(landform.get('placement'))
    pos = placement.get('position')
    if not isinstance(pos, list) or len(pos) != 3 or not all(_finite(v) for v in pos):
        errors.append('pond position must be three finite numbers')
    if placement.get('rotation_degrees') != [0, 0, 0]:
        errors.append('pond rotation must be zero')
    params = _object(landform.get('topography')).get('parameters', {})
    if not isinstance(params, dict):
        return errors + ['pond parameters must be an object']
    depth = params.get('depth')
    if not _finite(depth) or depth <= 0:
        errors.append('pond depth must be positive')
    waves = params.get('ripples')
    if not isinstance(waves, list):
        errors.append('pond ripples must be a list')
    else:
        amplitude = 0
        for wave in waves:
            if not isinstance(wave, dict) or any(not _finite(wave.get(k)) for k in
                    ('amplitude', 'wavelength', 'direction_degrees', 'phase_degrees')):
                errors.append('each ripple requires four finite parameters')
                continue
            if wave['amplitude'] < 0 or wave['wavelength'] <= 0:
                errors.append('ripple amplitude must be nonnegative and wavelength positive')
            amplitude += abs(wave['amplitude'])
        if _finite(depth) and depth <= amplitude:
            errors.append('pond depth must exceed total ripple amplitude')
    surface = _object(landform.get('surface'))
    mat = _object(surface.get('material'))
    if mat.get('type') != 'dielectric':
        errors.append('pond material must be dielectric')
    for key, low, high in [('eta', 1.0, 3.0), ('roughness', 0.0, 1.0)]:
        if not _finite(mat.get(key)) or not low <= mat[key] <= high:
            errors.append(f'pond material {key} must be in [{low}, {high}]')
    absorption = mat.get('absorption', [])
    if (not isinstance(absorption, list) or len(absorption) != 3
            or not all(_finite(v) and v >= 0 for v in absorption)):
        errors.append('pond absorption must be three nonnegative coefficients')
    if _object(surface.get('texture')).get('enabled'):
        errors.append('pond uses geometric ripples; surface texture must be disabled')
    entries = landform.get('surface_objects', [])
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict) and entry.get('enabled') and entry.get('generator') != 'water_lily':
                errors.append('pond currently supports water_lily surface objects only')
    return errors


def validate_water_lily(construction, population):
    errors = []
    for key, low, high in [('variants', 1, 16), ('pads_per_cluster', 1, 8),
                           ('pad_segments', 16, 256), ('pad_rings', 2, 16),
                           ('vein_count', 3, 48), ('petal_layers', 1, 6),
                           ('petals_per_layer', 5, 32), ('petal_segments', 4, 32),
                           ('stamen_count', 8, 128)]:
        v = construction.get(key)
        if type(v) is not int or not low <= v <= high:
            errors.append(f'construction.{key} must be an integer in [{low}, {high}]')
    for key in ('pad_radius', 'cluster_radius', 'flower_radius', 'flower_height',
                'petal_width', 'vein_width'):
        if not _finite(construction.get(key)) or construction[key] <= 0:
            errors.append(f'construction.{key} must be positive')
    for key, low, high in [('pad_notch_degrees', 5, 90), ('pad_camber', 0, 5),
                           ('roughness', 0, 1)]:
        v = construction.get(key)
        if not _finite(v) or not low <= v <= high:
            errors.append(f'construction.{key} must be in [{low}, {high}]')
    for key in ('pad_color', 'vein_color', 'petal_color', 'petal_tip_color', 'center_color'):
        v = construction.get(key)
        if not isinstance(v, list) or len(v) != 3 or not all(_finite(x) and 0 <= x <= 1 for x in v):
            errors.append(f'construction.{key} must be three numbers in [0, 1]')
    if population.get('method') not in ('scatter', 'explicit'):
        errors.append('population.method must be scatter or explicit')
    if type(population.get('seed')) is not int:
        errors.append('population.seed must be an integer')
    scale = population.get('scale')
    if (not isinstance(scale, list) or len(scale) != 2
            or not all(_finite(v) and v > 0 for v in scale) or scale[0] > scale[1]):
        errors.append('population.scale must be an ascending positive pair')
    for key in ('minimum_spacing', 'surface_offset'):
        if not _finite(population.get(key)) or population[key] < 0:
            errors.append(f'population.{key} must be nonnegative')
    if not _finite(population.get('flower_probability')) or not 0 <= population['flower_probability'] <= 1:
        errors.append('population.flower_probability must be in [0, 1]')
    if population.get('method') == 'scatter':
        if type(population.get('count')) is not int or not 0 <= population['count'] <= 10000:
            errors.append('population.count must be an integer in [0, 10000]')
        region = population.get('region', {})
        for key in ('center', 'size'):
            v = region.get(key) if isinstance(region, dict) else None
            if (not isinstance(v, list) or len(v) != 2 or not all(_finite(x) for x in v)
                    or (key == 'size' and min(v) <= 0)):
                errors.append(f'population.region.{key} must be a finite pair (size > 0)')
    else:
        instances = population.get('instances')
        if not isinstance(instances, list):
            errors.append('population.instances must be a list')
        else:
            for item in instances:
                if not isinstance(item, dict):
                    errors.append('each instance must be an object')
                    continue
                pos = item.get('position')
                if not isinstance(pos, list) or len(pos) != 2 or not all(_finite(x) for x in pos):
                    errors.append('instance position must be world XZ')
                if not _finite(item.get('scale')) or item['scale'] <= 0:
                    errors.append('instance scale must be positive')
                if not _finite(item.get('rotation_degrees')):
                    errors.append('instance rotation_degrees must be finite')
                if type(item.get('flower')) is not bool:
                    errors.append('instance flower must be boolean')
                if (type(item.get('variant')) is not int or type(construction.get('variants')) is not int
                        or not 0 <= item['variant'] < construction['variants']):
                    errors.append('instance variant is out of range')
    return errors


class PondSurface:
    def __init__(self, landform):
        errors = validate_pond(landform)
        if errors:
            raise ValueError('; '.join(errors))
        self.patch = next(p for p in landform['geometry']['patches'] if p['enabled'])
        self.center = [a + b for a, b in zip(landform['placement']['position'], self.patch['local_position'])]
        self.width, self.depth = self.patch['dimensions']
        self.parameters = landform['topography']['parameters']
        self.x_min, self.x_max = self.center[0] - self.width / 2, self.center[0] + self.width / 2
        self.z_min, self.z_max = self.center[2] - self.depth / 2, self.center[2] + self.depth / 2

    def height(self, x, z):
        # Ripples vanish at the rectangular boundary, closing the water volume.
        dx, dz = x - self.center[0], z - self.center[2]
        envelope = max(0, math.cos(math.pi * dx / self.width)) ** 2 * max(0, math.cos(math.pi * dz / self.depth)) ** 2
        h = 0.0
        for wave in self.parameters['ripples']:
            a = math.radians(wave['direction_degrees'])
            phase = 2 * math.pi * (dx * math.cos(a) + dz * math.sin(a)) / wave['wavelength']
            h += wave['amplitude'] * math.sin(phase + math.radians(wave['phase_degrees']))
        return self.center[1] + envelope * h

    def contains(self, x, z, margin=0):
        return self.x_min + margin <= x <= self.x_max - margin and self.z_min + margin <= z <= self.z_max - margin


def _mesh(lines, points, faces, smooth=True):
    lines.append('Shape "trianglemesh" "point3 P" [ ' + ' '.join(f'{v:.6f}' for p in points for v in p) + ' ]')
    lines.append('    "integer indices" [ ' + ' '.join(str(i) for f in faces for i in f) + ' ]')
    if smooth:
        normals = [[0.0, 0.0, 0.0] for _ in points]
        for a, b, c in faces:
            u = [points[b][i] - points[a][i] for i in range(3)]
            v = [points[c][i] - points[a][i] for i in range(3)]
            n = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
            for j in (a, b, c):
                for k in range(3): normals[j][k] += n[k]
        unit = []
        for n in normals:
            length = math.sqrt(sum(v*v for v in n))
            unit.extend([v / length for v in n] if length > 1e-15 else [0, 1, 0])
        lines.append('    "normal N" [ ' + ' '.join(f'{v:.7f}' for v in unit) + ' ]')


def _material(lines, color, roughness):
    lines.append('Material "coateddiffuse" "rgb reflectance" [ ' + ' '.join(map(str, color)) + f' ] "float roughness" [ {roughness} ] "float eta" [ 1.4 ]')


def pad_mesh(c, radius, phase=0):
    segments, rings = c['pad_segments'], c['pad_rings']
    notch = math.radians(c['pad_notch_degrees']) / 2
    points, faces = [(0, 0, 0)], []
    for ring in range(1, rings + 1):
        t = ring / rings
        for i in range(segments + 1):
            a = notch + (2 * math.pi - 2 * notch) * i / segments
            r = radius * t * (1 + .025 * math.sin(7*a+phase) * t**3)
            y = c['pad_camber'] * (t*t + .2*math.sin(5*a+phase)*t**3)
            points.append((r*math.cos(a), y, r*math.sin(a)))
    for i in range(segments): faces.append((0, i+2, i+1))
    for ring in range(rings - 1):
        for i in range(segments):
            a = 1 + ring*(segments+1)+i; b = a+segments+1
            faces.extend([(a, a+1, b+1), (a, b+1, b)])
    return points, faces


def _pad(lines, c, radius, phase):
    _material(lines, [v * (0.88 + .12*math.cos(phase)) for v in c['pad_color']], c['roughness'])
    _mesh(lines, *pad_mesh(c, radius, phase))
    _material(lines, c['vein_color'], .65)
    notch = math.radians(c['pad_notch_degrees']) / 2
    for i in range(c['vein_count']):
        a = notch + .08 + (2*math.pi-2*notch-.16)*i/(c['vein_count']-1)
        pts, faces = [], []
        for j in range(9):
            t = .04 + .9*j/8
            r = radius*t
            h = c['pad_camber']*(t*t + .2*math.sin(5*a+phase)*t**3) + .035
            width = c['vein_width']*(1-t)
            for side in (-1,1):
                pts.append((r*math.cos(a)-side*width*math.sin(a),h,r*math.sin(a)+side*width*math.cos(a)))
        for j in range(8):
            k=2*j;faces.extend([(k,k+1,k+3),(k,k+3,k+2)])
        _mesh(lines,pts,faces)


def _flower(lines, c, variant):
    # Narrow pointed petals open outward in overlapping whorls, then rise
    # more steeply toward the center. Each petal is a curved ribbon surface.
    phase = variant * 2.399963
    for layer in range(c['petal_layers']):
        frac = layer/max(1,c['petal_layers']-1)
        radius = c['flower_radius']*(1-.5*frac)
        height = c['flower_height']*(.45+.55*frac)
        count = c['petals_per_layer']
        for i in range(count):
            angle = 2*math.pi*(i+.5*layer)/count + phase
            pts, faces = [], []
            for j in range(c['petal_segments']+1):
                t = j/c['petal_segments']
                r = c['flower_radius']*.10 + radius*t
                width = c['petal_width']*(1-.35*frac)*max(.008,math.sin(math.pi*t)**.85)
                y = 2 + height*(t**1.5) + .8*layer
                for k in range(5):
                    s=(k-2)/2
                    pts.append((r*math.cos(angle)-s*width*math.sin(angle),
                                y+width*.15*s*s, r*math.sin(angle)+s*width*math.cos(angle)))
            # Separate petal bands give a pink-to-ivory gradient along the blade.
            for j in range(c['petal_segments']):
                t=(j+.5)/c['petal_segments']
                white = .8 if variant % 3 == 0 else 0.0
                mix = min(1,white+(1-white)*t*.82)
                color=[a*(1-mix)+b*mix for a,b in zip(c['petal_color'],c['petal_tip_color'])]
                _material(lines,color,.4)
                faces=[]
                for k in range(4):
                    a=j*5+k;b=a+5
                    faces.extend([(a,a+1,b+1),(a,b+1,b)])
                _mesh(lines,pts,faces)
    _material(lines,c['center_color'],.55)
    lines.extend(['AttributeBegin', 'Translate 0 3.2 0',
                  f'Scale {c["flower_radius"]*.19} 1.8 {c["flower_radius"]*.19}',
                  'Shape "sphere" "float radius" [ 1 ]','AttributeEnd'])
    for i in range(c['stamen_count']):
        a=i*2.399963; r=c['flower_radius']*.22*math.sqrt((i+.5)/c['stamen_count'])
        lines.extend(['AttributeBegin', f'Translate {r*math.cos(a)} {4.3+1.2*math.cos(i)} {r*math.sin(a)}',
                      'Scale 0.45 2.2 0.45','Shape "sphere" "float radius" [ 1 ]','AttributeEnd'])


def lily_placements(surface, entry):
    c,p=entry['construction'],entry['population']
    errors=validate_water_lily(c,p)
    if errors: raise ValueError('; '.join(errors))
    rng=random.Random(p['seed']); placements=[]
    if p['method']=='explicit':
        items=p['instances']
    else:
        items=[];cx,cz=p['region']['center'];w,d=p['region']['size']
        for _ in range(max(100,p['count']*1000)):
            if len(items)==p['count']: break
            x,z=rng.uniform(cx-w/2,cx+w/2),rng.uniform(cz-d/2,cz+d/2)
            scale=rng.uniform(*p['scale'])
            margin=(c['cluster_radius']+c['pad_radius']*1.15)*scale
            if not surface.contains(x,z,margin):continue
            if any(math.hypot(x-it['position'][0],z-it['position'][1])<p['minimum_spacing'] for it in items):continue
            items.append(dict(position=[x,z],scale=scale,rotation_degrees=rng.uniform(0,360),
                              variant=rng.randrange(c['variants']),flower=rng.random()<p['flower_probability']))
        if len(items)!=p['count']:
            raise ValueError(f"water lily scatter accepted {len(items)} of {p['count']} requested clusters")
    for item in items:
        x,z=item['position'];margin=(c['cluster_radius']+c['pad_radius']*1.15)*item['scale']
        if not surface.contains(x,z,margin):raise ValueError('water lily cluster extends beyond pond')
        placements.append({**item,'height':surface.height(x,z)+p['surface_offset']})
    return placements


def write_water_lilies(lines,surface,entry,prefix):
    if not entry.get('enabled'): return
    placements=lily_placements(surface,entry)
    c=entry['construction']
    for variant in range(c['variants']):
        for flower in (False,True):
            lines.append(f'ObjectBegin "{prefix}_{variant}_{int(flower)}"')
            for pad in range(c['pads_per_cluster']):
                a=2*math.pi*pad/c['pads_per_cluster']+variant*.6
                radius=c['pad_radius']*(.86+.14*math.sin(pad*4+variant))
                lines.extend(['AttributeBegin',f'Translate {c["cluster_radius"]*math.cos(a)} {pad*.09} {c["cluster_radius"]*math.sin(a)}',
                              f'Rotate {math.degrees(-a)+90} 0 1 0'])
                _pad(lines,c,radius,variant+pad)
                lines.append('AttributeEnd')
            if flower: _flower(lines,c,variant)
            lines.append('ObjectEnd')
    lines.append(f'# Water lilies {prefix}: {len(placements)} clusters')
    for item in placements:
        x,z=item['position'];s=item['scale']
        lines.extend(['AttributeBegin',f'Translate {x} {item["height"]} {z}',
                      f'Rotate {item["rotation_degrees"]} 0 1 0',f'Scale {s} {s} {s}',
                      f'ObjectInstance "{prefix}_{item["variant"]}_{int(item["flower"])}"','AttributeEnd'])


def write_ponds(lines,landforms):
    for index,landform in enumerate(landforms):
        if not landform.get('enabled') or not landform.get('topography',{}).get('enabled') or landform['topography'].get('generator')!='pond_surface':continue
        surface=PondSurface(landform);prefix=f'pond_{index}';mat=landform['surface']['material']
        lines.extend([f'MakeNamedMedium "{prefix}_water" "string type" [ "homogeneous" ]',
                      '    "rgb sigma_a" [ '+' '.join(map(str,mat['absorption']))+' ] "rgb sigma_s" [ 0 0 0 ]',
                      'AttributeBegin',f'MediumInterface "{prefix}_water" ""',
                      f'Material "dielectric" "float eta" [ {mat["eta"]} ] "float roughness" [ {mat["roughness"]} ]'])
        nx,nz=surface.patch['subdivisions'];points=[];faces=[]
        for j in range(nz):
            z=surface.z_min+surface.depth*j/(nz-1)
            for i in range(nx):
                x=surface.x_min+surface.width*i/(nx-1)
                points.append((x,surface.height(x,z),z))
        for j in range(nz-1):
            for i in range(nx-1):
                a=j*nx+i;faces.extend([(a,a+nx,a+nx+1),(a,a+nx+1,a+1)])
        _mesh(lines,points,faces)
        # Close the absorbing water volume with outward-facing side/bottom
        # boundaries. Top rim heights match the zero-envelope ripple boundary.
        bottom=surface.center[1]-surface.parameters['depth']
        x0,x1,z0,z1=surface.x_min,surface.x_max,surface.z_min,surface.z_max;y=surface.center[1]
        corners=[(x0,y,z0),(x0,y,z1),(x1,y,z1),(x1,y,z0),
                 (x0,bottom,z0),(x0,bottom,z1),(x1,bottom,z1),(x1,bottom,z0)]
        sides=[]
        for a in range(4):
            b=(a+1)%4;sides.extend([(a,b+4,b),(a,a+4,b+4)])
        sides.extend([(4,6,5),(4,7,6)])
        lines.append('Material "interface"');_mesh(lines,corners,sides,False)
        lines.append('AttributeEnd')
        for j,entry in enumerate(landform.get('surface_objects',[])):
            if entry.get('generator')=='water_lily':write_water_lilies(lines,surface,entry,f'{prefix}_lily_{j}')
