extends RefCounted
static func overlap(a: Array,b: Array) -> bool:
	return a[0]<b[0]+b[2] and b[0]<a[0]+a[2] and a[1]<b[1]+b[3] and b[1]<a[1]+a[3]
static func expand(r: Array,x: float,y: float) -> Array:return [r[0]-x,r[1]-y,r[2]+2*x,r[3]+2*y]
static func move_rect(r: Array,origin: Array) -> Array:return [r[0]+origin[0],r[1]+origin[1],r[2],r[3]]
static func distance(a: Array,b: Array) -> float:return sqrt(pow(a[0]-b[0],2)+pow(a[1]-b[1],2))
static func point_rect(p: Array,r: float) -> Array:return [p[0]-r,p[1]-r,2*r,2*r]
static func swept(a: Array,b: Array,r: float) -> Array:return [minf(a[0],b[0])-r,minf(a[1],b[1])-r,absf(a[0]-b[0])+2*r,absf(a[1]-b[1])+2*r]
static func along(points: Array,t: float) -> Array:
	for i in range(1,points.size()):
		var length: float=distance(points[i-1],points[i])
		if length>0 and t<=length:
			var f: float=t/length
			return [lerpf(points[i-1][0],points[i][0],f),lerpf(points[i-1][1],points[i][1],f)]
		t-=length
	return points[-1]
