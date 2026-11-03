import json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
text='extends RefCounted\n# Embedded from existing public schemas; implementation domain is checked by Protocol.\n'
for name,file in [('REQUEST','request.schema.json'),('CONFIG','config.schema.json')]:text+='const '+name+' = '+json.dumps(json.loads((root/'schemas'/file).read_text()),ensure_ascii=False,indent=2)+'\n'
(root/'godot_runtime/addons/mapgen/schema_data.gd').write_text(text)
