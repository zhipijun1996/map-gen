"""Review frozen evidence without relabeling unsuccessful generation as PASS."""
import collections,gzip,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'validation/role-growth-20261105'
def read(p):return json.loads(p.read_text())
def main():
 checks={};selection=read(BASE/'selection.json');lock=selection['source_lock']
 profile=read(ROOT/'role_growth/profiles/default.json')
 checks['selected_config_unchanged']=profile==selection['profile']
 original=read(ROOT/'route_construction/profiles/joint-merge.json')
 projected={k:v for k,v in profile.items() if k!='growth_roles'};projected['algorithm']=original['algorithm']
 checks['original_goals_budgets_and_existing_options_unchanged']=projected==original
 outcomes={}
 for cohort in ['primary40','fresh10','fresh-baseline','contracts']:
  folder=BASE/cohort;summary=read(folder/'summary.json')
  checks[cohort+':frozen_runtime_identity']=read(folder/'source-lock.json')==lock
  checks[cohort+':locked_toolchain']=summary['engine_sha256']=='eeaec2b65dc3234168be1e1cbcc89731514bbb78dfb2c1b502920c50830a0638'
  for row in summary['rows']:
   name=row['case'];result=json.loads(gzip.decompress((folder/(name+'.json.gz')).read_bytes()))['result']
   if result['status']=='PASS':checks[cohort+':'+name+':audits']=all(row['checks'].values())
   else:
    checks[cohort+':'+name+':failure_empty']=result['map'] is None and result['content_store']=={}
    checks[cohort+':'+name+':non_expectation_checks']=all(v for k,v in row['checks'].items() if k!='expected_status')
  outcomes[cohort]=dict(collections.Counter(row['status'] for row in summary['rows']))
 for name in ['baseline-equivalence','jobs','isolation','web-audit','protected-packages','viewer']:
  checks[name]=read(BASE/(name+'.json'))['status']=='PASS'
 checks['contracts']=read(BASE/'contracts/summary.json')['status']=='PASS'
 checks['legacy_prototype']='PASS:' in (BASE/'prototype.log').read_text()
 checks['legacy_20_replay']='PASS: all 20 fixed seeds reproduce' in (BASE/'history.log').read_text()
 for path,expected in read(BASE/'protected-packages.json')['packages'].items():
  checks['preserved:'+path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected['sha256']
 changes=subprocess.check_output(['git','diff','776b3cd4046896cfe2ea19ef6e6f8b4b8fca4372','--name-only'],cwd=ROOT,text=True).splitlines()
 checks['only_new_workline_and_root_entry']=all(p=='README.md' or p.startswith(('role_growth/','validation/role-growth-20261105/','runtime_packages/experiments/0.9.0-experiment/')) for p in changes)
 result=dict(status='PASS' if all(checks.values()) else 'FAIL',scope='Evidence integrity and audits, NOT all-seed generation success or production readiness.',outcomes=outcomes,checks=checks,decision='Do not replace v7: new10 is 8/10 versus baseline 10/10; retain failures and current frozen selection.',not_verified=['whole-map physics','main-game integration/performance','per-route persistent task planner','Web cancellation latency in this experiment'])
 (BASE/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(result['status'],len(checks),'checks',outcomes)
 assert result['status']=='PASS',[k for k,v in checks.items() if not v]
if __name__=='__main__':main()
