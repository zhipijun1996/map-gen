"""Run the real local Web export in Chromium. Does not deploy/publish anything."""
import argparse
import gzip
import hashlib
import http.server
import json
from pathlib import Path
import sys
import threading
import time

from playwright.sync_api import sync_playwright
from replay import ROOT, compare
sys.path.insert(0,str(ROOT))
from mapgen import GenerationRequest, GeneratorConfig, ModuleLibrary
from mapgen.artifacts import deterministic_result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--module-zip',type=Path,required=True)
    p.add_argument('--chromium',default='/usr/bin/chromium')
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    export=ROOT/'godot_candidate/build/web'
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw): super().__init__(*a,directory=str(export),**kw)
        def log_message(self,*a): pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    logs=[]
    errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=browser.new_page()
        page.on('console',lambda msg:logs.append(dict(type=msg.type,text=msg.text)))
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/index.html',wait_until='load',timeout=60000)
        started=time.monotonic()
        previous=None
        while not page.evaluate('Boolean(window.mapgenReport)'):
            phase=page.evaluate('window.mapgenPhase || "loading"')
            if phase != previous:
                print('Web phase:',phase,flush=True);previous=phase
            if time.monotonic()-started>480:
                (args.out/'timeout-console.json').write_text(json.dumps(logs,indent=2))
                raise TimeoutError('real Web execution exceeded 480 seconds')
            page.wait_for_timeout(1000)
        report=page.evaluate('window.mapgenReport')
        environment=page.evaluate('({userAgent:navigator.userAgent,crossOriginIsolated:window.crossOriginIsolated,hardwareConcurrency:navigator.hardwareConcurrency})')
        page.screenshot(path=str(args.out/'browser.png'))
        browser.close()
    server.shutdown()
    (args.out/'console.json').write_text(json.dumps(logs,indent=2)+'\n')
    (args.out/'report.json.gz').write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))
    library=ModuleLibrary.from_zip(args.module_zip,expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723')
    cfg=GeneratorConfig.from_dict(json.loads((ROOT/'profiles/stable-v2.json').read_text()))
    checks={}
    for name,case in [('default-128','success'),('default-4096','success'),('failure','failure')]:
        fixture=ROOT/'reference_package/fixtures'/case
        req=GenerationRequest.from_dict(json.loads((fixture/'request.json').read_text()))
        expected=json.loads((fixture/'result.json').read_text())
        checks[name]=compare(report['results'][name],expected,req,cfg,library)
    for name in ['request','config','reference-vectors','number-vectors','hypot-vectors']:
        assert report['input_sha256'][name]==hashlib.sha256((ROOT/f'godot_candidate/tests/{name}.json').read_bytes()).hexdigest()
    cancellation=report['results']['cancel']
    checks['cancel']={'status':cancellation['status']=='CANCELLED','no_map':cancellation['map'] is None and cancellation['content_store']=={},'expanded_17':cancellation['metrics']['expansions']==17}
    checks['batch_independence']={'full_result':deterministic_result(report['results']['default-128'])==deterministic_result(report['results']['default-4096'])}
    ok=not errors and not report['foundation_failures'] and all(all(c.values()) for c in checks.values())
    summary=dict(status='PASS' if ok else 'FAIL',runtime='actual Godot Web single-thread export in Chromium',environment=environment,
                 errors=errors,foundation_failures=report['foundation_failures'],checks=checks,timing=report['timing'],cancel_usec=report['cancel_usec'],input_sha256=report['input_sha256'],
                 component_source_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((ROOT/'godot_candidate/addons/mapgen').glob('*.gd'))},
                 export_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(export.iterdir()) if f.is_file()},
                 mobile_device='NOT_RUN',whole_map_playable='NOT_RUN')
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(status=summary['status'],checks=checks,timing=report['timing'],errors=errors)),flush=True)
    return 0 if ok else 1

if __name__=='__main__': raise SystemExit(main())
