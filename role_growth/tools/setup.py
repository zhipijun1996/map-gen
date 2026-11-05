"""Independent v8 role-aware experiment assembled over frozen v7 sources."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from route_construction.tools.setup import assemble as baseline
ROOT=Path(__file__).resolve().parents[2]
ALGORITHM='experimental-v8-role-aware-growth'
def assemble(out,profile):
 baseline(out,ROOT/'route_construction/profiles/joint-merge.json');addon=out/'addons/mapgen';shutil.copyfile(addon/'solver.gd',addon/'joint_basis.gd')
 for p in (ROOT/'role_growth/runtime').glob('*.gd'):shutil.copyfile(p,addon/p.name)
 cfg=json.loads(profile.read_text());schema=json.loads((out/'schemas/config.schema.json').read_text());schema['properties']['algorithm']={'const':ALGORITHM};schema['required'].append('growth_roles');schema['properties']['growth_roles']={'type':'object','additionalProperties':False,'required':list(cfg['growth_roles']),'properties':{k:({'type':'boolean'} if isinstance(v,bool) else {'type':'integer','minimum':0}) for k,v in cfg['growth_roles'].items()}}
 p=addon/'protocol.gd';raw=p.read_text();raw=re.sub(r'const ALGORITHM := "[^"]+"',f'const ALGORITHM := "{ALGORITHM}"',raw);raw=re.sub(r'const IMPLEMENTATION := "[^"]+"','const IMPLEMENTATION := "mapgen/gdscript-experiment-0.9.0"',raw);p.write_text(raw)
 (addon/'schema_data.gd').write_text('extends RefCounted\nconst REQUEST = '+json.dumps(json.load(open(ROOT/'schemas/request.schema.json')),indent=2)+'\nconst CONFIG = '+json.dumps(schema,indent=2)+'\n')
 p=addon/'derived_library.gd';p.write_text(re.sub(r'const IMPLEMENTATION="[^"]+"','const IMPLEMENTATION="mapgen/gdscript-experiment-0.9.0"',p.read_text()))
 digest=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in sorted(addon.glob('*.gd')))).hexdigest()[:12];impl='mapgen/gdscript-experiment-0.9.0+'+digest
 for name in ['protocol.gd','derived_library.gd']:
  p=addon/name;p.write_text(p.read_text().replace('mapgen/gdscript-experiment-0.9.0"',impl+'"'))
 (out/'schemas/config.schema.json').write_text(json.dumps(schema,indent=2)+'\n');p=out/'schemas/runtime-map.schema.json';v=json.loads(p.read_text());g=v['properties']['generator']['properties'];g['algorithm']['enum'].append(ALGORITHM);g['implementation']['enum'].append(impl);p.write_text(json.dumps(v,indent=2)+'\n');shutil.copyfile(profile,out/'tests/config.json')
 (out/'source-lock.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(addon.glob('*.gd'))},indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--profile',type=Path,default=ROOT/'role_growth/profiles/default.json');a=p.parse_args();assemble(a.out,a.profile)
