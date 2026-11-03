"""Independent B audit and old/new diff; no changes to Python reference or oracles."""
import argparse,copy,gzip,hashlib,itertools,json,sys
from pathlib import Path
from replay import ROOT,OLD
sys.path.insert(0,str(ROOT))
from mapgen import GenerationRequest,GeneratorConfig,ModuleLibrary
from mapgen.artifacts import validate_result
from mapgen.contracts import request_fingerprint

def exclusion(region,seals,half):
 if len(region)!=4 or region[2]<=0 or region[3]<=0:return None
 rects=[[s['rect_pixels'][0]-half[0],s['rect_pixels'][1]-half[1],s['rect_pixels'][2]+2*half[0],s['rect_pixels'][3]+2*half[1]] for s in seals]
 samples=[]
 for axis in [0,1]:
  lo=region[axis];hi=lo+region[axis+2];points={lo,hi}
  for rect in rects:
   points.update(v for v in [rect[axis],rect[axis]+rect[axis+2]] if lo<v<hi)
  points=sorted(points);samples.append(points+[(a+b)/2 for a,b in zip(points,points[1:])])
 return all(any(r[0]<x<r[0]+r[2] and r[1]<y<r[1]+r[3] for r in rects) for x,y in itertools.product(*samples))

def inspect_result(r,library):
 if r['status']!='PASS':
  assert r['status'] in ['SEARCH_EXHAUSTED','BUDGET_EXHAUSTED','CANCELLED'],r['status']
  assert r['map'] is None and r['content_store']=={}
  return dict(status=r['status'],usable_map=False,sites_checked=0)
 m=r['map'];cfg=copy.deepcopy(m['inputs']['config']);assert cfg['algorithm']=='stable-v3-reward-space';cfg['algorithm']='stable-v2'
 req=GenerationRequest.from_dict(m['inputs']['request']);config=GeneratorConfig.from_dict(cfg);fp=request_fingerprint(req,config,library)
 projected=copy.deepcopy(r);projected['request_fingerprint']=fp
 pm=projected['map'];pm['inputs']['config']=cfg;pm['map_id']='map-'+fp[:24];pm['generator'].update(implementation='mapgen/interface-v1',algorithm='stable-v2',request_fingerprint=fp)
 validate_result(projected,req,config,library)
 assert m['generator']['implementation']=='mapgen/gdscript-candidate-0.4.0' and m['generator']['request_fingerprint']==r['request_fingerprint'] and m['map_id']=='map-'+r['request_fingerprint'][:24]
 found=[];excluded=[];half=m['inputs']['request']['player']['clearance_half_extents_pixels']
 for instance in m['instances']:
  for site in r['content_store'][instance['content_ref']]['reward_sites']:
   proof=exclusion(site.get('region',[]),instance['seals'],half)
   row=dict(instance=instance['id'],module_id=instance['module_id'],role=instance['role'],reward_id=site['id'],fully_excluded=proof,physical='UNKNOWN')
   found.append(row)
   if proof:excluded.append(row)
 assert not excluded,excluded
 return dict(status='PASS',usable_map=True,sites_checked=len(found),ordinary_sites=sum(x['role']!='target_reward' for x in found),target_sites=sum(x['role']=='target_reward' for x in found),sites=found,source_payload_validation='PASS',physics='NOT_RUN')

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--module-zip',type=Path,required=True);a=p.parse_args();library=ModuleLibrary.from_zip(a.module_zip,expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723');summary=json.loads((a.input/'summary.json').read_text());rows=[]
 for row in summary['records']:
  name=row['case'];r=json.loads(gzip.decompress((a.input/(name+'.json.gz')).read_bytes()))['result'];audit=inspect_result(r,library)
  original='success' if name.startswith('success-batch') else name
  diff={}
  if not name.startswith('cancel-'):
   old=json.loads(gzip.decompress((OLD/original/'actual.json.gz').read_bytes()))['result'];om=old['map'];nm=r['map']
   if om and nm:
    diff={field:om[field]!=nm[field] for field in ['instances','connections','graph','anchors','bounds_blocks']}
    diff['content_store_changed']=old['content_store']!=r['content_store']
   old_excluded=[]
   if om:
    for instance in om['instances']:
     for site in old['content_store'][instance['content_ref']]['reward_sites']:
      if exclusion(site.get('region',[]),instance['seals'],om['inputs']['request']['player']['clearance_half_extents_pixels']):
       old_excluded.append(dict(instance=instance['id'],module_id=instance['module_id'],reward_id=site['id'],region=site['region'],sealed_port_ids=[x['port_id'] for x in instance['seals']]))
   diff['old_fully_excluded_sites']=old_excluded
   diff.update(old_status=old['status'],new_status=r['status'],old_expansions=old['metrics'].get('expansions'),new_expansions=r['metrics'].get('expansions'),proof_rejections=r['metrics'].get('pruning',{}).get('reward_claim_region_excluded_by_seals',0))
  rows.append(dict(case=name,audit=audit,diff=diff,proofs=r['diagnostics'].get('details',{}).get('reward_seal_conflicts',[])))
 report=dict(status='PASS',stage='B',algorithm='stable-v3-reward-space',comparison='0.3.0/A old results retained; new outcomes frozen separately',semantic_validator_projection='only implementation, fingerprint and config/generator algorithm identity projected on a copy; original actual retained',generation_statuses={s:sum(r['audit']['status']==s for r in rows) for s in {r['audit']['status'] for r in rows}},rows=rows,claim='no full strict seal-AABB exclusion detected in any surviving ordinary or target site; NOT physical playability')
 (a.input.parent/'validity.json').write_text(json.dumps(report,indent=2)+'\n');print('Independent source/graph/all-reward validity PASS',len(rows))
if __name__=='__main__':main()
