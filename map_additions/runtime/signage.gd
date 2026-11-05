extends RefCounted
## One logical view per reachable arrival context; nearby views share a board.
const G=preload("geometry.gd")
var j
func _init(job):j=job
func run() -> bool:
	j._phase="sign_analysis"
	for item in j.map_data.instances:
		var arrivals: Dictionary={}
		for route in item.routes:
			if not route.from_port in item.connected_port_ids or not route.to_port in item.connected_port_ids:continue
			var nid: String=j.port_nodes.get([item.id,route.from_port,"port_arrive"],"")
			if not j.reachable.has(nid):continue
			if not arrivals.has(route.from_port):arrivals[route.from_port]={}
			if not arrivals[route.from_port].has(route.to_port):arrivals[route.from_port][route.to_port]=[]
			arrivals[route.from_port][route.to_port].append(route)
		var incoming_ids: Array=arrivals.keys();incoming_ids.sort()
		for incoming in incoming_ids:
			if not await j.tick():return false
			var exits: Dictionary=arrivals[incoming]
			if exits.size()<2:continue
			var routes: Array=[];var choices: Array=[];var distances: Array=[]
			var pids: Array=exits.keys();pids.sort()
			for pid in pids:
				var nid: String=j.port_nodes.get([item.id,pid,"port_depart"],"")
				if nid.is_empty():continue
				var reached: Dictionary=await j.walk(nid,item.id)
				if j.is_done():return false
				var cost: Dictionary={}
				for tid in j.targets:
					for node in j.targets[tid].node_ids:
						if reached.has(node):cost[tid]=minf(cost.get(tid,1e15),reached[node])
				# Reward nodes on this selected local Route precede the exit.
				var rids: Array=[]
				for route in exits[pid]:
					rids.append(route.id)
					for rid in route.required_reward_ids:
						var key: String="chest:"+item.id+":"+rid
						if j.targets.has(key):cost[key]=0
				var p: Dictionary={}
				for port in item.ports:
					if port.id==pid:p=port
				choices.append({"exit_port_id":pid,"route_ids":rids,"exit_position_pixels":j.world(item,p.local_position_pixels),"categories":[],"targets":[]})
				distances.append(cost);routes.append(exits[pid][0].author_path_pixels)
			if choices.size()<2:continue
			var main_pid: String=main_exit(item.id,incoming)
			var shared: Array=[]
			for tid in j.targets:
				var best:=1e15;var all_same:=true;var first: float=distances[0].get(tid,1e15)
				for cost in distances:
					var c: float=cost.get(tid,1e15);best=minf(best,c)
					if c!=first:all_same=false
				if best==1e15:continue
				var target: Dictionary=j.targets[tid]
				if target.kind!="boss" and all_same:shared.append(tid);continue
				var assigned_main:=false
				if target.kind=="boss":
					for i in range(choices.size()):
						if choices[i].exit_port_id==main_pid and distances[i].has(tid):assign(choices[i],tid);assigned_main=true
				if not assigned_main:
					for i in range(choices.size()):
						if distances[i].get(tid,1e15)==best:assign(choices[i],tid)
			for choice in choices:choice.categories.sort();choice.targets.sort()
			var fork: Dictionary=await fork_point(item,routes)
			if j.is_done():return false
			var point: Array=fork.point
			for index in range(choices.size()):
				var forward: Array=j.world(item,G.along(routes[index],fork.distance+j.config.signage.branch_separation_pixels))
				choices[index].route_direction_vector=[forward[0]-point[0],forward[1]-point[1]]
			var decision: Dictionary={"id":j.stable("decision-",[item.id,incoming,pids]),"instance_id":item.id,"arrival_port_id":incoming,"fork_position_pixels":point,"directions":choices,"routing_scope":"nearest known target per exit without re-entering junction instance; Boss prefers public reference main path; graph guidance only"}
			j.decisions.append(decision);j.stats.decisions+=1
			j._phase="sign_placement"
			var placement: Dictionary=await place(item,point,choices,incoming,fork.distance,shared)
			if j.is_done():return false
			if placement.is_empty():
				j.gaps.append({"decision_id":decision.id,"instance_id":item.id,"arrival_port_id":incoming,"reason":"NO_TAGGABLE_TARGET" if shared.is_empty() and choices.all(func(c):return c.categories.is_empty()) else "NO_CLEAR_SUPPORTED_OR_SUSPENDED_PLACEMENT","fork_position_pixels":point})
			else:
				var shared_categories: Array=[]
				for tid in shared:
					if not j.targets[tid].kind in shared_categories:shared_categories.append(j.targets[tid].kind)
				var view: Dictionary={"decision_id":decision.id,"arrival_port_id":incoming,"directions":choices,"shared_targets":shared,"shared_categories":shared_categories}
				var board: Dictionary={}
				for existing in j.boards:
					if existing.instance_id==item.id and G.distance(existing.position_pixels,placement.position_pixels)<=j.config.signage.merge_radius_pixels:
						# A merged marker is one physical board with approach-specific
						# views; route permissions never become an unconditional union.
						if G.distance(existing.interaction_position_pixels,point)<=j.config.signage.interact_radius_pixels:board=existing;break
				if board.is_empty():
					board={"id":j.stable("sign-",[item.id,decision.id]),"instance_id":item.id,"position_pixels":placement.position_pixels,"interaction_position_pixels":placement.interaction_position_pixels,"actor_stand_position_pixels":placement.get("actor_stand_position_pixels"),"mount":placement.mount,"views":[],"collidable":false,"interaction":"inspect_routes","placement_validation":"STATIC_PROVISIONAL; suspended mounts have no floor proof; host standing/interaction NOT_RUN"}
					j.boards.append(board)
				for choice in view.directions:
					var d: Array=choice.route_direction_vector
					if G.distance(d,[0,0])<1:d=[choice.exit_position_pixels[0]-point[0],choice.exit_position_pixels[1]-point[1]]
					choice.arrow=arrow(d)
				board.views.append(view);j.stats.placed_decisions+=1
			j._phase="sign_analysis"
	return true
func arrow(d: Array) -> String:
	if absf(d[0])>2*absf(d[1]):return "right" if d[0]>=0 else "left"
	if absf(d[1])>2*absf(d[0]):return "down" if d[1]>=0 else "up"
	return ("down" if d[1]>=0 else "up")+"_"+("right" if d[0]>=0 else "left")
func assign(choice: Dictionary,tid: String):
	var kind: String=j.targets[tid].kind
	if not kind in choice.categories:choice.categories.append(kind)
	if not tid in choice.targets:choice.targets.append(tid)
func main_exit(iid: String,pid: String) -> String:
	var arrival: String=j.port_nodes.get([iid,pid,"port_arrive"],"")
	for path in j.map_data.graph.main_paths:
		var at: int=path.find(arrival)
		if at<0:continue
		for i in range(at+1,path.size()):
			var node: Dictionary=j.nodes[path[i]]
			if node.instance_id!=iid:break
			if node.kind=="port_depart":return node.port_id
	return ""
func fork_point(item: Dictionary,routes: Array) -> Dictionary:
	var previous: Array=j.world(item,routes[0][0])
	for step in range(0,65):
		if not await j.tick():return {}
		var points: Array=[];var x:=0.0;var y:=0.0
		for path in routes:
			var p: Array=G.along(path,step*j.config.signage.sample_step_pixels);points.append(p);x+=p[0];y+=p[1]
		var spread:=0.0
		for a in points:
			for b in points:spread=maxf(spread,G.distance(a,b))
		if spread>=j.config.signage.branch_separation_pixels:return {"point":previous,"distance":maxi(0,step-1)*j.config.signage.sample_step_pixels}
		previous=j.world(item,[x/points.size(),y/points.size()])
	return {"point":previous,"distance":64*j.config.signage.sample_step_pixels}
func place(item: Dictionary,point: Array,choices: Array,incoming: String,prefix_distance: float,shared: Array) -> Dictionary:
	if shared.is_empty() and choices.all(func(c):return c.categories.is_empty()):return {}
	var body: Dictionary=j.contents[item.content_ref]
	var cfg: Dictionary=j.config.signage;var half: Array=j.map_data.inputs.request.player.clearance_half_extents_pixels
	var candidates: Array=[]
	for index in range(body.get("platforms",[]).size()):
		if index in body.get("wall_platform_indices",[]):continue
		var r: Array=G.move_rect(body.platforms[index],j.origin(item))
		for n in range(int(ceil(r[2]/cfg.sample_step_pixels))+1):
			if not await j.tick():return {}
			var x: float=r[0]+n*cfg.sample_step_pixels
			if x<r[0]+half[0] or x>r[0]+r[2]-half[0]:continue
			var stand: Array=[x,r[1]-half[1]]
			if G.distance(stand,point)>cfg.search_radius_pixels:continue
			var actor: Array=[x-half[0],r[1]-2*half[1],2*half[0],2*half[1]]
			var board: Array=[x-cfg.board_size_pixels[0]/2,r[1]-cfg.board_size_pixels[1],cfg.board_size_pixels[0],cfg.board_size_pixels[1]]
			var blocked:=false
			for obstacle in j.solids:
				if G.overlap(actor,obstacle) or G.overlap(board,obstacle):blocked=true;break
			if blocked:continue
			for danger in j.dangers:
				if G.overlap(G.expand(actor,8,8),danger) or G.overlap(board,danger):blocked=true;break
			if blocked:continue
			# Require an actual declared incoming Route to pass near this stand.
			var near_route:=false
			for route in item.routes:
				if route.from_port!=incoming:continue
				var walked:=0.0
				for index2 in range(route.author_path_pixels.size()):
					if index2>0:walked+=G.distance(route.author_path_pixels[index2-1],route.author_path_pixels[index2])
					if walked>prefix_distance+cfg.sample_step_pixels:break
					var p: Array=route.author_path_pixels[index2]
					if G.distance(stand,j.world(item,p))<=cfg.interact_radius_pixels:near_route=true;break
				if near_route:break
			if near_route:candidates.append([G.distance(stand,point),x,r[1],stand])
	candidates.sort_custom(func(a,b):return a[0]<b[0] if a[0]!=b[0] else a[1]<b[1] if a[1]!=b[1] else a[2]<b[2])
	if candidates.is_empty():return await suspended(item,point,incoming,prefix_distance) if cfg.allow_suspended else {}
	var row: Array=candidates[0]
	return {"position_pixels":[row[1],row[2]],"interaction_position_pixels":row[3],"actor_stand_position_pixels":row[3],"mount":"floor"}
func suspended(item: Dictionary,point: Array,incoming: String,prefix_distance: float) -> Dictionary:
	var cfg: Dictionary=j.config.signage;var half: Array=j.map_data.inputs.request.player.clearance_half_extents_pixels
	var options: Array=[]
	for route in item.routes:
		if route.from_port!=incoming:continue
		var length:=0.0
		for index in range(route.author_path_pixels.size()):
			if not await j.tick():return {}
			if index>0:length+=G.distance(route.author_path_pixels[index-1],route.author_path_pixels[index])
			if length>prefix_distance+cfg.sample_step_pixels:break
			var actor: Array=j.world(item,route.author_path_pixels[index])
			if G.distance(actor,point)>cfg.search_radius_pixels:continue
			var actor_rect: Array=[actor[0]-half[0],actor[1]-half[1],2*half[0],2*half[1]]
			var actor_blocked:=false
			for rect in j.solids+j.dangers:
				if G.overlap(actor_rect,rect):actor_blocked=true;break
			if actor_blocked:continue
			for offset in [[-48,-16],[48,-16],[0,-8]]:
				var p: Array=[actor[0]+offset[0],actor[1]+offset[1]]
				if G.distance(actor,p)>cfg.interact_radius_pixels:continue
				var box: Array=[p[0]-cfg.board_size_pixels[0]/2,p[1]-cfg.board_size_pixels[1],cfg.board_size_pixels[0],cfg.board_size_pixels[1]]
				var blocked:=false
				for rect in j.solids+j.dangers:
					if G.overlap(box,rect):blocked=true;break
				if not blocked:options.append([G.distance(actor,point),p[0],p[1],p,actor])
	options.sort_custom(func(a,b):return a[0]<b[0] if a[0]!=b[0] else a[1]<b[1] if a[1]!=b[1] else a[2]<b[2])
	if options.is_empty():return {}
	return {"position_pixels":options[0][3],"interaction_position_pixels":options[0][4],"actor_stand_position_pixels":null,"mount":"suspended"}
