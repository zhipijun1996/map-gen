extends RefCounted
## Sufficient impossibility only: grounded + center-in-region cannot succeed
## when every center is strictly inside the union of seal-expanded AABBs.
static func check(region: Array, seals: Array, half_extents: Array, gate = null) -> Dictionary:
 if region.size()!=4 or region[2]<=0 or region[3]<=0:
  return {"verdict":"UNKNOWN","reason":"missing_or_invalid_claim_region"}
 var forbidden: Array=[]
 var xs: Array=[region[0],region[0]+region[2]]
 for seal in seals:
  var r: Array=seal.rect_pixels
  var box: Array=[r[0]-half_extents[0],r[1]-half_extents[1],r[2]+2*half_extents[0],r[3]+2*half_extents[1]]
  forbidden.append(box)
  for x in [box[0],box[0]+box[2]]:
   if x>region[0] and x<region[0]+region[2] and not x in xs:xs.append(x)
 xs.sort()
 var samples: Array=xs.duplicate()
 for i in range(xs.size()-1):samples.append((xs[i]+xs[i+1])/2.0)
 for x in samples:
  if gate!=null and not await gate.checkpoint():return {"verdict":"CANCELLED"}
  var intervals: Array=[]
  for box in forbidden:
   if box[0]<x and x<box[0]+box[2]:intervals.append([box[1],box[1]+box[3]])
  intervals.sort_custom(func(a,b):return a[0]<b[0] if a[0]!=b[0] else a[1]<b[1])
  var covered_to=region[1]
  var begun:=false
  for interval in intervals:
   if not begun:
    if interval[0]<region[1] and interval[1]>region[1]:
     begun=true;covered_to=interval[1]
   elif interval[0]<covered_to:
    covered_to=max(covered_to,interval[1])
   else:break
  if not begun or covered_to<=region[1]+region[3]:
   return {"verdict":"NOT_PROVEN_EXCLUDED","forbidden_rectangles":forbidden,"unexcluded_center_candidate":[x,region[1] if not begun else covered_to],"physical_validation":"UNKNOWN"}
 return {"verdict":"PROVEN_EXCLUDED_BY_SEALS","forbidden_rectangles":forbidden,"claim_region":region.duplicate(),"half_extents":half_extents.duplicate(),"scope":"strict AABB union covers the closed claim rectangle; no path/grounding certification"}
