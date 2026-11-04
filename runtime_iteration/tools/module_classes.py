"""Source identity-free classes for diagnostics; not generator inputs or qualification."""
import json
from mapgen.transform import materialize

def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def build(library):
 catalog=library.read('catalog.json');rows={}
 for e in catalog['modules']:
  shapes=[];routes=[]
  for mirror in [False,True]:
   content=materialize(dict(compiled_content=library.read(e['compiled']),source_bounds=e['bounds'],size_blocks=e['sizeBlocks']),mirror,e['blockSize'])
   slabs=sorted((tuple(s),i in content['one_way_platform_indices'],i in content['wall_platform_indices']) for i,s in enumerate(content['platforms']))
   shapes.append(encode([e['sizeBlocks'],slabs]))
   by={}
   for p in e['ports']:
    xy=p['position'];xy=[xy['x'],xy['y']] if isinstance(xy,dict) else xy;x=xy[0]-e['bounds']['x'];y=xy[1]-e['bounds']['y'];face=p['face']
    if mirror:x=e['sizeBlocks'][0]*e['blockSize']-x;face={'LEFT':'RIGHT','RIGHT':'LEFT'}.get(face,face)
    by[p['id']]=[face,p['surface'],p['permission'],x,y]
   edges=sorted(encode([by[r['from']],by[r['to']],sorted(r['validation'].get('availableAbilities',[]))]) for r in e['routes'])
   routes.append(encode([e['sizeBlocks'],sorted(encode(v) for v in by.values()),edges]))
  rows[e['id']]={'platform_geometry':min(shapes),'port_route_topology':min(routes)}
 return rows
