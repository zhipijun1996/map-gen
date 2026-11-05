"""Preserve all40 base outcomes, add matched map review and honest coverage/limits."""
import collections,gzip,json,statistics,argparse
from pathlib import Path
from map_additions.tools.setup import ROOT
from route_construction.tools.report import source,read,quality,means
BASE=ROOT/'validation/map-additions-20261105'
NAMES={'v5':'v5 / 0.6.0 联合支路','v6returns':'v6 / 0.7.0 多模块折返','v6merge':'v6 / 0.7.0 归并骨架','v7':'v7 / 0.8.0 联合构造'}
def main():
 p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);maps={};summary={};unmapped=[]
 for algo in NAMES:
  folder=BASE/('cohort-'+algo);rows=json.loads((folder/'summary.json').read_text())['rows'];success=[r for r in rows if r['status']!='BASE_FAILED'];gaps=collections.Counter();mounts=collections.Counter();classes=collections.Counter();boards=0;alltimes=[];maxadv=[];maps[algo]={}
  for row in rows:
   seed=row['seed'];r=read(source(algo,seed));m=r['map']
   if r['status']!='PASS':maps[algo][seed]={'status':r['status']};continue
   record=json.loads(gzip.decompress((folder/('seed-'+str(seed)+'.json.gz')).read_bytes()));v=record['result'];gaps.update(g['reason'] for g in v['gaps']);mounts.update(b['mount'] for b in v['signs']);classes.update(s['boundary_class'] for s in v['moving_saws']);boards+=len(v['signs']);alltimes.append(record['creation_usec']+record['profile']['wall_usec']);maxadv.extend(ph['max_usec'] for ph in record['profile']['phases'].values())
   gs={(n['instance_id'],rid) for n in m['graph']['nodes'] if n['kind']=='reward' for rid in n['reward_ids']};items=[]
   for i in m['instances']:
    b=r['content_store'][i['content_ref']];items.append({k:i[k] for k in ['id','module_id','role','origin_blocks','size_blocks','seals']}|dict(platforms=b.get('platforms',[]),routes=[x['author_path_pixels'] for x in i['routes']],rewards=[s.get('position') for s in b.get('reward_sites',[]) if s.get('position')]))
    unmapped.extend(dict(algorithm=algo,seed=seed,instance=i['id'],module_id=i['module_id'],site=s['id'],reason='reward_site has no retained directed Route graph node; no inferred reachability or fake sign') for s in b.get('reward_sites',[]) if (i['id'],s['id']) not in gs)
   maps[algo][seed]=dict(status=r['status'],bounds=m['bounds_blocks'],instances=items,signs=v['signs'],moving_saws=v['moving_saws'],gaps=v['gaps'],stats=v['stats'])
  d=sum(r['stats']['decisions'] for r in success);placed=sum(r['stats']['placed_decisions'] for r in success)
  summary[algo]=dict(base_outcomes=dict(collections.Counter(r['base_status'] for r in rows)),postprocess_outcomes=dict(collections.Counter(r['status'] for r in rows)),decision_views=d,placed_views=placed,view_coverage=placed/d,boards=boards,mounts=dict(mounts),gaps=dict(gaps),saws=sum(r['stats']['moving_saws'] for r in success),boundary_classes=dict(classes),mean_creation_plus_drain_seconds=statistics.mean(alltimes)/1e6,max_advance_msec=max(maxadv)/1000,unmapped_reward_sites=sum(x['algorithm']==algo for x in unmapped))
 common=[s for s in range(930001,930041) if all(read(source(algo,s))['status']=='PASS' for algo in ['v5','v7'])];paired={algo:means([quality(read(source(algo,s))) for s in common]) for algo in ['v5','v7']}
 report=dict(status='PASS',scope='Frozen original40 maps, all base failures retained. Structural metrics only on common39 v5/v7 successful seeds. New signs are declared directed Port-arrival views, not complete physical fork detection. Known graph targets only; unmapped source reward sites listed separately. Core outcomes reused, no new generation.',summary=summary,common_success_seeds=common,paired_quality=paired,unmapped_reward_sites=unmapped,earlier60_comparison='route_construction/comparison/metrics.json');(a.out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 html=(ROOT/'map_additions/tools/view.html').read_text().replace('__DATA__',json.dumps(dict(maps=maps,names=NAMES,summary=summary),ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'));(a.out/'index.html').write_text(html);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
