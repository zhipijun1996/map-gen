"""Execute actual exported Godot preview; compare sidecars and exercise trusted input."""
import argparse,gzip,hashlib,http.server,json,threading,time,atexit
from pathlib import Path
from playwright.sync_api import sync_playwright
from map_additions.tools.setup import ROOT
p=argparse.ArgumentParser(__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
class Handler(http.server.SimpleHTTPRequestHandler):
 def __init__(self,*args,**kw):super().__init__(*args,directory=str((a.project/'build').resolve()),**kw)
 def end_headers(self):self.send_header('Cross-Origin-Opener-Policy','same-origin');self.send_header('Cross-Origin-Embedder-Policy','require-corp');super().end_headers()
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();logs=[];errors=[];records=[]
def persist():
 (a.out/'partial-records.json.gz').write_bytes(gzip.compress(json.dumps(records).encode(),mtime=0));(a.out/'console.json').write_text(json.dumps(logs,indent=2)+'\n');(a.out/'page-errors.json').write_text(json.dumps(errors,indent=2)+'\n')
atexit.register(persist)
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader']);page=browser.new_page(viewport={'width':1300,'height':900});page.on('console',lambda m:logs.append(dict(type=m.type,text=m.text)));page.on('pageerror',lambda e:errors.append(str(e)));page.add_init_script("window.addEventListener('keydown',e=>{if(e.key==='Escape'){window.cancelDomInputTime=performance.now();window.cancelDomEventTrusted=e.isTrusted;}},true)")
 page.goto(f'http://127.0.0.1:{server.server_port}/index.html',timeout=60000);page.wait_for_function('window.additionsStage==="done"',timeout=120000)
 def keep(algo):
  r=page.evaluate('window.additionsReport');native=json.loads(gzip.decompress((ROOT/'validation/map-additions-20261105'/('cohort-'+algo)/'seed-930001.json.gz').read_bytes()))['result'];v=dict(r['result']);v.pop('metrics',None);native.pop('metrics',None);r['native_equal_except_metrics']=v==native;records.append(r);persist();print('kept',algo,r['native_equal_except_metrics'],flush=True);return r
 keep('v7');page.screenshot(path=str(a.out/'initial.png'));print('initial v7 finished',flush=True)
 def choose(index):
  page.mouse.move(1100,800);page.mouse.down();page.wait_for_timeout(200);page.mouse.up();page.keyboard.down(str(index+1));page.wait_for_timeout(200);page.keyboard.up(str(index+1));print('selected',index,page.evaluate('window.lastReviewInput'),flush=True)
 for index,algo in enumerate(['v5','v6returns','v6merge']):
  choose(index);page.wait_for_function('(a)=>window.additionsStage==="done" && window.additionsReport.algorithm===a',arg=algo,timeout=120000);keep(algo)
 choose(3);page.wait_for_function('window.additionsStage==="running"',timeout=10000);t=time.monotonic();page.keyboard.down('Escape');page.wait_for_timeout(200);page.keyboard.up('Escape');page.wait_for_function('window.additionsReport?.result.status==="CANCELLED"',timeout=10000);cancel=page.evaluate('window.additionsReport');cancel['launcher_input_roundtrip_msec']=(time.monotonic()-t)*1000;cancel['dom_input_to_cancel_done_msec']=page.evaluate('window.additionsCancelDoneDomTime-window.cancelDomInputTime');cancel['dom_event_trusted']=page.evaluate('window.cancelDomEventTrusted')
 # Restart via two real option selections; preserve both completed and cancelled results.
 choose(0);page.wait_for_function('window.additionsStage==="running"',timeout=10000);choose(3);page.wait_for_function('window.additionsStage==="done" && window.additionsReport.algorithm==="v7"',timeout=120000)
 r=page.evaluate('window.additionsReport');points=[s for s in r['sign_screen_points'] if 245<s['screen'][1]<820 and 20<s['screen'][0]<1270];assert points,'no visible sign to inspect';page.mouse.move(*points[0]['screen']);page.mouse.down();page.wait_for_timeout(200);page.mouse.up();page.wait_for_function('Boolean(window.signInspection)',timeout=10000);inspection=page.evaluate('window.signInspection');page.screenshot(path=str(a.out/'preview.png'));page.wait_for_timeout(700);page.screenshot(path=str(a.out/'preview-later.png'))
 env=page.evaluate('({userAgent:navigator.userAgent,crossOriginIsolated,hardwareConcurrency:navigator.hardwareConcurrency})');env['browser_version']=browser.version;browser.close()
server.shutdown();report=dict(records=records,cancel=cancel,inspection=inspection,environment=env,errors=errors,scope='Live pure-GDScript postprocess of frozen real inputs in Web, animated data preview and inspect input; no main-game physics, damage or movement certification');(a.out/'report.json.gz').write_bytes(gzip.compress(json.dumps(report).encode(),mtime=0));(a.out/'console.json').write_text(json.dumps(logs,indent=2)+'\n');summary=dict(status='PASS' if not errors and all(r['native_equal_except_metrics'] for r in records) and cancel['result']['status']=='CANCELLED' and not cancel['result']['moving_saws'] and not cancel['result']['signs'] and cancel['dom_event_trusted'] and cancel['dom_input_to_cancel_done_msec']>=0 and inspection else 'FAIL',environment=env,records=[dict(algorithm=r['algorithm'],status=r['result']['status'],wall_usec=r['wall_usec'],profile=r['profile'],native_equal_except_metrics=r['native_equal_except_metrics']) for r in records],cancel=cancel,inspected_sign_id=inspection['id'],errors=errors,export_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (a.project/'build').iterdir() if f.is_file()},scope=report['scope']);(a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary['status'],[(r['algorithm'],r['wall_usec'],r['native_equal_except_metrics']) for r in summary['records']],flush=True)
