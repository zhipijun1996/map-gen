"""Describe module repetition and layout similarity; no generation decisions."""
import collections,gzip,itertools,json,math
from pathlib import Path
def read(p):return json.loads(gzip.decompress(p.read_bytes()))
def stats(result,classes=None):
 if result['status']!='PASS':return {'status':result['status']}
 m=result['map'];ordinary=[i for i in m['instances'] if i['role']=='traversal'];counts=collections.Counter(i['module_id'] for i in ordinary);by={i['id']:i for i in m['instances']}
 pairs=collections.Counter(tuple(sorted([by[c['a']['instance_id']]['module_id'],by[c['b']['instance_id']]['module_id']])) for c in m['connections'] if by[c['a']['instance_id']]['role']=='traversal' and by[c['b']['instance_id']]['role']=='traversal')
 areas=collections.Counter(i['module_id'] for i in m['instances']);bounds=m['bounds_blocks'];w=bounds[2]-bounds[0];h=bounds[3]-bounds[1]
 # Fixed 24x24 normalized occupancy, translation and map size factored out.
 # Module-level masks only: no claim about actual platform/action variety.
 mask=set()
 for y in range(24):
  for x in range(24):
   px=bounds[0]+(x+.5)*w/24;py=bounds[1]+(y+.5)*h/24
   if any(i['origin_blocks'][0]<=px<i['origin_blocks'][0]+i['size_blocks'][0] and i['origin_blocks'][1]<=py<i['origin_blocks'][1]+i['size_blocks'][1] for i in m['instances']):mask.add(y*24+x)
 normalized=tuple(sorted((i['module_id'],i['origin_blocks'][0]-bounds[0],i['origin_blocks'][1]-bounds[1],*i['size_blocks'],i['transform']['mirror_x']) for i in m['instances']))
 class_counts={k:len({classes[i['module_id']][k] for i in ordinary}) for k in ['platform_geometry','port_route_topology']} if classes else {}
 return dict(unique_platform_geometry=class_counts.get('platform_geometry'),unique_port_route_topology=class_counts.get('port_route_topology'),status='PASS',ordinary=len(ordinary),unique=len(counts),repeat_instances=len(ordinary)-len(counts),dominant_share=max(counts.values())/len(ordinary),entropy=-sum((n/len(ordinary))*math.log2(n/len(ordinary)) for n in counts.values()),repeated_neighbor_pairs=sum(n-1 for n in pairs.values()),nodes=len(m['graph']['nodes']),edges=len(m['graph']['edges']),instances=len(m['instances']),aspect=max(w/h,h/w),width=w,height=h,mask=mask,modules=set(counts),pairs=set(pairs),signature=normalized)
def aggregate(rows):
 good=[r for r in rows if r['status']=='PASS'];out={'cases':len(rows),'passed':len(good)}
 for key in ['unique_platform_geometry','unique_port_route_topology','ordinary','unique','repeat_instances','dominant_share','entropy','repeated_neighbor_pairs','nodes','edges','instances','aspect']:
  out['mean_'+key]=sum(r[key] for r in good)/len(good)
 for field,name in [('modules','module_set_jaccard'),('pairs','neighbor_pair_jaccard'),('mask','normalized_occupancy_jaccard')]:
  scores=[len(a[field]&b[field])/len(a[field]|b[field]) for a,b in itertools.combinations(good,2)];out['mean_'+name]=sum(scores)/len(scores)
 out['exact_duplicate_layouts']=len(good)-len({r['signature'] for r in good});return out
