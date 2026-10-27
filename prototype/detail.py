#!/usr/bin/env python3
"""Enlarged proof of unequal boundary-Block offsets on one real map seam."""
import json,html
from pathlib import Path
OUT=Path(__file__).parent/'output';M=json.loads((OUT/'map.json').read_text());ids={i['id']:i for i in M['instances']}
S=90;px=lambda x:120+(x-5)*S;py=lambda y:230+(y+4)*S
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1700" height="1150" viewBox="0 0 1700 1150"><style>text{font-family:"Noto Sans CJK SC",sans-serif}</style><rect width="1700" height="1150" fill="#f8fafb"/>']
def t(x,y,s,n=22,c='#263c4b',anchor='start',weight=400):svg.append(f'<text x="{x}" y="{y}" font-size="{n}" fill="{c}" text-anchor="{anchor}" font-weight="{weight}">{html.escape(str(s))}</text>')
t(55,60,'接缝放大：同一个侧边，可以有多个不同 Block 的 Port',33,weight=700)
t(55,110,'取自本图 C32 / C33 / C37。每个小格 = 1 Block，边界 Block 坐标从 0 开始。',21,'#607785')
for iid,fill,col in [('M02','#fcf0e9','#b87349'),('M08','#f3effa','#8c71a7'),('M06','#fcf0e9','#b87349'),('M07','#f3effa','#8c71a7')]:
 i=ids[iid];x,y=i['origin'];w,h=i['size_blocks'];xx,yy=px(x),py(y)
 svg.append(f'<rect x="{xx}" y="{yy}" width="{w*S}" height="{h*S}" fill="{fill}" stroke="{col}" stroke-width="2"/>')
 for bx in range(w):
  for by in range(h):
   svg.append(f'<rect x="{xx+bx*S}" y="{yy+by*S}" width="{S}" height="{S}" fill="none" stroke="{col}" stroke-opacity=".25"/>')
   if iid=='M06':t(xx+bx*S+45,yy+by*S+50,f'({bx},{by})',16,'#ad8c79','middle')
 t(xx+w*S/2,yy+h*S/2-15,iid+' · '+i['module_id'],19,col,'middle',700)
 t(xx+w*S/2,yy+h*S/2+12,f'{w}×{h}'+(' · MX' if i['mirror_x'] else ''),17,col,'middle')
 for pid,p in i['ports'].items():
  if p.get('connection') not in ('C32','C33','C37'):continue
  bx,by=p['edge_block'];sx,sy=px(p['world2'][0]/2),py(p['world2'][1]/2)
  svg.append(f'<rect x="{xx+bx*S+3}" y="{yy+by*S+3}" width="{S-6}" height="{S-6}" fill="#dcb69e" fill-opacity=".30"/><circle cx="{sx}" cy="{sy}" r="7" fill="#516b83"/>')
  if iid=='M06':
   label=pid+f' @ ({bx},{by})';offset=-12 if p['face']=='LEFT' else 12
   t(sx+offset,sy-14,label,17,'#304e66','end' if offset<0 else 'start',700)
for yy,cid,label in [(-3.5,'C32','M08.L ↔ M06.L'),(-.5,'C33','M02.R ↔ M06.L2'),(2.5,'C37','M06.R ↔ M07.L')]:
 sx=px(10 if cid=='C37' else 8);sy=py(yy)
 t(sx+12,sy+28,cid,17,'#516b83',weight=700)
t(960,250,'C33 的坐标计算',27,weight=700)
for y,line in [(305,'M02：origin = (5, −1)，尺寸 3×2'),(344,'R 在局部 Block (2, 0) 的右侧边中心'),(383,'局部 Port = (3, 0.5)'),(422,'世界 Port = (8, −0.5)'),(495,'M06：origin = (8, −4)，尺寸 2×7'),(534,'L2 在局部 Block (0, 3) 的左侧边中心'),(573,'局部 Port = (0, 3.5)'),(612,'世界 Port = (8, −0.5)')]:t(960,y,line,20)
t(960,686,'两端重合，但矩形顶边相差 3 Block。',22,'#b87349',weight=700)
t(960,735,'M06 同一左边还有 L：Block (0, 0)。',20)
t(960,774,'它与另一个 Module 的 Port 对接。',20)
t(55,1060,'左图深色格为接口所属 Block；圆点严格落在该格的外侧边中心。',22,'#607785')
t(55,1100,'Module 外形保持矩形；宽高和不同 Port 偏移共同产生错层拼接。',22,'#607785')
svg.append('</svg>');(OUT/'port-detail.svg').write_text(''.join(svg))
