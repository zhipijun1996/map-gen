"""Independent pure-GDScript map additions project; core algorithms untouched."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def assemble(out):
    out.mkdir(parents=True,exist_ok=False);addon=out/'addons/mapgen_additions';addon.mkdir(parents=True)
    for name in ['data_json.gd','decimal64.gd','python_rng.gd','work_gate.gd']:
        raw=(ROOT/'godot_runtime/addons/mapgen'/name).read_text().replace('res://addons/mapgen/','res://addons/mapgen_additions/')
        (addon/name).write_text(raw)
    for path in (ROOT/'map_additions/runtime').glob('*.gd'):shutil.copyfile(path,addon/path.name)
    digest=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in sorted(addon.glob('*.gd')))).hexdigest()[:12]
    p=addon/'protocol.gd';p.write_text(p.read_text().replace('mapgen/additions-gdscript-0.1.0"','mapgen/additions-gdscript-0.1.0+'+digest+'"'))
    (out/'tests').mkdir()
    for path in (ROOT/'map_additions/tests').glob('*.gd'):shutil.copyfile(path,out/'tests'/path.name)
    (out/'project.godot').write_text('config_version=5\n[application]\nconfig/name="Map additions experiment"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
    (out/'source-lock.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(addon.glob('*.gd'))},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);assemble(p.parse_args().out)
