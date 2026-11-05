"""Assemble the independently versioned joint route-construction experiment."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from structure_routes.tools.setup import assemble as baseline
from branch_routes.tools.setup import ROOT
ALGORITHM='experimental-v7-joint-route-construction'
def assemble(out,profile):
    baseline(out,ROOT/'structure_routes/profiles/merge.json');addon=out/'addons/mapgen'
    shutil.copyfile(addon/'solver.gd',addon/'structure_basis.gd')
    for path in (ROOT/'route_construction/runtime').glob('*.gd'):shutil.copyfile(path,addon/path.name)
    schema=json.loads((out/'schemas/config.schema.json').read_text());schema['properties']['algorithm']={'const':ALGORITHM};schema['required'].append('construction')
    schema['properties']['construction']={'type':'object','additionalProperties':False,'required':['anchor_growth_count','max_anchor_growth_count','bypass_depth','macro_candidate_limit','core_loop_policy'],'properties':{'core_loop_policy':{'type':'string','enum':['path_gain','legacy']},'anchor_growth_count':{'type':'integer','minimum':2},'max_anchor_growth_count':{'type':'integer','minimum':2},'bypass_depth':{'type':'integer','enum':[1,2]},'macro_candidate_limit':{'type':'integer','minimum':1}}}
    path=addon/'protocol.gd';raw=path.read_text();raw=re.sub(r'const ALGORITHM := "[^"]+"',f'const ALGORITHM := "{ALGORITHM}"',raw);raw=re.sub(r'const IMPLEMENTATION := "[^"]+"','const IMPLEMENTATION := "mapgen/gdscript-experiment-0.8.0"',raw)
    raw=raw.replace('if config.diversity.early_fraction >=','if config.topology.reward_modes.count("forward_merge")!=1 or config.construction.anchor_growth_count>config.construction.max_anchor_growth_count or config.construction.max_anchor_growth_count>config.topology.backbone_min:\n\t\treturn "config.construction: requires exactly one forward merge and valid anchor range"\n\tif config.diversity.early_fraction >=');path.write_text(raw)
    (addon/'schema_data.gd').write_text('extends RefCounted\nconst REQUEST = '+json.dumps(json.load(open(ROOT/'schemas/request.schema.json')),indent=2)+'\nconst CONFIG = '+json.dumps(schema,indent=2)+'\n')
    digest=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in sorted(addon.glob('*.gd')))).hexdigest()[:12];impl='mapgen/gdscript-experiment-0.8.0+'+digest;path.write_text(raw.replace('mapgen/gdscript-experiment-0.8.0"',impl+'"'))
    path=addon/'derived_library.gd';path.write_text(re.sub(r'const IMPLEMENTATION="[^"]+"',f'const IMPLEMENTATION="{impl}"',path.read_text()))
    (out/'schemas/config.schema.json').write_text(json.dumps(schema,indent=2)+'\n');path=out/'schemas/runtime-map.schema.json';v=json.loads(path.read_text());g=v['properties']['generator']['properties'];g['algorithm']['enum'].append(ALGORITHM);g['implementation']['enum'].append(impl);path.write_text(json.dumps(v,indent=2)+'\n')
    shutil.copyfile(profile,out/'tests/config.json')
    for path in (ROOT/'route_construction/tests').glob('*.gd'):shutil.copyfile(path,out/'tests'/path.name)
    (out/'source-lock.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(addon.glob('*.gd'))},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--profile',type=Path,default=ROOT/'route_construction/profiles/joint-merge.json');a=p.parse_args();assemble(a.out,a.profile)
