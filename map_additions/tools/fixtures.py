"""Small hand-built logic fixtures, explicitly not real module/playability evidence."""
import json
from pathlib import Path
def fixture():
    def port(pid,face,xy):return dict(id=pid,face=face,local_position_pixels=xy,permission='INOUT',surface='ROCK')
    def route(rid,out):return dict(id=rid,from_port='in',to_port=out,required_reward_ids=[],required_abilities=[],author_path_pixels=[[192,0],[192,128],[192,206],[0 if out=='left' else 512,206]])
    items=[];contents={}
    for iid,role,origin,size,ports,routes in [
        ('S','start',[1,-1],[1,1],[port('out','BOTTOM',[64,128])],[]),
        ('J','traversal',[0,0],[4,3],[port('in','TOP',[192,0]),port('left','LEFT',[0,192]),port('right','RIGHT',[512,192])],[route('take-left','left'),route('take-right','right')]),
        ('C','target_reward',[-2,0],[2,3],[port('return','RIGHT',[256,192])],[]),
        ('B','boss',[4,0],[2,3],[port('in','LEFT',[0,192])],[])]:
        ref='content/'+iid+'.json';items.append(dict(id=iid,role=role,module_id='SYNTHETIC-'+iid,origin_blocks=origin,size_blocks=size,ports=ports,routes=routes,seals=[],connected_port_ids=[p['id'] for p in ports],content_ref=ref,transform={'mirror_x':False,'content_is_materialized':True}));contents[ref]={'platforms':[[0,224,size[0]*128,32]] if iid!='S' else [],'reward_sites':[{'id':'cache','position':[128,192],'region':[112,176,32,32]}] if iid=='C' else []}
    def n(nid,kind,iid,**extra):return dict(id=nid,kind=kind,instance_id=iid,**extra)
    nodes=[n('start','start','S'),n('s-out','port_depart','S',port_id='out'),n('j-in','port_arrive','J',port_id='in'),n('j-left','port_depart','J',port_id='left'),n('j-right','port_depart','J',port_id='right'),n('j-back','port_arrive','J',port_id='left'),n('c-in','port_arrive','C',port_id='return'),n('c-reward','reward','C',route_id='collect',reward_ids=['cache'],target=True),n('c-out','port_depart','C',port_id='return'),n('b-in','port_arrive','B',port_id='in'),n('boss','boss','B')]
    edges=[['start','s-out'],['s-out','j-in'],['j-in','j-left'],['j-in','j-right'],['j-left','c-in'],['c-in','c-reward'],['c-reward','c-out'],['c-out','j-back'],['j-back','j-right'],['j-right','b-in'],['b-in','boss']]
    m=dict(schema='mapgen/runtime-map/v2',map_id='synthetic-fork-v1',seed=123,coordinates={'block_size_pixels':128,'content_transform_applied':True},bounds_blocks=[-2,-1,6,3],instances=items,connections=[],graph=dict(nodes=nodes,edges=edges,main_paths=[['start','s-out','j-in','j-right','b-in','boss']]),inputs={'request':{'player':{'clearance_half_extents_pixels':[12.0,18.0]}}},anchors={'start_departure':{'instance_id':'S','port_id':'out'},'boss_arrival':{'instance_id':'B','port_id':'in'}})
    return dict(status='PASS',map=m,content_store=contents)
def shop_anchors():
    return [dict(id='test-shop',kind='shop',instance_id='B',node_id='b-in',position_pixels=[560,192])]
def write(out):
    out.mkdir(parents=True,exist_ok=False)
    (out/'fork.json').write_text(json.dumps(fixture(),indent=2)+'\n')
    (out/'shops.json').write_text(json.dumps(shop_anchors(),indent=2)+'\n')
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);write(p.parse_args().out)
