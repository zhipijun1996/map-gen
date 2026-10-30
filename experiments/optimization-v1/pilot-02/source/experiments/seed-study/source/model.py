"""Shared rectangle, doubled-coordinate Port, and explicit Route helpers."""
import copy
OPPOSITE={"LEFT":"RIGHT","RIGHT":"LEFT","TOP":"BOTTOM","BOTTOM":"TOP"}
ABILITIES={"jump","double_jump","recoil","grapple"}
LIB={}

def port(pid, face, xy, surface='ROCK', permission='INOUT'):
    return dict(id=pid,face=face,local2=xy,surface=surface,permission=permission,
                closure='prototype_local_solid_cap')

def template(mid, name, w, h, ports, pairs, ability='jump', difficulty=2, mirror=True, reward=False):
    routes=[]
    pp={p['id']:p for p in ports}
    for a,b in pairs:
        routes.append(dict(id=f'{a}>{b}',from_port=a,to_port=b,
            displacement=[(pp[b]['local2'][i]-pp[a]['local2'][i])/2 for i in (0,1)],
            required_abilities=[ability],action_tags=[ability],difficulty=difficulty,
            estimated_duration=12 if not reward else 20,
            resource_profile={'description':'占位设计标签，未做消耗模拟'},
            initial_conditions='initial',entry_exit_contract='prototype_support_or_downward_entry',
            validation={'status':'NOT_PHYSICALLY_CERTIFIED','evidence':None},
            content='reward' if reward else None))
    LIB[mid]=dict(id=mid,name=name,size_blocks=[w,h],ports=ports,routes=routes,
        allow_mirror_x=mirror,reward=reward,
        certification={'status':'PROTOTYPE_ONLY','routes':False,'seams':False,'closures':False,'mirror':False},
        closure_model='占位假设：局部实体封口仅禁用涉及该接口的 Route；其余 Route 保留。待 Godot 认证。')
    return mid

def bidir(pairs):
    return [(a,b) for x,y in pairs for a,b in [(x,y),(y,x)]]

def placed_ports(t,x,y,mirror):
    result={}
    for p0 in t['ports']:
        p=copy.deepcopy(p0)
        if mirror:
            p['local2'][0]=2*t['size_blocks'][0]-p['local2'][0]
            p['face']={'LEFT':'RIGHT','RIGHT':'LEFT'}.get(p['face'],p['face'])
        p['world2']=[2*x+p['local2'][0],2*y+p['local2'][1]]
        result[p['id']]=p
    return result

def overlap(a,b):
    x,y=a['origin'];w,h=a['size_blocks'];xx,yy=b['origin'];ww,hh=b['size_blocks']
    return x<xx+ww and xx<x+w and y<yy+hh and yy<y+h

def permitted(p, direction):
    return p['permission'] in (('OUTPUT','INOUT') if direction=='out' else ('INPUT','INOUT'))
