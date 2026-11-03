extends SceneTree
const A = preload("res://addons/mapgen/module_archive.gd")
const P = preload("res://addons/mapgen/prepared_library.gd")
const J = preload("res://addons/mapgen/data_json.gd")
const T = preload("res://addons/mapgen/content_transform.gd")
func _initialize():
 var a=A.open_zip(OS.get_cmdline_user_args()[0],preload("res://addons/mapgen/protocol.gd").PACKAGE_SHA)
 if not a.ok:print(a);quit(1);return
 var p=P.new()
 var r=J.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
 var c=J.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
 p.begin(a.library,r,c)
 while not p.ready and p.error.is_empty():p.advance_one()
 print({"error":p.error,"templates":p.templates.size(),"entries":p.entries.size()})
 var out={"keys":p.templates.keys(),"templates":p.templates,"materialized":{}}
 for key in p.templates:
  out.materialized[key]=[T.materialize(p.templates[key],false,p.block_pixels),T.materialize(p.templates[key],true,p.block_pixels)]
 var file=FileAccess.open(OS.get_cmdline_user_args()[1],FileAccess.WRITE)
 file.store_string(J.canonical(out))
 quit(0 if p.error.is_empty() else 1)
