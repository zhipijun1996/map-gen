extends Node2D
## Review harness only. The addon does not depend on nodes, rendering or gameplay.
const DATA=preload("res://addons/mapgen_additions/data_json.gd")
const JOB=preload("res://addons/mapgen_additions/job.gd")
var source: Dictionary
var value: Dictionary={}
var job
var zoom:=0.04
var offset:=Vector2(100,300)
var elapsed:=0.0
var panel: Label
var title: Label
var select: OptionButton
var begin_usec:=0
var cancel_input_usec:=0
var selected_algorithm: String="v7"
var generation:=0
func read(path: String):return DATA.parse(FileAccess.get_file_as_string(path)).value
func _ready():
	var ui:=CanvasLayer.new();add_child(ui)
	var bg:=ColorRect.new();bg.position=Vector2(10,10);bg.size=Vector2(540,220);bg.color=Color(0.02,0.04,0.08,0.94);ui.add_child(bg)
	title=Label.new();title.position=Vector2(20,18);title.text="MAP ADDITIONS / real frozen map / live postprocess";ui.add_child(title)
	select=OptionButton.new();select.position=Vector2(20,50)
	for name in ["v5 / 0.6.0","v6 returns / 0.7.0","v6 merge / 0.7.0","v7 / 0.8.0"]:select.add_item(name)
	select.select(3);select.item_selected.connect(func(index):start(["v5","v6returns","v6merge","v7"][index]));ui.add_child(select)
	panel=Label.new();panel.position=Vector2(20,90);panel.text="Loading";panel.add_theme_font_size_override("font_size",14);ui.add_child(panel)
	start("v7")
func publish(name: String,data):
	if OS.has_feature("web"):JavaScriptBridge.eval("window."+name+"="+DATA.canonical(data),true)
func start(algorithm: String):
	if job!=null and not job.is_done():job.cancel()
	generation+=1;selected_algorithm=algorithm;value={};cancel_input_usec=0
	source=read("res://inputs/"+algorithm+".json");var cfg=read("res://inputs/config.json")
	begin_usec=Time.get_ticks_usec();job=JOB.create(source,cfg)
	var box: Array=source.map.bounds_blocks;var b: int=source.map.coordinates.block_size_pixels
	zoom=minf(1100.0/((box[2]-box[0])*b),580.0/((box[3]-box[1])*b));offset=Vector2(650,440)-Vector2((box[0]+box[2])*b/2,(box[1]+box[3])*b/2)*zoom
	publish("additionsStage","running");publish("additionsReport",null)
func _process(delta: float):
	elapsed+=delta
	if job!=null and not job.is_done():
		# Soft review scheduler: repeated advance(1), at most128/frame or8ms.
		var frame_start:=Time.get_ticks_usec()
		for _attempt in range(128):
			job.advance(1)
			if job.is_done() or Time.get_ticks_usec()-frame_start>=8000:break
		panel.text="Live postprocess: "+job.phase_name()+"\nEscape: cancel; wheel: zoom; drag: pan\nOrange moving gears; cyan signs (click to inspect)\nReview animation only; no physics or gameplay certification"
		if job.is_done():
			value=job.result();var points: Array=[]
			for sign in value.signs:points.append({"id":sign.id,"screen":[sign.position_pixels[0]*zoom+offset.x,sign.position_pixels[1]*zoom+offset.y]})
			var report: Dictionary={"algorithm":selected_algorithm,"result":value,"profile":job.profile(),"wall_usec":Time.get_ticks_usec()-begin_usec,"callback_cancel_usec":Time.get_ticks_usec()-cancel_input_usec if cancel_input_usec else null,"sign_screen_points":points,"generation":generation}
			publish("additionsReport",report);publish("additionsStage","done")
			panel.text=value.status+" / signs "+str(value.signs.size())+" / moving gears "+str(value.moving_saws.size())+"\nClick a cyan sign: chest / shop / boss\nMouse wheel: zoom; drag: pan; Escape: cancel\nNo whole-map physics or main-game interaction test"
	queue_redraw()
func _input(event):
	if event is InputEventKey or event is InputEventMouseButton:publish("lastReviewInput",str(event))
	if event is InputEventKey and event.pressed and event.keycode in [KEY_1,KEY_2,KEY_3,KEY_4]:
		var index: int=event.keycode-KEY_1;select.select(index);start(["v5","v6returns","v6merge","v7"][index])
	if event is InputEventKey and event.pressed and event.keycode==KEY_ESCAPE and job!=null and not job.is_done():
		cancel_input_usec=Time.get_ticks_usec();job.cancel()
		value=job.result()
		if OS.has_feature("web"):JavaScriptBridge.eval("window.additionsCancelDoneDomTime=performance.now()",true)
		publish("additionsReport",{"algorithm":selected_algorithm,"result":value,"callback_cancel_usec":Time.get_ticks_usec()-cancel_input_usec});publish("additionsStage","done");panel.text="CANCELLED / no usable additions"
	if event is InputEventMouseButton and event.pressed and event.position.y>235:
		if event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
			var before: Vector2=(event.position-offset)/zoom;zoom*=1.18 if event.button_index==MOUSE_BUTTON_WHEEL_UP else 1.0/1.18;offset=event.position-before*zoom
		elif event.button_index==MOUSE_BUTTON_LEFT:
			for board in value.get("signs",[]):
				if (v(board.position_pixels)-event.position).length()<13:
					var text: String="Sign "+board.id+" / "+board.mount+"\n"
					for view in board.views:
						text+="arrive "+view.arrival_port_id+": "
						for d in view.directions:text+=d.arrow+"="+str(d.categories)+"  "
						text+=" shared="+str(view.shared_categories)+"\n"
					panel.text=text;publish("signInspection",board);break
	if event is InputEventMouseMotion and event.button_mask&MOUSE_BUTTON_MASK_LEFT:offset+=event.relative
func v(p: Array) -> Vector2:return Vector2(p[0],p[1])*zoom+offset
func rect(r: Array,o: Array) -> Rect2:return Rect2(v([r[0]+o[0],r[1]+o[1]]),Vector2(r[2],r[3])*zoom)
func _draw():
	draw_rect(Rect2(Vector2.ZERO,Vector2(1800,1100)),Color("0c1322"))
	if source.is_empty():return
	for item in source.map.instances:
		var b: int=source.map.coordinates.block_size_pixels;var o: Array=[item.origin_blocks[0]*b,item.origin_blocks[1]*b]
		draw_rect(rect([0,0,item.size_blocks[0]*b,item.size_blocks[1]*b],o),Color("1e3048"),false,1)
		var body: Dictionary=source.content_store[item.content_ref]
		for r in body.get("platforms",[]):draw_rect(rect(r,o),Color("657387"))
		for seal in item.seals:draw_rect(rect(seal.rect_pixels,o),Color("b64554"))
		for route in item.routes:
			for n in range(1,route.author_path_pixels.size()):
				var a: Array=route.author_path_pixels[n-1];var z: Array=route.author_path_pixels[n]
				draw_line(v([a[0]+o[0],a[1]+o[1]]),v([z[0]+o[0],z[1]+o[1]]),Color(0.2,0.7,0.5,0.22),1)
		for site in body.get("reward_sites",[]):draw_circle(v([site.position[0]+o[0],site.position[1]+o[1]]),3,Color("e7c75c"))
	for saw in value.get("moving_saws",[]):
		var phase: float=fposmod(elapsed/saw.period+saw.initial_phase,1);var t: float=1-absf(2*phase-1)
		var end: Array=[saw.origin[0]+saw.travel[0],saw.origin[1]+saw.travel[1]];draw_line(v(saw.origin),v(end),Color("9f633e"),2)
		var p: Vector2=v([saw.origin[0]+saw.travel[0]*t,saw.origin[1]+saw.travel[1]*t]);var radius: float=maxf(5,saw.radius*zoom)
		draw_circle(p,radius,Color("ff9a45"));draw_arc(p,radius+2,elapsed*3,elapsed*3+TAU*0.85,12,Color("ffc38b"),2)
	for board in value.get("signs",[]):draw_rect(Rect2(v(board.position_pixels)-Vector2(4,4),Vector2(8,8)),Color("5ad8ed"))
