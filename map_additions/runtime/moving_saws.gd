extends RefCounted
const G=preload("geometry.gd")
var j
func _init(job):j=job
func reject(reason: String):j.stats.candidate_rejections[reason]=j.stats.candidate_rejections.get(reason,0)+1
func run() -> bool:
	j._phase="boundary_candidates"
	var cfg: Dictionary=j.config.moving_saws
	var b: int=j.map_data.coordinates.block_size_pixels
	var edges: Array=[]
	for item in j.map_data.instances:
		var o: Array=j.origin(item);var w: int=item.size_blocks[0]*b;var h: int=item.size_blocks[1]*b
		edges.append_array([[0,o[0],o[1],o[1]+h,item.id],[0,o[0]+w,o[1],o[1]+h,item.id],[1,o[1],o[0],o[0]+w,item.id],[1,o[1]+h,o[0],o[0]+w,item.id]])
	var segments: Dictionary={}
	for e in edges:
		if not await j.tick():return false
		var cuts: Array=[e[2],e[3]]
		for other in edges:
			if e[0]==other[0] and e[1]==other[1] and e[4]!=other[4] and maxf(e[2],other[2])<minf(e[3],other[3]):cuts.append(maxf(e[2],other[2]));cuts.append(minf(e[3],other[3]))
		cuts.sort()
		for i in range(1,cuts.size()):
			if cuts[i]<=cuts[i-1]:continue
			var key: Array=[e[0],int(e[1]),int(cuts[i-1]),int(cuts[i])]
			if not segments.has(key):segments[key]={"key":key,"instances":[]}
			if not e[4] in segments[key].instances:segments[key].instances.append(e[4])
	var random=j.rng("moving-saws",cfg)
	var candidates: Array=[]
	for segment in segments.values():
		var key: Array=segment.key;var length: float=key[3]-key[2]
		var travel: float=minf(cfg.max_travel_pixels,length-2*(cfg.radius_pixels+cfg.margin_pixels))
		if travel<cfg.min_travel_pixels:continue
		var span: float=travel+2*(cfg.radius_pixels+cfg.margin_pixels)
		var windows: int=maxi(1,int(ceil(length/span)))
		for index in range(windows):
			if not await j.tick():return false
			if candidates.size()>=cfg.candidate_limit:break
			var center: float=key[2]+length*(index+0.5)/windows
			var low: float=maxf(key[2]+cfg.radius_pixels+cfg.margin_pixels,center-travel/2)
			var high: float=minf(key[3]-cfg.radius_pixels-cfg.margin_pixels,center+travel/2)
			if high-low<cfg.min_travel_pixels:continue
			var a: Array=[key[1],low] if key[0]==0 else [low,key[1]]
			var z: Array=[key[1],high] if key[0]==0 else [high,key[1]]
			var envelope: Array=G.swept(a,z,cfg.radius_pixels)
			var half: Array=j.map_data.inputs.request.player.clearance_half_extents_pixels
			var expanded: Array=G.expand(envelope,half[0]+cfg.margin_pixels,half[1]+cfg.margin_pixels)
			var reason: String=blocked(expanded)
			if not reason.is_empty():reject(reason);continue
			var midpoint: Array=[(a[0]+z[0])/2,(a[1]+z[1])/2]
			var nearby:=0
			for p in j.existing_centers:
				if G.distance(midpoint,p)<cfg.density_radius_pixels:nearby+=1
			var internal: bool=segment.instances.size()>1
			candidates.append({"a":a,"b":z,"envelope":envelope,"expanded":expanded,"center":midpoint,"boundary":key.duplicate(),"instances":segment.instances.duplicate(),"priority":(10.0 if internal else 0.0)-nearby+random.random(),"internal":internal})
	j.stats.boundary_candidates=candidates.size()
	candidates.sort_custom(func(a,b):return a.priority>b.priority)
	j._phase="moving_saw_selection"
	for candidate in candidates:
		if not await j.tick():return false
		if j.saws.size()>=cfg.max_groups:break
		if not candidate.internal and random.random()>cfg.random_keep_probability:reject("outer_random_sample");continue
		var local:=0;var conflict:=false
		for placed in j.saws:
			var dist: float=G.distance(candidate.center,placed.center_pixels)
			if dist<cfg.min_spacing_pixels or G.overlap(candidate.expanded,placed.protected_envelope_pixels):conflict=true;break
			if dist<cfg.density_radius_pixels:local+=1
		if conflict:reject("new_group_spacing");continue
		# Adding a candidate must preserve the cap around EVERY existing center.
		var density_conflict: bool=local>=cfg.max_local_groups
		for placed in j.saws:
			if G.distance(candidate.center,placed.center_pixels)>=cfg.density_radius_pixels:continue
			var around:=2
			for other in j.saws:
				if other.id!=placed.id and G.distance(placed.center_pixels,other.center_pixels)<cfg.density_radius_pixels:around+=1
			if around>cfg.max_local_groups:density_conflict=true;break
		if density_conflict:reject("local_density");continue
		var travel: Array=[candidate.b[0]-candidate.a[0],candidate.b[1]-candidate.a[1]]
		j.saws.append({"id":j.stable("moving-saw-",[candidate.boundary,candidate.a,candidate.b]),"kind":"moving_saw","origin":candidate.a,"travel":travel,"radius":cfg.radius_pixels,"period":cfg.period_seconds,"initial_phase":random.random(),"center_pixels":candidate.center,"swept_envelope_pixels":candidate.envelope,"protected_envelope_pixels":candidate.expanded,"boundary_instances":candidate.instances,"boundary_class":"internal" if candidate.internal else "outer","placement_validation":"STATIC_CONSERVATIVE; not proof all illegal crossings blocked"})
	return true
func blocked(rect: Array) -> String:
	for solid in j.solids:
		if G.overlap(rect,solid):return "solid_or_seal"
	for danger in j.dangers:
		if G.overlap(rect,danger):return "existing_dynamic_hazard"
	for safe in j.protections:
		if G.overlap(rect,safe):return "port_route_reward_or_terminal"
	for board in j.boards:
		if G.overlap(rect,G.point_rect(board.interaction_position_pixels,j.config.signage.interact_radius_pixels)):return "sign_interaction"
	return ""
