extends SceneTree
const SOLVER=preload("res://addons/mapgen/solver.gd")
const GEO=preload("res://addons/mapgen/geometry.gd")
const DATA=preload("res://addons/mapgen/data_json.gd")
class Gate extends RefCounted:
 func consume():return true
func _initialize():
 var gate=Gate.new()
 var solver=SOLVER.new(gate,{"seed":930001},{"templates":{}},{})
 var checks:=0
 var failures: Array=[]
 # More than the 64 cache entries, including cycles, sinks, disconnected graphs,
 # and absent nodes. Check duality against an independent forward traversal.
 for sample in range(80):
  var graph: Dictionary={}
  for a in range(9):
   for b in range(9):
    if (sample*17+a*13+b*7+a*b*3)%19<sample%7:
     var key: String="N%d"%a
     if not graph.has(key):graph[key]=[]
     graph[key].append("N%d"%b)
  for start in range(10):
   var at: String="N%d"%start
   var expected: Dictionary={at:true};var queue: Array=[at];var head:=0
   while head<queue.size():
    var node: String=queue[head];head+=1
    for next in graph.get(node,[]):
     if not expected.has(next):expected[next]=true;queue.append(next)
   for target in range(10):
    checks+=1
    if (await solver.reverse_reachable(graph,"N%d"%target)).has(at)!=expected.has("N%d"%target):failures.append([sample,start,target])
 # Pair keys remain exact at extreme supported origins; no Vector2 conversion.
 var items: Array=[]
 for x in [-2000000000,-1,0,1,2000000000]:
  items.append({"id":str(x),"ports":{"P":{"id":"P","world2":[x,-x],"face":"LEFT","surface":"ROCK","permission":"INOUT"}}})
 checks+=1
 if GEO.groups(items).size()!=5:failures.append("integer coordinate alias")
 var out={"status":"PASS" if failures.is_empty() else "FAIL","checks":checks,"failures":failures,"scope":"directed reachability equivalence and exact integer keys; not physics"}
 var args:=OS.get_cmdline_user_args()
 if args.size():FileAccess.open(args[0],FileAccess.WRITE).store_string(DATA.canonical(out))
 print(JSON.stringify(out));quit(0 if failures.is_empty() else 1)
