"""Owned-rectangle affine transforms for the full 1.1.0 compiled content.

This is a data/diagram materializer, not a Godot scene loader. Evidence and
source references retain their original coordinate frame. Route IDs and
directional from/to references are never reversed by reflection.
"""
import copy
import math

POINTS = {'position', 'origin', 'start', 'finish', 'bell', 'return_access',
          'additional_pair_access', 'muzzle', 'ellipse_center', 'entry_port',
          'exit_port', 'stagingPosition', 'targetPosition'}
RECTS = {'rect', 'gate', 'paired_gate', 'region', 'world_bounds'}
VECTORS = {'travel', 'direction', 'normal', 'offset', 'sequence_offset', 'crossing_offset'}
POINT_ARRAYS = {'loop_points'}
RECT_ARRAYS = {'platforms', 'hazards'}


def transform_geometry(data, width, source_origin=(0, 0), mirror=False):
    ox, oy = source_origin

    def point(p):
        x, y = p[0]-ox, p[1]-oy
        return [width-x if mirror else x, y]

    def rectangle(p):
        x, y = p[0]-ox, p[1]-oy
        return [width-x-p[2] if mirror else x, y, p[2], p[3]]

    def visit(value, key=''):
        if isinstance(value, dict):
            if {'x', 'y', 'w', 'h'} <= value.keys():
                x, y, w, h = rectangle([value[k] for k in ('x','y','w','h')])
                return {**copy.deepcopy(value), 'x':x, 'y':y, 'w':w, 'h':h}
            if 'x' in value and 'y' in value:
                x, y = point([value['x'], value['y']])
                return {**{k:visit(v,k) for k,v in value.items() if k not in ('x','y')}, 'x':x, 'y':y}
            return {k:visit(v,k) for k,v in value.items()}
        if isinstance(value, list):
            if key in POINTS and len(value) == 2 and all(isinstance(v,(int,float)) for v in value): return point(value)
            if key in RECTS and len(value) == 4 and all(isinstance(v,(int,float)) for v in value): return rectangle(value)
            if key in VECTORS and len(value) == 2: return [-value[0] if mirror else value[0], value[1]]
            if key in POINT_ARRAYS: return [point(p) for p in value]
            if key in RECT_ARRAYS: return [rectangle(p) if isinstance(p,list) else visit(p) for p in value]
            if key == 'access':
                return point(value) if len(value)==2 and isinstance(value[0],(int,float)) else [point(p) for p in value]
            return [visit(v) for v in value]
        if key == 'targetX' and isinstance(value,(int,float)):
            x = value-ox; return width-x if mirror else x
        if mirror and key in ('face', 'targetFace', 'return_access_side_policy'):
            return {'left':'right','right':'left','LEFT':'RIGHT','RIGHT':'LEFT'}.get(value,value)
        return copy.deepcopy(value)

    result = visit(data)
    if mirror:
        for thorn in result.get('thorns', []):
            if thorn['face'] in ('top','bottom'):
                platform = result['platforms'][thorn['platform_index']]
                thorn['start_offset'] = platform[2]-thorn['start_offset']-thorn['length']
        for platform in result.get('moving_platforms', []):
            # Ellipse radii remain lengths; handedness tracks the reflected
            # parametric path, including identical initial phase/time.
            if platform.get('trajectory_kind') == 'clockwise_ellipse/v1':
                platform['ellipse_x_sign'] = -platform.get('ellipse_x_sign', 1)
                if platform['ellipse_x_sign'] == 1: del platform['ellipse_x_sign']
    return result


def materialize(template, mirror):
    raw = copy.deepcopy(template['compiled_content'])
    # These source declarations include provenance/qualification coordinates.
    # Export transformed generation interfaces separately, never mutate evidence.
    raw.pop('ports', None); raw.pop('routes', None)
    b = template['source_bounds']; width = template['size_blocks'][0]*128
    content = transform_geometry(raw, width, (b['x'], b['y']), mirror)
    content['coordinate_frame'] = 'owned_rectangle_pixels'
    content['source_affine'] = [-1 if mirror else 1, 0, 0, 1,
        width+b['x'] if mirror else -b['x'], -b['y']]
    return content


def ellipse_sample(platform, fraction):
    # Used to verify the materialized mirrored trajectory, not simulate physics.
    cx, cy = platform['ellipse_center']; rx, ry = platform['ellipse_radii']
    angle = 2*math.pi*fraction
    return [cx-platform.get('ellipse_x_sign',1)*rx*math.cos(angle), cy-ry*math.sin(angle)]
