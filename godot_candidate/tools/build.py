"""Build a deterministic independent Godot candidate ZIP from committed files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]
NAME='mapgen-godot-candidate-0.3.0'
MODULE_SHA='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723'

def sha(data): return hashlib.sha256(data).hexdigest()
def encoded(value): return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-commit',required=True)
    p.add_argument('--module-zip',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--godot',default='godot')
    args=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse',args.source_commit],cwd=ROOT,text=True).strip()
    files={};sources={}
    def add(target,path):
        rel=path.relative_to(ROOT).as_posix()
        raw=path.read_bytes()
        if raw!=subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT):raise ValueError('uncommitted package input:'+rel)
        files[target]=raw;sources[target]=dict(repository_path=rel,sha256=sha(raw))
    project=ROOT/'godot_candidate'
    for path in sorted((project/'addons/mapgen').glob('*.gd')):add('addons/mapgen/'+path.name,path)
    for path in sorted((project/'tests').glob('*')):
        if path.suffix in ('.gd','.json','.tscn'):add('tests/'+path.name,path)
    for path in sorted((project/'docs').rglob('*')):
        if path.is_file():add('docs/'+path.relative_to(project/'docs').as_posix(),path)
    for name in ['project.godot','export_presets.cfg','README.md']:add(name,project/name)
    add('evidence/toolchain.json',ROOT/'validation/godot-candidate-0.3.0/toolchain.json')
    for path in sorted((ROOT/'schemas').glob('*.json')):add('schemas/'+path.name,path)
    add('profiles/stable-v2.json',ROOT/'profiles/stable-v2.json')
    for case in ['success','failure']:
        for name in ['result.json','request.json','config.json','module-lock.json','provenance.json']:
            add(f'tests/samples/{case}/{name}',ROOT/f'reference_package/fixtures/{case}/{name}')
    for directory in ['replay-precision','replay-final','jobs-precision','jobs-final','web-final','protection','foundation','foundation-final','precision','replay','web']:
        folder=ROOT/'validation/godot-candidate-0.3.0'/directory
        # Reports are bounded evidence; full per-seed data stays in repository.
        for name in ['summary.json','report.json','foundation.log','numbers.log','hypot.log','integer_hypot_probe.log','prototype.log','progress-replay.log','interface.log','reference.log']:
            path=folder/name
            if path.is_file():add(f'evidence/{directory}/{name}',path)
    module=args.module_zip.read_bytes()
    if sha(module)!=MODULE_SHA:raise ValueError('module ZIP SHA mismatch')
    files['tests/dependencies/modules.zip']=module
    lock=json.loads((ROOT/'reference_package/fixtures/success/module-lock.json').read_text())
    builder_raw=Path(__file__).read_bytes()
    if builder_raw!=subprocess.check_output(['git','show',commit+':godot_candidate/tools/build.py'],cwd=ROOT):raise ValueError('builder differs from source commit')
    manifest=dict(schema='mapgen/reference-package/v1',package=dict(name=NAME,version='0.3.0',algorithm='stable-v2',implementation='mapgen/gdscript-candidate-0.3.0'),
                  runtime_target='godot-standard-gdscript',readiness=dict(status='candidate',production_ready=False,whole_map_physics='NOT_RUN',playable_in_host='NOT_RUN',mobile_device='NOT_RUN'),
                  source=dict(repository='https://github.com/zhipijun1996/map-gen',commit=commit,base_commit='0d338c2309d4e17bd8e9b128f745eb93938e99b2',builder_sha256=sha(builder_raw),files=sources),
                  protocol=dict(request='mapgen/generation-request/v1',config='mapgen/generator-config/v1',result='mapgen/generation-result/v1',map='mapgen/runtime-map/v2',content='pcg/compiled-module-content/v1'),
                  module_zip_ref='tests/dependencies/modules.zip',module_lock=lock,
                  determinism=dict(seed_min='-9007199254740991',seed_max='9007199254740991',rng='python-mt19937-v1',encoding='data_json.canonical: Godot full-precision typed JSON; NOT Python canonical',rules='docs/HOST_API.md'),
                  dependencies=dict(runtime='Godot Standard 4.6.3, no external runtime libraries',web='matching official single-thread Standard export template; browser WebAssembly/WebGL2'),
                  verification='godot --headless --path <unpacked> --script res://tests/verify_bundle.gd -- <explicit modules.zip>',
                  files={name:sha(raw) for name,raw in sorted(files.items())})
    files['manifest.json']=encoded(manifest)
    args.out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='mapgen-godot-independent-') as tmp:
        folder=Path(tmp)/NAME
        for name,raw in files.items():
            dest=folder/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        run=subprocess.run([args.godot,'--headless','--path',str(folder),'--script','res://tests/verify_bundle.gd','--',str(folder/'tests/dependencies/modules.zip')],cwd=tmp,text=True,capture_output=True,timeout=150)
        (args.out/'standalone.log').write_text(run.stdout+run.stderr)
        if run.returncode or 'SCRIPT ERROR' in run.stderr:raise RuntimeError(run.stdout+run.stderr)
        if not any('"status":"PASS"' in line for line in run.stdout.splitlines()):raise RuntimeError('missing standalone PASS')
    dest=args.out/(NAME+'.zip')
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(NAME+'/'+name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,raw,compresslevel=9)
    digest=sha(dest.read_bytes())
    (args.out/(dest.name+'.sha256')).write_text(digest+'  '+dest.name+'\n')
    web_report=json.loads((ROOT/'validation/godot-candidate-0.3.0/web-final/summary.json').read_text())
    if web_report['status']!='PASS':raise ValueError('Web execution not verified')
    for name,expected in web_report['component_source_sha256'].items():
        if sha((project/'addons/mapgen'/name).read_bytes())!=expected:raise ValueError('Web source differs:'+name)
    web_files={}
    for name,expected in web_report['export_sha256'].items():
        raw=(project/'build/web'/name).read_bytes()
        if sha(raw)!=expected:raise ValueError('Web export differs:'+name)
        web_files[name]=raw
    web_files['README.txt']=b'Local conformance export only; not a playable game or deployment.\nServe this directory with python3 -m http.server --bind 127.0.0.1 8000, then open http://127.0.0.1:8000/.\nResult is available as window.mapgenReport in the browser console. No Python is used by generation.\n'
    web_dest=args.out/'mapgen-web-conformance-0.3.0.zip'
    with zipfile.ZipFile(web_dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(web_files.items()):
            info=zipfile.ZipInfo('mapgen-web-conformance-0.3.0/'+name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,raw,compresslevel=9)
    web_sha=sha(web_dest.read_bytes())
    (args.out/(web_dest.name+'.sha256')).write_text(web_sha+'  '+web_dest.name+'\n')
    receipt=dict(status='PASS',archive=dest.name,sha256=digest,bytes=dest.stat().st_size,source_commit=commit,runtime_target=manifest['runtime_target'],readiness=manifest['readiness'],manifest_sha256=sha(files['manifest.json']),standalone_verified=True,web_archive=dict(path=web_dest.name,sha256=web_sha,bytes=web_dest.stat().st_size))
    (args.out/'receipt.json').write_bytes(encoded(receipt));print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
