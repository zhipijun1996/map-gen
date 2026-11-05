"""Assemble a new topology-first research algorithm; old versions stay frozen."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from joint_routes.tools.setup import assemble as baseline
from branch_routes.tools.setup import ROOT
ALGORITHM='experimental-v6-structure-first'

def assemble(out,profile):
    baseline(out);addon=out/'addons/mapgen'
    shutil.copyfile(addon/'solver.gd',addon/'solver_basis.gd')
    for path in (ROOT/'structure_routes/runtime').glob('*.gd'):shutil.copyfile(path,addon/path.name)
    schema=json.loads((out/'schemas/config.schema.json').read_text())
    schema['properties']['algorithm']={'const':ALGORITHM};schema['required'].append('topology')
    schema['properties']['topology']={'type':'object','additionalProperties':False,'required':['backbone_min','backbone_max','domain_limit','reward_modes'],'properties':{'backbone_min':{'type':'integer','minimum':2},'backbone_max':{'type':'integer','minimum':2},'domain_limit':{'type':'integer','minimum':1},'reward_modes':{'type':'array','minItems':1,'items':{'type':'string','enum':['multi_return','forward_merge']}}}}
    protocol=addon/'protocol.gd';raw=protocol.read_text();raw=re.sub(r'const ALGORITHM := "[^"]+"',f'const ALGORITHM := "{ALGORITHM}"',raw)
    raw=raw.replace('if config.diversity.early_fraction >=', 'if config.topology.reward_modes.size()!=config.goals.reward_target or config.topology.backbone_min>config.topology.backbone_max or config.topology.backbone_max>config.goals.growth_target:\n\t\treturn "config.topology: invalid mode count/backbone range"\n\tif config.diversity.early_fraction >=')
    raw=re.sub(r'const IMPLEMENTATION := "[^"]+"','const IMPLEMENTATION := "mapgen/gdscript-experiment-0.7.0"',raw);protocol.write_text(raw)
    (addon/'schema_data.gd').write_text('extends RefCounted\nconst REQUEST = '+json.dumps(json.loads((ROOT/'schemas/request.schema.json').read_text()),indent=2)+'\nconst CONFIG = '+json.dumps(schema,indent=2)+'\n')
    identity=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in sorted(addon.glob('*.gd')))).hexdigest()[:12];impl='mapgen/gdscript-experiment-0.7.0+'+identity
    protocol.write_text(raw.replace('mapgen/gdscript-experiment-0.7.0"',impl+'"'))
    path=addon/'derived_library.gd';path.write_text(re.sub(r'const IMPLEMENTATION="[^"]+"',f'const IMPLEMENTATION="{impl}"',path.read_text()))
    (out/'schemas/config.schema.json').write_text(json.dumps(schema,indent=2)+'\n')
    path=out/'schemas/runtime-map.schema.json';v=json.loads(path.read_text());g=v['properties']['generator']['properties'];g['algorithm']['enum'].append(ALGORITHM);g['implementation']['enum'].append(impl);path.write_text(json.dumps(v,indent=2)+'\n')
    shutil.copyfile(profile,out/'tests/config.json')
    shutil.copyfile(ROOT/'runtime_iteration/upstream/controller-request.json',out/'tests/request.json')
    for path in (ROOT/'structure_routes/tests').glob('*.gd'):shutil.copyfile(path,out/'tests'/path.name)
    (out/'source-lock.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(addon.glob('*.gd'))},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--profile',type=Path,default=ROOT/'structure_routes/profiles/returns.json');a=p.parse_args();assemble(a.out,a.profile)
