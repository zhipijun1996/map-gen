import argparse,copy,gzip,hashlib,http.server,json,threading,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from replay import ROOT,OLD,normalized

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 export=ROOT/'godot_runtime/build/web'
 class Handler(http.server.SimpleHTTPRequestHandler):
  def __init__(self,*args,**kw):super().__init__(*args,directory=str(export),**kw)
  def log_message(self,*args):pass
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();logs=[]
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage'])
  page=browser.new_page();page.on('console',lambda m:logs.append(m.text));page.on('pageerror',lambda e:logs.append('PAGE_ERROR:'+str(e)))
  page.goto(f'http://127.0.0.1:{server.server_port}/index.html',timeout=60000)
  for case,phase in [('preload-cancel','catalog_json'),('generation-cancel','growth')]:
   page.wait_for_function('(x)=>window.mapgenCase===x[0]&&window.mapgenPhase===x[1]',arg=[case,phase],timeout=180000)
   page.keyboard.press('Escape');print('trusted Escape sent:',case,phase,flush=True)
  page.wait_for_function('Boolean(window.mapgenReport)',timeout=300000)
  report=page.evaluate('window.mapgenReport');browser.close()
 server.shutdown();(a.out/'console.json').write_text(json.dumps(logs,indent=2));(a.out/'report.json.gz').write_bytes(gzip.compress(json.dumps(report).encode(),mtime=0))
 cases=report['cases'];checks={}
 for name in ['preload-cancel','generation-cancel']:
  r=cases[name];checks[name]=r['result']['status']=='CANCELLED' and r['cancel']['trusted'] and r['cancel']['input_to_done_ms']>=r['cancel']['queue_ms']>=0
 checks['preload-reuse']=cases['preload']['result']['status']=='PASS' and cases['preload']['result']['checked_files']==657
 checks['batches']=normalized(cases['default-1']['result'])==normalized(cases['default-17']['result'])
 for name,ref in [('default-1','success'),('failure','failure')]:
  old=json.loads(gzip.decompress((OLD/ref/'actual.json.gz').read_bytes()))['result']
  if a.stage=='A':checks[name]=normalized(cases[name]['result'])==normalized(old)
  else:checks[name]=cases[name]['result']['status']==old['status']
 for name in ['failure','generation-cancel']:
  r=cases[name]['result'];checks[name+'-no-map']=r['map'] is None and r['content_store']=={}
 summary=dict(status='PASS' if all(checks.values()) else 'FAIL',stage=a.stage,checks=checks,cases={n:{k:v for k,v in r.items() if k!='result'} for n,r in cases.items()},actual_web=True,engine=report['engine'],frame_target_usec=report['frame_target_usec'],module_sha256=report['module_sha256'],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'godot_runtime/addons/mapgen').glob('*.gd')},export_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in export.iterdir() if p.is_file()},whole_map_physics='NOT_RUN')
 (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary['status'],checks,flush=True)
 return 0 if summary['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
