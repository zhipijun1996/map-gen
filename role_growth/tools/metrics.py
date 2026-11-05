"""Actual directed forks; an authored multi-Port template alone is not a fork."""
import collections,gzip,json
from route_construction.tools.report import quality

def read(path):return json.loads(gzip.decompress(path.read_bytes()))['result']
def metrics(r):
 if r['status']!='PASS':return {}
 m=r['map'];nodes={n['id']:n for n in m['graph']['nodes']};g=collections.defaultdict(list)
 for a,b in m['graph']['edges']:g[a].append(b)
 start=next(n for n,v in nodes.items() if v['kind']=='start');seen={start};queue=collections.deque([start])
 while queue:
  for b in g[queue.popleft()]:
   if b not in seen:seen.add(b);queue.append(b)
 pn={(n['instance_id'],n.get('port_id'),n['kind']):nid for nid,n in nodes.items()};forks=set();views=0
 for i in m['instances']:
  exits=collections.defaultdict(set)
  for route in i['routes']:
   if route['from_port']!=route['to_port'] and route['from_port'] in i['connected_port_ids'] and route['to_port'] in i['connected_port_ids'] and pn.get((i['id'],route['from_port'],'port_arrive')) in seen:exits[route['from_port']].add(route['to_port'])
  count=sum(len(e)>=2 for e in exits.values());views+=count
  if count:forks.add(i['id'])
 pairs={tuple(sorted((c['a']['instance_id'],c['b']['instance_id']))) for c in m['connections'] if c['a']['instance_id'] in forks and c['b']['instance_id'] in forks}
 large=[i for i in m['instances'] if i['role']=='traversal' and len(i['ports'])<=2 and i['size_blocks'][0]*i['size_blocks'][1]>=24]
 return quality(r)|dict(fork_instances=len(forks),fork_views=views,adjacent_fork_pairs=len(pairs),fork_pair_fraction=len(pairs)/max(1,len(m['connections'])),large_two_port_instances=len(large),large_two_port_unique=len({i['module_id'] for i in large}),ordinary_instances=sum(i['role']=='traversal' for i in m['instances']))
