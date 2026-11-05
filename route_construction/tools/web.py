import argparse,gzip,hashlib,http.server,json,threading,time
from pathlib import Path
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cancel',choices=['preload','transit_catalog','motif_catalog','joint_merge','demand_core_routes','structure_domains','growth','reward_branches']);p.add_argument('--profile',choices=['default','varied'],default='default');p.add_argument('--failure',action='store_true');p.add_argument('--seeds',default='930001,930007');p.add_argument('--preloads',type=int,default=1);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
for name in ('index.html','index.pck','index.wasm'):
 assert (a.project/'build'/name).is_file(), 'missing Web export: '+name
class Handler(http.server.SimpleHTTPRequestHandler):
 def __init__(self,*args,**kw):super().__init__(*args,directory=str((a.project/'build').resolve()),**kw)
 def end_headers(self):
  self.send_header('Cross-Origin-Opener-Policy','same-origin');self.send_header('Cross-Origin-Embedder-Policy','require-corp');super().end_headers()
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();logs=[];errors=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 page=browser.new_page();page.add_init_script('window.benchArgs='+json.dumps({'seeds':[int(s) for s in a.seeds.split(',') if s], 'preloads':a.preloads,'failure':a.failure,'profile':a.profile})+';');page.on('console',lambda m:logs.append({'type':m.type,'text':m.text}));page.on('pageerror',lambda e:errors.append(str(e)))
 t=time.monotonic();page.goto(f'http://127.0.0.1:{server.server_port}/index.html',wait_until='load',timeout=60000)
 if a.cancel:
  page.wait_for_function('(p)=>p==="preload" ? window.benchStage==="preload" && ["catalog_json","derived_json"].includes(window.benchPhase) : window.benchStage==="generate" && window.benchPhase===p',arg=a.cancel,timeout=120000)
  page.keyboard.press('Escape')
 last=None
 while not page.evaluate('Boolean(window.benchReport)'):
  phase=page.evaluate('[window.benchStage,window.benchPhase]')
  if phase!=last:print(phase,flush=True);last=phase
  if time.monotonic()-t>280:
   (a.out/'timeout.json').write_text(json.dumps({'errors':errors,'logs':logs,'phase':phase},indent=2));raise TimeoutError('standalone 280 seconds')
  page.wait_for_timeout(1000)
 report=page.evaluate('window.benchReport');launcher_elapsed=time.monotonic()-t;environment=page.evaluate('({userAgent:navigator.userAgent,crossOriginIsolated,hardwareConcurrency:navigator.hardwareConcurrency})');environment['browser_version']=browser.version;browser.close()
server.shutdown();(a.out/'report.json.gz').write_bytes(gzip.compress(json.dumps(report).encode(),mtime=0));(a.out/'console.json').write_text(json.dumps(logs,indent=2));summary={k:v for k,v in report.items() if k!='records'};summary.update(environment=environment,launcher_elapsed_seconds=launcher_elapsed,errors=errors,records=[{k:v for k,v in r.items() if k!='result'} for r in report['records']],export_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (a.project/'build').iterdir() if f.is_file()});(a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('WEB finished',[(r['stage'],r.get('seed'),r['wall_usec'],r['advance_cpu_usec']) for r in report['records']],flush=True)
