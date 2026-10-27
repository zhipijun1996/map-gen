#!/usr/bin/env python3
"""Concrete 60-module AUTHORING PROPOSAL, never substituted into the measured library."""
import json,csv,math,html
from pathlib import Path
from collections import Counter
OUT=Path(__file__).parent/'output'

# Independent content tasks. Geometry/port patterns are interface families, not
# a claim that changing only a port or mirroring creates new authored content.
PLAN=[(2,2,['traverse']*3+['reward']), (3,2,['traverse']*3+['reward']),
 (2,3,['traverse']*3+['reward']), (4,3,['traverse']*7+['hub','reward']),
 (3,4,['traverse']*7+['hub','reward']), (5,3,['traverse']*3+['reward']),
 (6,3,['traverse']*3+['hub']), (3,5,['traverse']*2+['reward']),
 (3,6,['traverse']*2+['hub','reward']), (4,4,['hub']*2+['reward']),
 (5,4,['hub']*2+['open']), (6,4,['hub']+['open']*2),
 (6,5,['open']*2), (6,6,['open','start']), (8,6,['boss']), (10,6,['boss'])]
SUR={'ROCK':'#536b83','ONE_WAY_PLATFORM':'#10978e','AIR':'#e27d31'}
ROLE={'traverse':'穿越','hub':'枢纽','reward':'奖励','open':'开阔','start':'起点','boss':'Boss'}

def port(pid,face,k,w,h,surface=None,permission='INOUT'):
    surface=surface or ('ROCK' if face in ('LEFT','RIGHT') else 'ONE_WAY_PLATFORM')
    bx,by={'LEFT':(0,k),'RIGHT':(w-1,k),'TOP':(k,0),'BOTTOM':(k,h-1)}[face]
    local2={'LEFT':[0,2*k+1],'RIGHT':[2*w,2*k+1],'TOP':[2*k+1,0],'BOTTOM':[2*k+1,2*h]}[face]
    return dict(id=pid,face=face,edge_block=[bx,by],local2=local2,surface=surface,permission=permission,closure_zone='预留在所属边界 Block 内；须认证碰撞和 Route 兼容性')

def build():
    tasks=[];counts=Counter();air_ids=[]
    for w,h,roles in PLAN:
        for j,role in enumerate(roles):
            counts[role]+=1;n=counts[role];pp=[];pairs=[];flow='bidirectional';surface=None
            def P(pid,face,k,s=None,permission='INOUT'):return port(pid,face,k,w,h,s,permission)
            if role=='traverse':
                vertical=h>w
                if n in (10,11,20,21):
                    output=n in (10,20)
                    pp=[P('L','LEFT',h-1 if output else 0,'ROCK' if output else 'AIR','INPUT'),
                        P('R','RIGHT',0 if output else h-1,'AIR' if output else 'ROCK','OUTPUT')]
                    pairs=[('L','R')];flow='one_way_air_output' if output else 'one_way_air_input';air_ids.append(len(tasks)+1)
                elif vertical:
                    mode=j%5
                    if mode==0:pp=[P('U','TOP',w//2),P('D','BOTTOM',w//2)]
                    elif mode==1:pp=[P('U','TOP',0),P('D','BOTTOM',min(1,w-1))]
                    elif mode==2:pp=[P('U','TOP',w-1),P('D','BOTTOM',0)]
                    elif mode==3:pp=[P('U','TOP',0),P('R','RIGHT',h-2)]
                    else:pp=[P('L','LEFT',1),P('U','TOP',w-1),P('D','BOTTOM',0)]
                else:
                    mode=j%7
                    if mode==0:pp=[P('L','LEFT',h//2),P('R','RIGHT',h//2)]
                    elif mode==1:pp=[P('L','LEFT',h-1),P('R','RIGHT',max(0,h-2))]
                    elif mode==2:pp=[P('L','LEFT',0),P('R','RIGHT',min(1,h-1))]
                    elif mode==3:pp=[P('L','LEFT',h-1),P('R','RIGHT',0)]
                    elif mode==4:pp=[P('L','LEFT',h//2),P('U','TOP',w-1)]
                    elif mode==5:pp=[P('L','LEFT',h//2),P('D','BOTTOM',0)]
                    else:pp=[P('L','LEFT',0),P('R','RIGHT',h-1),P('U','TOP',w-2)]
                if len(pp)==2 and n%3==0 and not flow.startswith('one_way_air'):
                    used={p['id'] for p in pp}
                    for pid,face,k in [('U','TOP',max(0,w-2)),('D','BOTTOM',0),('L','LEFT',min(1,h-1)),('R','RIGHT',h-1)]:
                        if pid not in used:
                            pp.append(P(pid,face,k));break
                if not pairs:
                    pairs=[(pp[0]['id'],p['id']) for p in pp[1:]]
                    if len(pp)==3:pairs.append((pp[1]['id'],pp[2]['id']))
                    pairs=[p for a,b in pairs for p in ((a,b),(b,a))]
            elif role in ('hub','open'):
                pp=[P('L','LEFT',1),P('R','RIGHT',h-2),P('U','TOP',w-2),P('D','BOTTOM',1)]
                pairs=[('L','R'),('L','U'),('R','U'),('L','D'),('R','D')]
                if n%3==0:
                    pp.append(P('L2','LEFT',h-1));pairs.extend([('L2','R'),('L2','U')])
                if n%2==0:pairs.append(('U','D'))
                pairs=[p for a,b in pairs for p in ((a,b),(b,a))]
            elif role=='reward':
                if n<=5:
                    face=['LEFT','RIGHT','TOP','BOTTOM','LEFT'][n-1];k=(h if face in ('LEFT','RIGHT') else w)//2
                    pp=[P('P',face,k)];pairs=[('P','P')];flow='single_port_roundtrip'
                elif n<=7:
                    pp=[P('L','LEFT',h-1,permission='INPUT'),P('R','RIGHT',0,permission='OUTPUT')]
                    pairs=[('L','R')];flow='one_way_loop_return'
                else:
                    pp=[P('U','TOP',0,permission='INPUT'),P('R','RIGHT',h-1,permission='OUTPUT')]
                    pairs=[('U','R')];flow='cross_route_rejoin'
            elif role=='start':pp=[P('R','RIGHT',h//2,permission='OUTPUT')];flow='spawn_anchor'
            else:pp=[P('L','LEFT',h//2,permission='INPUT')];flow='boss_anchor'
            mechanic=['jump','recoil','grapple','double_jump'][(n-1)%4]
            if 'air' in flow:mechanic='recoil' if 'output' in flow else 'grapple'
            routes=[dict(from_port=a,to_port=b,required_abilities=[mechanic],validation='DESIGN_TARGET_NOT_CERTIFIED') for a,b in pairs]
            task=dict(id=f'P{len(tasks)+1:02}',size_blocks=[w,h],primary_role=role,mechanic_target=mechanic,
                      difficulty_target=1+(n-1)%4,ports=pp,route_targets=routes,return_mode=flow,
                      mirror_x='可选；必须独立验证方向性行为',status='AUTHORING_PROPOSAL_NOT_TESTED',
                      content_task=f'{ROLE[role]}独立内容任务 {n:02}：制作真实地形和动作差异，不能只靠镜像或 Port 子集计为新模板。')
            tasks.append(task)
    assert len(tasks)==60
    for t in tasks:
        w,h=t['size_blocks'];seen=set()
        for p in t['ports']:
            assert tuple(p['local2']) not in seen;seen.add(tuple(p['local2']))
            bx,by=p['edge_block'];assert 0<=bx<w and 0<=by<h
    return tasks

def draw(tasks):
    cols=6;cw=470;ch=410;W=cols*cw+100;H=190+math.ceil(len(tasks)/cols)*ch
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><style>text{{font-family:"Noto Sans CJK SC",sans-serif}}</style><rect width="100%" height="100%" fill="#f8fafb"/>']
    s.append('<text x="50" y="58" font-size="34" fill="#263c4b">推荐首批 60 个 Module 制作任务 / 尺寸与 Port 位置</text><text x="50" y="104" font-size="20" fill="#946e45">设计建议，未参与这次 Seed 测试，未做物理认证；数字 b 为边界 Block 索引，从 0 开始。</text><text x="50" y="145" font-size="19" fill="#607785">R / P / A = 岩体 / 可穿平台 / 空中。每个任务须有独立玩法内容；镜像和 Port 子集不增加基础模板数量。</text>')
    for n,t in enumerate(tasks):
        w,h=t['size_blocks'];sc=min(36,275/max(w,h));x=60+(n%cols)*cw;y=205+(n//cols)*ch;gx=x+60;gy=y+42
        s.append(f'<text x="{x}" y="{y}" font-size="20" font-weight="700" fill="#263c4b">{t["id"]} · {w}×{h} · {ROLE[t["primary_role"]]}</text>')
        s.append(f'<text x="{x}" y="{y+23}" font-size="13" fill="#607785">{t["mechanic_target"]} / 难度目标 {t["difficulty_target"]}</text><rect x="{gx}" y="{gy}" width="{w*sc}" height="{h*sc}" fill="#eef3f6" stroke="#677f8e" stroke-width="2"/>')
        for k in range(1,w):s.append(f'<path d="M{gx+k*sc},{gy}v{h*sc}" stroke="#d2dfe6"/>')
        for k in range(1,h):s.append(f'<path d="M{gx},{gy+k*sc}h{w*sc}" stroke="#d2dfe6"/>')
        for p in t['ports']:
            u,v=p['local2'];xx=gx+u/2*sc;yy=gy+v/2*sc;f=p['face'];b=p['edge_block'][1 if f in ('LEFT','RIGHT') else 0]
            dx,dy={'LEFT':(-7,4),'RIGHT':(7,4),'TOP':(0,-8),'BOTTOM':(0,21)}[f];a='end' if f=='LEFT' else 'start' if f=='RIGHT' else 'middle'
            typ={'ROCK':'R','ONE_WAY_PLATFORM':'P','AIR':'A'}[p['surface']];permission={'INPUT':'in','OUTPUT':'out','INOUT':'↔'}[p['permission']]
            s.append(f'<circle cx="{xx}" cy="{yy}" r="4" fill="{SUR[p["surface"]]}"/><text x="{xx+dx}" y="{yy+dy}" text-anchor="{a}" font-size="12" fill="{SUR[p["surface"]]}">{p["id"]}@b{b} {typ} {permission}</text>')
        compact=' / '.join(r['from_port']+'→'+r['to_port'] for r in t['route_targets'])
        if len(compact)>58:compact=compact[:55]+'…'
        s.append(f'<text x="{x}" y="{y+345}" font-size="12" fill="#607785">{html.escape(compact or t["return_mode"])}</text>')
    s.append('</svg>');(OUT/'recommended-60-atlas.svg').write_text(''.join(s))

if __name__=='__main__':
    tasks=build();roles=Counter(t['primary_role'] for t in tasks)
    (OUT/'recommended-60-library.json').write_text(json.dumps(dict(status='PROPOSED_OFFLINE_AUTHORING_TASKS_NOT_TESTED',base_template_count=60,role_counts=roles,
        shape_counts=[dict(size_blocks=[w,h],count=len(roles)) for w,h,roles in PLAN],
        guidance=['普通穿越优先 2–3 Port；枢纽 3–5；开阔空间 4–6；单口折返奖励必须声明 P→P。',
                  '预留同高、小错层、大错层和转角接口族；不要求所有 Port 偏离 Module 边中点。',
                  '同高/小错层/大错层的水平双侧接口初始供给目标约 30%/50%/20%，后续按失败签名调整。',
                  '同高=dy0；小错层=abs(dy)1；大错层=abs(dy)>=2；该配额是后续制作目标，不是本清单实测分布。',
                  'ROCK 仅左右；纵向优先 ONE_WAY_PLATFORM；AIR 初期只做成对、有明确出口的单向结构。',
                  '奖励必须在 instance.port 有向图中证明可达且有合法去向；U↔D 不存在时不能经同一 Module 自动转接。',
                  '先认证双向能力基础骨架，再添加反冲/钩索高难支路；水平镜像须保留 Port ID 与权限语义。'],modules=tasks),ensure_ascii=False,indent=2))
    with (OUT/'recommended-60-tasks.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['id','width','height','role','mechanic_target','difficulty_target','ports','route_targets','return_mode','status'])
        for t in tasks:w.writerow([t['id'],*t['size_blocks'],ROLE[t['primary_role']],t['mechanic_target'],t['difficulty_target'],
            '; '.join(f"{p['id']} {p['face']} block={p['edge_block']} {p['surface']} {p['permission']}" for p in t['ports']),
            '; '.join(r['from_port']+'->'+r['to_port'] for r in t['route_targets']),t['return_mode'],t['status']])
    draw(tasks);print('Recommended 60-task library:',dict(roles))
