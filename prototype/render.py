#!/usr/bin/env python3
import json, html, math
from pathlib import Path
ROOT=Path(__file__).parent;OUT=ROOT/'output'
M=json.loads((OUT/'map.json').read_text());LIB=json.loads((OUT/'module_library.json').read_text())
S=56;B=M['summary']['bounds_blocks'];W=(B[2]-B[0]+2)*S+120;H=(B[3]-B[1]+2)*S+500
COL={'jump':('#f0f4fa','#527294'),'recoil':('#fcf0e9','#b87349'),'grapple':('#edf6ee','#528365'),
     'double_jump':('#f3effa','#8c71a7'),'shared':('#ecf2f5','#4b6e83'),'reward':('#fff2cd','#aa8027'),'air':('#fff0e2','#d47c36')}
SUR={'ROCK':'#536b83','ONE_WAY_PLATFORM':'#10978e','AIR':'#e27d31'}
PX=lambda x:60+(x-B[0]+1)*S;PY=lambda y:245+(y-B[1]+1)*S
parts=[]
def e(s):parts.append(s)
def text(x,y,s,size=17,c='#263c4b',a='start',weight=400,extra=''):
    e(f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" text-anchor="{a}" font-weight="{weight}" {extra}>{html.escape(str(s))}</text>')
def rect(x,y,w,h,fill,stroke='none',extra=''):
    e(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" {extra}/>')
e(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
e('''<defs><pattern id="grid" width="56" height="56" patternUnits="userSpaceOnUse"><path d="M56,0H0V56" fill="none" stroke="#d6e0e5" stroke-width=".8"/></pattern><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10Z" fill="context-stroke"/></marker></defs>''')
e('<style>text{font-family:"Noto Sans CJK SC",Arial,sans-serif}.module,.connection{cursor:pointer}.module.selected .body{stroke:#cf2c67;stroke-width:5}.dim{opacity:.15}.halo{paint-order:stroke;stroke:#fff;stroke-width:4;stroke-linejoin:round}.route{pointer-events:none}</style>')
rect(0,0,W,H,'#f8fafb')
text(60,58,'失序之钟 / MAP STUDY 02',21,'#6c808d',weight=600)
text(60,116,'边界 Block 定位 · 自由二维拼接',43,weight=700)
text(62,156,'每一格 = 1 Block；Port 位于选定边界 Block 的外侧边中心。Module 保持矩形，占用互不重叠。',21,'#607785')
sumry=M['summary'];text(W-65,62,f'SEED {M["seed"]}',22,a='end',weight=600)
text(W-65,105,f'{sumry["instances"]} 实例  /  {sumry["distinct_sizes"]} 种尺寸  /  {sumry["connections"]} 处连接',27,a='end',weight=600)
text(W-65,145,f'{sumry["used_templates"]} 模板  ·  {sumry["cycles"]} 个几何独立环  ·  6 处奖励',19,'#607785',a='end')
rect(60,183,W-120,57,'#eef2f5',extra='rx="8"')
for n,(key,label) in enumerate([('jump','跳跃'),('recoil','反冲'),('grapple','钩索'),('double_jump','纵向动作'),('reward','奖励')]):
    x=83+n*180;fill,stroke=COL[key];rect(x,201,18,18,fill,stroke);text(x+27,217,label,17)
text(1050,217,'Port 地貌：',17,weight=600)
for n,(key,label) in enumerate([('ROCK','岩体'),('ONE_WAY_PLATFORM','可穿平台'),('AIR','空中')]):
    x=1180+n*260;e(f'<circle cx="{x}" cy="209" r="6" fill="{SUR[key]}"/>');text(x+16,217,label,17)
text(2060,217,'↔ 双向   → 初始单向   × 封口',17)
text(W-80,217,'MX = 水平镜像；Port ID 不改名',16,'#607785',a='end')
rect(PX(B[0]-1),PY(B[1]-1),(B[2]-B[0]+2)*S,(B[3]-B[1]+2)*S,'#f8fafb','#dfe6eb')
for x in range(B[0]-1,B[2]+2):
    e(f'<path d="M{PX(x)},{PY(B[1]-1)}V{PY(B[3]+1)}" stroke="#e1e7eb" stroke-width=".65"/>')
    if x%4==0:text(PX(x),PY(B[1]-1)+20,x,12,'#8fa0ac','middle')
for y in range(B[1]-1,B[3]+2):
    e(f'<path d="M{PX(B[0]-1)},{PY(y)}H{PX(B[2]+1)}" stroke="#e1e7eb" stroke-width=".65"/>')
    if y%4==0:text(PX(B[0]-1)+6,PY(y)+5,y,12,'#8fa0ac')
ids={i['id']:i for i in M['instances']}
for i in M['instances']:
    x,y=i['origin'];w,h=i['size_blocks'];xx,yy=PX(x),PY(y);ww,hh=w*S,h*S
    fill,stroke=COL[i['lane']]
    if i['module_id']=='BOSS':fill,stroke='#fbecee','#b25664'
    e(f'<g class="module" data-id="{i["id"]}"><title>{i["id"]} · {i["module_id"]} · {w}×{h}</title>')
    rect(xx+.8,yy+.8,ww-1.6,hh-1.6,fill,stroke,extra='stroke-width="2" class="body"')
    # Grid is local to each module, aligned exactly to the global integer grid.
    for k in range(1,w):e(f'<path d="M{xx+k*S},{yy+1}V{yy+hh-1}" stroke="{stroke}" stroke-opacity=".14" stroke-width=".8"/>')
    for k in range(1,h):e(f'<path d="M{xx+1},{yy+k*S}H{xx+ww-1}" stroke="{stroke}" stroke-opacity=".14" stroke-width=".8"/>')
    # Highlight the ACTUAL boundary Block supporting each active port.
    for pid,p in i['ports'].items():
        u,v=[n/2 for n in p['local2']]
        bx=0 if p['face']=='LEFT' else w-1 if p['face']=='RIGHT' else int(u)
        by=0 if p['face']=='TOP' else h-1 if p['face']=='BOTTOM' else int(v)
        p['edge_block']=[bx,by];p['block_offset']=by if p['face'] in ('LEFT','RIGHT') else bx
        if p.get('connection'):rect(xx+bx*S+2,yy+by*S+2,S-4,S-4,SUR[p['surface']],extra='opacity=".12"')
    cx,cy=xx+ww/2,yy+hh/2
    if i['module_id']=='BOSS':
        text(cx,cy-15,'BOSS',39,stroke,'middle',700);text(cx,cy+23,f'{i["id"]} · 9×7',21,stroke,'middle')
    else:
        small=w<=2 or h<=2
        name='START' if i['module_id']=='START' else i['name']
        text(cx,cy-20,i['id'],20 if not small else 17,stroke,'middle',700,extra='class="halo"')
        text(cx,cy+2,i['module_id'],15,stroke,'middle',600,extra='class="halo"')
        text(cx,cy+22,f'{w}×{h}'+(' · MX' if i['mirror_x'] else ''),13,stroke,'middle',extra='class="halo"')
        if w>=4 and h>=4:text(cx,cy+45,name,15,stroke,'middle',extra='class="halo"')
        elif i['reward']:text(cx,cy+42,'奖励',13,stroke,'middle',extra='class="halo"')
    # Draw all ports; sealed ports sit INSIDE their owner's boundary.
    for pid,p in i['ports'].items():
        sx,sy=PX(p['world2'][0]/2),PY(p['world2'][1]/2)
        if p.get('closed'):
            dx,dy={'LEFT':(5,0),'RIGHT':(-5,0),'TOP':(0,5),'BOTTOM':(0,-5)}[p['face']]
            sx+=dx;sy+=dy;e(f'<path d="M{sx-3},{sy-3}L{sx+3},{sy+3}M{sx-3},{sy+3}L{sx+3},{sy-3}" stroke="#bd6373" stroke-width="1.8" opacity=".8"/>')
    e('</g>')
e('<g id="route-layer" class="route"></g>')
for c in M['connections']:
    xx,yy=PX(c['world2'][0]/2),PY(c['world2'][1]/2)
    iid,pid=c['a'].split('.');p=ids[iid]['ports'][pid];col=SUR[c['surface']]
    horizontal=p['face'] in ('LEFT','RIGHT')
    vx,vy={'RIGHT':(1,0),'LEFT':(-1,0),'TOP':(0,-1),'BOTTOM':(0,1)}[p['face']]
    if c['directions'][0][0]!=c['a']:vx=-vx;vy=-vy
    e(f'<g class="connection" data-connection="{c["id"]}"><title>{c["id"]}: {c["a"]} / {c["b"]}</title>')
    # Wide transparent hit target makes single points easy to click.
    e(f'<circle cx="{xx}" cy="{yy}" r="14" fill="transparent"/>')
    extra='marker-start="url(#arrow)"' if len(c['directions'])==2 else ''
    e(f'<path d="M{xx-vx*14},{yy-vy*14}L{xx+vx*14},{yy+vy*14}" stroke="{col}" stroke-width="2.1" marker-end="url(#arrow)" {extra}/><circle cx="{xx}" cy="{yy}" r="4" fill="{col}"/>')
    if horizontal:tx,ty=xx,yy+18
    else:tx,ty=xx+25,yy+4
    text(tx,ty,c['id'],10,col,'middle',700,extra='class="halo"')
    for endpoint in (c['a'],c['b']):
        ii,pp=endpoint.split('.');port=ids[ii]['ports'][pp]
        dx,dy={'LEFT':(18,-5),'RIGHT':(-18,-5),'TOP':(-5,19),'BOTTOM':(-5,-11)}[port['face']]
        text(xx+dx,yy+dy,pp,10,col,'middle',700,extra='class="halo"')
    e('</g>')
footer=PY(B[3]+1)+48
text(62,footer,'本次变化',23,weight=700)
text(220,footer,f'116 / 122 个已用 Port 端点偏离 Module 边中点；26 / 35 处左右接缝使相邻矩形上下错开。',20)
text(62,footer+38,'彩色浅格 = Port 所属边界 Block；小圆点 = 该 Block 的外侧边中心；相邻 Module 的两端 Port 在此精确重合。',19,'#607785')
text(62,footer+75,'矩形内：实例 ID / 模板 ID / Block 尺寸。具体边界 Block 索引与全部 Port 配对见交互版和接缝详图。',19,'#607785')
text(62,footer+113,'固定输入的纯程序生成；无预设水平路线带。占位 Route、封口与镜像尚未经过 Godot 物理认证。',18,'#946e45')
e('</svg>')
svg=''.join(parts);(OUT/'map.svg').write_text(svg)
# Edge-Block annotations are derived presentation data; persist for inspection.
(OUT/'map.json').write_text(json.dumps(M,ensure_ascii=False,indent=2))
(OUT/'poster.html').write_text('<!doctype html><meta charset="utf-8"><style>body{margin:0}</style>'+svg)

# Module atlas makes the library geometries and arbitrary block offsets explicit.
used=sorted(set(i['module_id'] for i in M['instances']))
atlas=[];cols=6;cellw=470;cellh=420;aw=cols*cellw+100;ah=150+math.ceil(len(used)/cols)*cellh
atlas.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{aw}" height="{ah}" viewBox="0 0 {aw} {ah}"><style>text{{font-family:"Noto Sans CJK SC",sans-serif}}</style><rect width="100%" height="100%" fill="#f8fafb"/><text x="50" y="60" font-size="34" fill="#263c4b">本图使用的 37 种模板 / 原向 Port 分布</text><text x="50" y="102" font-size="19" fill="#607785">所有标注为局部 Block 坐标。示例：R@b4 = 右边界第 4 号 Block 的外侧边中心（0 起算）。</text>')
for n,mid in enumerate(used):
    t=LIB[mid];w,h=t['size_blocks'];sc=min(36,300/max(w,h));xx=65+(n%cols)*cellw;yy=155+(n//cols)*cellh
    atlas.append(f'<text x="{xx}" y="{yy}" font-size="21" font-weight="700" fill="#263c4b">{mid} · {w}×{h} · {t["name"]}</text>')
    gx=xx+65;gy=yy+35
    atlas.append(f'<rect x="{gx}" y="{gy}" width="{w*sc}" height="{h*sc}" fill="#edf3f6" stroke="#627c8d" stroke-width="2"/>')
    for k in range(1,w):atlas.append(f'<path d="M{gx+k*sc},{gy}v{h*sc}" stroke="#d1dde4"/>')
    for k in range(1,h):atlas.append(f'<path d="M{gx},{gy+k*sc}h{w*sc}" stroke="#d1dde4"/>')
    for p in t['ports']:
        u,v=p['local2'];px=gx+u/2*sc;py=gy+v/2*sc;face=p['face'];b=(v//2 if face in ('LEFT','RIGHT') else u//2)
        dx,dy={'LEFT':(-7,4),'RIGHT':(7,4),'TOP':(0,-9),'BOTTOM':(0,21)}[face]
        anchor='end' if face=='LEFT' else 'start' if face=='RIGHT' else 'middle'
        atlas.append(f'<circle cx="{px}" cy="{py}" r="4" fill="{SUR[p["surface"]]}"/><text x="{px+dx}" y="{py+dy}" font-size="13" text-anchor="{anchor}" fill="{SUR[p["surface"]]}">{p["id"]}@b{b}</text>')
atlas.append('</svg>');(OUT/'module-atlas.svg').write_text(''.join(atlas))

# Reuse the tested standalone inspector mechanics, replace all old row-based assumptions.
source=(ROOT/'inspector-base.html').read_text()
start=source.index('<script>');script=source[start:]
begin=script.index('const DATA=');end=script.index('const svg=')
script=script[:begin]+'const DATA='+json.dumps(M,ensure_ascii=False)+';const LIB='+json.dumps(LIB,ensure_ascii=False)+';\n'+script[end:]
script=script.replace('3200,2290',f'{W},{H}')
script=script.replace('298+p.world2[0]/2*48',f'{60+(1-B[0])*S}+p.world2[0]/2*{S}')
script=script.replace('278+(p.world2[1]/2+12)*48',f'{245+(1-B[1])*S}+p.world2[1]/2*{S}')
script=script.replace('298+(i.origin[0]+i.size_blocks[0]/2)*48',f'{60+(1-B[0])*S}+(i.origin[0]+i.size_blocks[0]/2)*{S}')
script=script.replace('278+(i.origin[1]+12+i.size_blocks[1]/2)*48',f'{245+(1-B[1])*S}+(i.origin[1]+i.size_blocks[1]/2)*{S}')
script=script.replace('298+c.world2[0]/2*48',f'{60+(1-B[0])*S}+c.world2[0]/2*{S}')
script=script.replace('278+(c.world2[1]/2+12)*48',f'{245+(1-B[1])*S}+c.world2[1]/2*{S}')
hstart=script.index('function home()');hend=script.index('function download()',hstart)
script=script[:hstart]+'''function home(){info.innerHTML=`<h2>Block 边中点 / 二维自由生长</h2><p>49 个实例 · 37 种模板 · 18 种尺寸<br>61 处连接；岩体 / 可穿平台 / 空中三类均已接通。</p><p>116 / 122 个已用 Port 端点偏离 Module 边中点。35 处左右拼接有 26 处使矩形上下错开。无预设水平带。</p><h3>读图</h3><p>一格是 1 Block；彩色浅格是 Port 所属边界 Block。Port 小圆点落在该 Block 的外侧边中心。</p><p>点击矩形看每个 Port 的 <b>edge_block</b>、局部坐标、世界坐标和配对；点击 C 编号看接缝。滚轮缩放 / 拖动平移。</p><div class="note">Module 占用仍为矩形。动作、接缝、封口和镜像均未做 Godot 物理认证。</div><button class="download" onclick="download()">下载地图 JSON</button>`}
''' +script[hend:]
script=script.replace('方','方')
script=script.replace("${p.face}<br>${p.surface}<br>${p.permission}","${p.face}<br>${p.surface}<br>${p.permission}<br><b>Block (${p.edge_block.join(', ')})</b><br>local (${p.local2.map(v=>v/2).join(', ')})")
lane_start=script.index("document.querySelectorAll('[data-lane]').forEach")
lane_end=script.index("document.querySelector('#find').onclick",lane_start)
script=script[:lane_start]+'''document.querySelectorAll('[data-path]').forEach(b=>b.onclick=()=>{clear();document.querySelectorAll('[data-path]').forEach(x=>x.classList.remove('active'));b.classList.add('active');const k=Number(b.dataset.path);const seq=k<0?null:new Set(DATA.main_paths[k].map(n=>n.split('.')[0].split(':')[0]));document.querySelectorAll('.module').forEach(x=>x.classList.toggle('dim',seq&&!seq.has(x.dataset.id)));if(k<0)home();else info.innerHTML=`<h2>可达通路 ${k+1}</h2><p>${[...seq].join(' → ')}</p><p>这是实际有向图中查出的通路示例，不预设水平带，也不声明三种不同的玩法画像。</p>`});
''' +script[lane_end:]
script=script.replace("M01–M46 或 C01–C49",'M01–M49 或 C01–C61')
script=script.replace('map-seed-271027.json',f'map-seed-{M["seed"]}.json')
css=source[source.index('<style>'):source.index('</style>')+8]
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Map v2 · Block Port 检查器</title>'+css
page+='''<header><h1>Map v2 · Block Port 检查器</h1><button data-path="-1" class="active">全图</button><button data-path="0">通路 1</button><button data-path="1">通路 2</button><button data-path="2">通路 3</button><button id="fit">适应</button><button id="zin">＋</button><button id="zout">−</button><input id="search" aria-label="搜索实例或连接" placeholder="M12 / C21"><button id="find">定位</button></header><main><div id="viewport">'''+svg+'</div><aside id="info"></aside></main>'+script
(OUT/'map-inspector.html').write_text(page)
print(json.dumps(dict(width=W,height=H,inspector_kib=len(page.encode())//1024)))
