#!/usr/bin/env python3
import json,html,math,statistics
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).parent;OUT=ROOT/'output';R=json.loads((OUT/'results.json').read_text())
ROWS=R['results'];OK=[r for r in ROWS if r['status']=='PASS'];FAIL=[r for r in ROWS if r['status']!='PASS']
COL={'jump':('#edf3fa','#507497'),'recoil':('#fbf0e8','#ac6942'),'grapple':('#edf6ef','#4b8062'),
     'double_jump':('#f2eef9','#8b6fa5'),'shared':('#eaf1f6','#4b6e83'),'reward':('#fff1cb','#ad832d'),'air':('#ffeddf','#d77c33')}
SUR={'ROCK':'#536b83','ONE_WAY_PLATFORM':'#10978e','AIR':'#e27d31'}

def tx(x,y,text,size=18,c='#263c4b',anchor='start',weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" text-anchor="{anchor}" font-weight="{weight}">{html.escape(str(text))}</text>'
def bounds(items):return [min(i['origin'][0] for i in items),min(i['origin'][1] for i in items),max(i['origin'][0]+i['size_blocks'][0] for i in items),max(i['origin'][1]+i['size_blocks'][1] for i in items)]
def fragment(m,scale=40,details=True):
    B=bounds(m['instances']);ox=35-B[0]*scale;oy=35-B[1]*scale
    W=(B[2]-B[0])*scale+70;H=(B[3]-B[1])*scale+70;s=[]
    def X(x):return ox+x*scale
    def Y(y):return oy+y*scale
    s.append(f'<rect width="{W}" height="{H}" fill="#fbfcfd"/>')
    for i in m['instances']:
        x,y=i['origin'];w,h=i['size_blocks'];xx,yy=X(x),Y(y);fill,stroke=COL.get(i.get('lane','jump'),COL['jump'])
        if i['module_id']=='BOSS':fill,stroke='#fbecef','#b45467'
        s.append(f'<g class="module" data-id="{i["id"]}"><title>{i["id"]} / {i["module_id"]} / {w}×{h}</title><rect class="body" x="{xx}" y="{yy}" width="{w*scale}" height="{h*scale}" fill="{fill}" stroke="{stroke}" stroke-width="{max(1,scale/27)}"/>')
        if details:
            for k in range(1,w):s.append(f'<path d="M{xx+k*scale},{yy}v{h*scale}" stroke="{stroke}" stroke-opacity=".17" stroke-width=".6"/>')
            for k in range(1,h):s.append(f'<path d="M{xx},{yy+k*scale}h{w*scale}" stroke="{stroke}" stroke-opacity=".17" stroke-width=".6"/>')
        if details:
            for pid,p in i['ports'].items():
                sx,sy=X(p['world2'][0]/2),Y(p['world2'][1]/2);face=p['face'];u,v=p['local2']
                bx=0 if face=='LEFT' else w-1 if face=='RIGHT' else u//2
                by=0 if face=='TOP' else h-1 if face=='BOTTOM' else v//2
                if p.get('connection'):s.append(f'<rect x="{xx+bx*scale+1}" y="{yy+by*scale+1}" width="{scale-2}" height="{scale-2}" fill="{SUR[p["surface"]]}" opacity=".12"/>')
                else:
                    dx,dy={'LEFT':(4,0),'RIGHT':(-4,0),'TOP':(0,4),'BOTTOM':(0,-4)}[face];sx+=dx;sy+=dy
                    s.append(f'<path d="M{sx-2.5},{sy-2.5}l5,5M{sx-2.5},{sy+2.5}l5,-5" stroke="#bd6373" stroke-width="1.2"/>')
        cx=xx+w*scale/2;cy=yy+h*scale/2
        if details:
            if i['module_id'] in ('START','BOSS'):
                s.append(tx(cx,cy-4,i['module_id'],max(15,scale*.48),stroke,'middle',700));s.append(tx(cx,cy+19,i['id'],13,stroke,'middle'))
            else:
                s.append(tx(cx,cy-13,i['id'],max(13,scale*.36),stroke,'middle',700));s.append(tx(cx,cy+6,i['module_id'],max(11,scale*.28),stroke,'middle'))
                s.append(tx(cx,cy+23,f'{w}×{h}'+(' MX' if i['mirror_x'] else ''),max(10,scale*.25),stroke,'middle'))
        elif i['module_id'] in ('START','BOSS'):s.append(tx(cx,cy+4,'S' if i['module_id']=='START' else 'B',max(10,scale*.65),stroke,'middle',700))
        s.append('</g>')
    ids={i['id']:i for i in m['instances']}
    for c in m['connections']:
        x,y=[v/2 for v in c['world2']];xx,yy=X(x),Y(y);col=SUR[c['surface']];a,ap=c['a'].split('.');p=ids[a]['ports'][ap]
        vx,vy={'LEFT':(-1,0),'RIGHT':(1,0),'TOP':(0,-1),'BOTTOM':(0,1)}[p['face']]
        if c['directions'][0][0]!=c['a']:vx=-vx;vy=-vy
        ln=scale*.19
        s.append(f'<g class="connection" data-cid="{c["id"]}"><title>{c["id"]}: {c["a"]} / {c["b"]}</title><circle cx="{xx}" cy="{yy}" r="{max(5,scale*.16)}" fill="transparent"/><path d="M{xx-vx*ln},{yy-vy*ln}L{xx+vx*ln},{yy+vy*ln}" stroke="{col}" stroke-width="{max(1,scale*.035)}" marker-end="url(#arrow)" '+('marker-start="url(#arrow)"' if len(c['directions'])==2 else '')+f'/><circle cx="{xx}" cy="{yy}" r="{max(1.5,scale*.065)}" fill="{col}"/>')
        if details:
            horizontal=p['face'] in ('LEFT','RIGHT');s.append(tx(xx if horizontal else xx+20,yy+14 if horizontal else yy+4,c['id'],8,col,'middle',700))
            for endpoint in (c['a'],c['b']):
                ii,pid=endpoint.split('.');face=ids[ii]['ports'][pid]['face'];dx,dy={'LEFT':(14,-4),'RIGHT':(-14,-4),'TOP':(-4,15),'BOTTOM':(-4,-8)}[face]
                s.append(tx(xx+dx,yy+dy,pid,8,col,'middle',700))
        s.append('</g>')
    return ''.join(s),W,H,dict(scale=scale,ox=ox,oy=oy)

DEFS='<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10Z" fill="context-stroke"/></marker></defs>'
STYLE='<style>text{font-family:"Noto Sans CJK SC",Arial,sans-serif}.module,.connection{cursor:pointer}.selected .body{stroke:#ce2e65;stroke-width:4}</style>'
def wrap(inner,w,h):return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'+DEFS+STYLE+inner+'</svg>'

payload={}
for r in ROWS:
    seed=r['seed']
    if r['status']=='PASS':
        m=json.loads((OUT/f'seed-{seed}/map.json').read_text());frag,w,h,transform=fragment(m,48,True)
        svg=wrap(frag,w,h);(OUT/f'seed-{seed}/map.svg').write_text(svg)
        payload[str(seed)]=dict(row=r,map=m,svg=svg,width=w,height=h,transform=transform)
    else:payload[str(seed)]=dict(row=r)

selected=[r['seed'] for r in OK if r['seed']!=271028][:6]
# Fixed scale across all six panels: footprint differences remain comparable.
pw=1440;ph=1060;W=2*pw+120;H=3*ph+370
maxw=max(payload[str(seed)]['row']['bounding_box'][0] for seed in selected)
maxh=max(payload[str(seed)]['row']['bounding_box'][1] for seed in selected)
scale=min((pw-100)/maxw,(ph-170)/maxh)
parts=[f'<rect width="{W}" height="{H}" fill="#f3f6f8"/>',tx(60,64,'同一模块库 / 不同 Seed',40,weight=700),
 tx(60,110,'连续测试 271028–271047：16 / 20 通过；4 个失败 Seed 保留在完整结果中。无重试，无替换。',23,c='#607785'),
 tx(60,148,'下方为除原图外最先通过的 6 个 Seed，使用相同 Block 绘制比例。S = Start，B = Boss，金色 = 奖励。',20,c='#607785')]
for n,seed in enumerate(selected):
    p=payload[str(seed)];r=p['row'];x=60+(n%2)*pw;y=190+(n//2)*ph
    parts.append(f'<rect x="{x}" y="{y}" width="{pw-20}" height="{ph-22}" rx="12" fill="white" stroke="#dfe6eb"/>')
    parts.append(tx(x+25,y+42,f'SEED {seed}',28,weight=700));parts.append(tx(x+25,y+78,f'{r["instances"]} 实例 / {r["connections"]} 连接 / {r["distinct_sizes"]} 尺寸 / 包围框 {r["bounding_box"][0]}×{r["bounding_box"][1]} Block',19,c='#607785'))
    frag,w,h,_=fragment(p['map'],scale,False);dx=x+(pw-20-w)/2;dy=y+110+(ph-150-h)/2
    parts.append(f'<g transform="translate({dx},{dy})">{frag}</g>')
parts.append(tx(60,H-75,'失败 Seed：271031、271039、271043、271044；其中 1 个奖励不可达，3 个奖励返回后无法抵达 Boss。',21,c='#a45563'))
parts.append(tx(60,H-34,'合格仅指矩形、接口和静态通行图检查；未做 Godot 物理认证。',19,c='#946e45'))
(OUT/'six-seeds.svg').write_text(wrap(''.join(parts),W,H))

# Complete 20-seed board includes rejected candidates as explicit rejected slots.
pw=760;ph=590;W=4*pw+100;H=5*ph+230;parts=[f'<rect width="{W}" height="{H}" fill="#f3f6f8"/>',tx(45,58,'全部 20 个 Seed / 首次生成结果',36,weight=700),tx(45,100,'同一 52 模板库、同一能力集合和生成配置；16 合格、4 拒绝，未重试。',21,c='#607785')]
maxw=max(r['bounding_box'][0] for r in OK);maxh=max(r['bounding_box'][1] for r in OK);scale=min((pw-100)/maxw,(ph-130)/maxh)
for n,r in enumerate(ROWS):
    x=45+n%4*pw;y=140+n//4*ph;passed=r['status']=='PASS'
    parts.append(f'<rect x="{x}" y="{y}" width="{pw-20}" height="{ph-20}" rx="8" fill="{ "white" if passed else "#fceff1"}" stroke="#dfe6eb"/>')
    parts.append(tx(x+20,y+34,f'{r["seed"]} · {"PASS" if passed else "REJECT"}',23,c='#263c4b' if passed else '#ab5264',weight=700))
    if passed:
        frag,w,h,_=fragment(payload[str(r['seed'])]['map'],scale,False);parts.append(f'<g transform="translate({x+(pw-20-w)/2},{y+70+(ph-110-h)/2})">{frag}</g>')
    else:
        parts.append(tx(x+35,y+200,'奖励可达 / 回程检查失败',25,c='#ab5264',weight=600));parts.append(tx(x+35,y+245,'候选未作为有效地图输出',20,c='#ab5264'))
(OUT/'all-20-seeds.svg').write_text(wrap(''.join(parts),W,H))

# Self-contained technical inspector for every accepted seed and failure record.
options=''.join(f'<option value="{r["seed"]}">{r["seed"]} · {r["status"]}</option>' for r in ROWS)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>多 Seed 地图检查</title><style>*{box-sizing:border-box}body{margin:0;font:14px system-ui,"Noto Sans CJK SC",sans-serif;background:#f1f5f8;color:#263c4b}header{height:66px;background:white;border-bottom:1px solid #dce4ea;display:flex;align-items:center;gap:12px;padding:0 20px}h1{font-size:19px;margin-right:15px}button,select,input{padding:8px 10px;font:inherit;border:1px solid #cad6df;border-radius:6px;background:white}button{cursor:pointer}main{height:calc(100vh - 66px);display:grid;grid-template-columns:minmax(0,1fr) 390px}#viewport{overflow:hidden;touch-action:none}#viewport>svg{width:100%;height:100%;display:block}aside{overflow:auto;padding:24px;background:white;border-left:1px solid #dce4ea}p{line-height:1.75}table{width:100%;border-collapse:collapse;font-size:12px}td,th{text-align:left;border-bottom:1px solid #e9eef2;padding:8px 3px}h2{font-size:23px}h3{font-size:15px;margin-top:24px}.note{padding:12px;background:#fff1dd;border-radius:6px;font-size:12px;line-height:1.7}.reject{padding:14px;background:#fce9ed;color:#a34f62;line-height:1.8}code{font-size:12px}.route{pointer-events:none}#search{width:130px}</style><header><h1>多 Seed 地图检查</h1><select id="seed">__OPTIONS__</select><button id="fit">全图</button><button id="zin">＋</button><button id="zout">−</button><input id="search" placeholder="M12 / C33" aria-label="搜索实例或接缝"><button id="find">定位</button><span>首次合格 16 / 20</span></header><main><div id="viewport"></div><aside id="info"></aside></main><script>
const DATA=__PAYLOAD__;let cur,svg,box,drag=null,moved=false;const viewport=document.querySelector('#viewport'),info=document.querySelector('#info');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function setbox(){if(svg)svg.setAttribute('viewBox',box.join(' '))}function fit(){if(!svg)return;box=[0,0,cur.width,cur.height];setbox()}function zoom(f,cx=box[0]+box[2]/2,cy=box[1]+box[3]/2){if(box[2]*f<200||box[2]*f>15000)return;box=[cx-(cx-box[0])*f,cy-(cy-box[1])*f,box[2]*f,box[3]*f];setbox()}
function clear(){if(svg){svg.querySelectorAll('.selected').forEach(x=>x.classList.remove('selected'));svg.querySelector('#routes')?.remove()}}
function overview(){let r=cur.row;info.innerHTML=`<h2>Seed ${r.seed}</h2><p>${r.instances} 实例 / ${r.used_templates} 已用模板<br>${r.connections} 接缝 / ${r.distinct_sizes} 尺寸<br>6 奖励 / ${r.main_paths} 条通路示例<br>包围框 ${r.bounding_box.join('×')} Block<br>左右接口错层 ${(100*r.horizontal_offset_ratio).toFixed(1)}%<br>未用 Port ${(100*r.closure_ratio).toFixed(1)}%</p><p>点击矩形查看 Module / Port / Route；点击 C 编号查看接缝。滚轮缩放、拖动平移。</p><div class="note">本页全部 Seed 共用相同 52 模板库和生成参数。失败 Seed 保留在下拉菜单中。通过表示几何与静态图成立，未做 Godot 物理认证。</div>`}
function show(i){clear();svg.querySelector(`[data-id="${i.id}"]`)?.classList.add('selected');let rows=Object.entries(i.ports).map(([pid,p])=>{let k=p.face==='LEFT'||p.face==='RIGHT'?p.local2[1]/2-.5:p.local2[0]/2-.5;let c=cur.map.connections.find(c=>c.id===p.connection);let self=i.id+'.'+pid;return `<tr><td><b>${pid}</b><br>${p.face}</td><td>b${k}<br>local (${p.local2.map(v=>v/2).join(', ')})<br>${p.surface}<br>${p.permission}</td><td>${p.connection||'封口'}<br>${c?(c.a===self?c.b:c.a):''}<br>world (${p.world2.map(v=>v/2).join(', ')})</td></tr>`}).join('');info.innerHTML=`<h2>${i.id} · ${i.module_id}</h2><p>${i.size_blocks.join('×')} Block / origin (${i.origin.join(', ')})<br>mirror_x=${i.mirror_x}</p><h3>Port 与边界 Block 索引</h3><table><tr><th>ID</th><th>局部 / 类型</th><th>连接 / 世界坐标</th></tr>${rows}</table><h3>全部有效内部 Route</h3>${i.actual_routes.map(r=>`<p><code>${r.from_port} → ${i.reward?'奖励 → ':''}${r.to_port}</code><br>${r.required_abilities.join(', ')}</p>`).join('')||'<p>专用起点 / Boss 锚点</p>'}<div class="note">Route、接缝、封口和镜像均为未认证占位契约。未声明的 Port 对不会自动互通。</div>`;let g=document.createElementNS('http://www.w3.org/2000/svg','g');g.id='routes';g.classList.add('route');let {scale,ox,oy}=cur.transform;for(let r of i.actual_routes){let a=i.ports[r.from_port].world2,b=i.ports[r.to_port].world2,cx=ox+(i.origin[0]+i.size_blocks[0]/2)*scale,cy=oy+(i.origin[1]+i.size_blocks[1]/2)*scale;let p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d',`M${ox+a[0]/2*scale},${oy+a[1]/2*scale}Q${cx},${cy} ${ox+b[0]/2*scale},${oy+b[1]/2*scale}`);p.setAttribute('stroke','#c62d67');p.setAttribute('stroke-width','2');p.setAttribute('stroke-opacity','.55');p.setAttribute('fill','none');p.setAttribute('marker-end','url(#arrow)');g.appendChild(p)}svg.appendChild(g)}
function connection(c){clear();info.innerHTML=`<h2>${c.id}</h2><p><b>${c.a} / ${c.b}</b><br>${c.surface}<br>世界坐标 (${c.world2.map(v=>v/2).join(', ')})</p><h3>初始方向</h3>${c.directions.map(([a,b])=>`<p>${a} → ${b}</p>`).join('')}<div class="note">坐标重合、法线相反、地貌同类和初始权限已检查。物理接缝未认证。</div>`;[c.a,c.b].forEach(x=>svg.querySelector(`[data-id="${x.split('.')[0]}"]`)?.classList.add('selected'))}
function load(){cur=DATA[document.querySelector('#seed').value];if(cur.row.status!=='PASS'){svg=null;viewport.innerHTML='<div style="padding:70px;color:#a34f62"><h2>该 Seed 的候选被拒绝</h2><p>完整静态检查未通过，没有输出有效地图。</p></div>';info.innerHTML=`<h2>Seed ${cur.row.seed} · REJECT</h2><div class="reject">奖励可达 / 回程检查失败。原始失败记录已保留；无重试、无替换。</div>`;return}viewport.innerHTML=cur.svg;svg=viewport.querySelector('svg');fit();overview();svg.addEventListener('wheel',e=>{e.preventDefault();let p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());zoom(e.deltaY>0?1.12:.89,p.x,p.y)},{passive:false});svg.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,box:[...box]};moved=false});svg.addEventListener('pointermove',e=>{if(!drag)return;let ct=svg.getScreenCTM(),dx=(e.clientX-drag.x)/ct.a,dy=(e.clientY-drag.y)/ct.d;if(Math.abs(dx)+Math.abs(dy)>4){moved=true;svg.setPointerCapture(e.pointerId)}box=[drag.box[0]-dx,drag.box[1]-dy,box[2],box[3]];setbox()});svg.addEventListener('pointerup',()=>drag=null);svg.addEventListener('click',e=>{if(moved)return;let c=e.target.closest('[data-cid]');if(c){connection(cur.map.connections.find(x=>x.id===c.dataset.cid));return}let i=e.target.closest('[data-id]');if(i)show(cur.map.instances.find(x=>x.id===i.dataset.id))})}
document.querySelector('#seed').onchange=load;document.querySelector('#fit').onclick=()=>{fit();if(svg){clear();overview()}};document.querySelector('#zin').onclick=()=>svg&&zoom(.75);document.querySelector('#zout').onclick=()=>svg&&zoom(1.3);document.querySelector('#find').onclick=()=>{if(!svg)return;let s=document.querySelector('#search').value.trim().toUpperCase(),i=cur.map.instances.find(x=>x.id===s),c=cur.map.connections.find(x=>x.id===s);if(!i&&!c){info.innerHTML='<p>未找到该编号。</p>';return}let {ox,oy,scale}=cur.transform,x,y;if(i){show(i);x=ox+(i.origin[0]+i.size_blocks[0]/2)*scale;y=oy+(i.origin[1]+i.size_blocks[1]/2)*scale}else{connection(c);x=ox+c.world2[0]/2*scale;y=oy+c.world2[1]/2*scale}box=[x-420,y-310,840,620];setbox()};document.querySelector('#search').addEventListener('keydown',e=>{if(e.key==='Enter')document.querySelector('#find').click()});load();</script></html>'''
page=page.replace('__OPTIONS__',options).replace('__PAYLOAD__',json.dumps(payload,ensure_ascii=False))
(OUT/'seed-inspector.html').write_text(page)

summary=dict(tested=len(ROWS),passed=len(OK),failed=len(FAIL),pass_rate=len(OK)/len(ROWS),seeds=[r['seed'] for r in ROWS],
             illustrated_seeds=selected,illustration_selection='除原 Seed 外，按测试顺序最先通过的六个 Seed',
             generation_seconds=dict(min=min(r['seconds'] for r in OK),max=max(r['seconds'] for r in OK),mean=statistics.mean(r['seconds'] for r in OK)),
             instances_range=[min(r['instances'] for r in OK),max(r['instances'] for r in OK)],
             air_success_count=sum('AIR' in r['surfaces'] for r in OK),
             closure_ratio_mean=statistics.mean(r['closure_ratio'] for r in OK),
             horizontal_offset_ratio_mean=statistics.mean(r['horizontal_offset_ratio'] for r in OK),
             all_accepted_instances_reachable=all(r['reachable_instances']==r['instances'] for r in OK),
             failure_diagnosis=json.loads((OUT/'failure-diagnosis.json').read_text()))
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(dict(selected=selected,comparison_size=[2*1440+120,3*1060+370],inspector_mib=round(len(page.encode())/1048576,2)),ensure_ascii=False))
