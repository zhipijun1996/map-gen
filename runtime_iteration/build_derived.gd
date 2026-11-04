extends SceneTree
const LOAD=preload("res://addons/mapgen/preload_job.gd")
const P=preload("res://addons/mapgen/protocol.gd")
func _initialize():
 var args:=OS.get_cmdline_user_args()
 var job=LOAD.create(args[0],P.PACKAGE_SHA,false)
 while not job.is_done():job.advance(128)
 var result: Dictionary=job.result()
 if result.status!="PASS":quit(2);return
 var rows: Array=[]
 var archive=result.library
 var manifest=preload("res://addons/mapgen/data_json.gd").parse(archive._files["manifest.json"].get_string_from_utf8()).value
 add_row(rows,"manifest",manifest)
 var catalog: Dictionary=archive._json['catalog.json']
 var header:=catalog.duplicate();header.erase('modules');add_row(rows,"catalog_header",header)
 for entry in catalog.modules:add_row(rows,"catalog_module",entry)
 for path in archive._json:
  if path!="catalog.json":add_row(rows,"json:"+path,archive._json[path])
 var text='extends RefCounted\n# Rebuildable source-data cache; not a module source or map lookup.\nconst SCHEMA="mapgen/derived-library/v1"\nconst MODULE_SHA="'+P.PACKAGE_SHA+'"\nconst IMPLEMENTATION="'+P.IMPLEMENTATION+'"\nconst SOURCE_IMPLEMENTATION="'+P.IMPLEMENTATION+'"\nconst ROWS = '+JSON.stringify(rows,"",true,true)+'\n'
 FileAccess.open(args[1],FileAccess.WRITE).store_string(text)
 print('DERIVED rows=',rows.size(),' bytes=',text.to_utf8_buffer().size())
 quit()
func add_row(rows: Array,key: String,value):
 var raw:=var_to_bytes(value);var packed:=raw.compress(FileAccess.COMPRESSION_DEFLATE)
 var hash:=HashingContext.new();hash.start(HashingContext.HASH_SHA256);hash.update(packed)
 rows.append([key,raw.size(),hash.finish().hex_encode(),Marshalls.raw_to_base64(packed)])
