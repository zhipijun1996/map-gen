"""Pure rectangle/Port operations. No global library or player state."""
import copy
from collections import defaultdict
OPPOSITE={"LEFT":"RIGHT","RIGHT":"LEFT","TOP":"BOTTOM","BOTTOM":"TOP"}

def placed_ports(t,x,y,mirror):
    result={}
    for p0 in t['ports']:
        p=copy.deepcopy(p0)
        if mirror:
            p['local2'][0]=2*t['size_blocks'][0]-p['local2'][0]
            p['face']={'LEFT':'RIGHT','RIGHT':'LEFT'}.get(p['face'],p['face'])
        p['world2']=[2*x+p['local2'][0],2*y+p['local2'][1]]
        result[p['id']]=p
    return result

def overlap(a,b):
    x,y=a['origin'];w,h=a['size_blocks'];xx,yy=b['origin'];ww,hh=b['size_blocks']
    return x<xx+ww and xx<x+w and y<yy+hh and yy<y+h

def permitted(p, direction):
    return p['permission'] in (('OUTPUT','INOUT') if direction=='out' else ('INPUT','INOUT'))

def matching(a,b):
    return a['world2']==b['world2'] and OPPOSITE[a['face']]==b['face'] and a['surface']==b['surface'] and (
        permitted(a,'out') and permitted(b,'in') or permitted(b,'out') and permitted(a,'in'))

def bounds(items):
    return [min(i['origin'][0] for i in items),min(i['origin'][1] for i in items),
            max(i['origin'][0]+i['size_blocks'][0] for i in items),max(i['origin'][1]+i['size_blocks'][1] for i in items)]

def connection_groups(items):
    groups=defaultdict(list)
    for i in items:
        for pid,p in i['ports'].items():groups[tuple(p['world2'])].append((i,pid,p))
    return [group for group in groups.values() if len(group)==2 and matching(group[0][2],group[1][2])]


def segment_hits_rect(a, b, rect):
    """Closed segment/AABB intersection, including tangency and zero length."""
    lo, hi = 0.0, 1.0
    for k in (0, 1):
        delta = b[k] - a[k]
        minimum, maximum = rect[k], rect[k] + rect[k+2]
        if delta == 0:
            if not minimum <= a[k] <= maximum:
                return False
        else:
            u, v = sorted(((minimum-a[k])/delta, (maximum-a[k])/delta))
            lo, hi = max(lo, u), min(hi, v)
            if lo > hi:
                return False
    return True
