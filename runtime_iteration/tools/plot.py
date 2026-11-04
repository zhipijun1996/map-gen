"""Standalone summary plot; full cohort, no selected successes."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];out=ROOT/'runtime_iteration/comparisons';r=json.loads((out/'metrics.json').read_text());fig,axes=plt.subplots(1,2,figsize=(10,4))
labels=['Source modules','Port/Route types','Repeated neighbors'];keys=['mean_unique','mean_unique_port_route_topology','mean_repeated_neighbor_pairs'];x=list(range(3))
for offset,key,label in [(-.18,'old','0.4.1 default'),(.18,'new','0.4.2 varied-v1')]:axes[0].bar([i+offset for i in x],[r[key][k] for k in keys],width=.36,label=label)
axes[0].set_xticks(x,labels,rotation=12);axes[0].set_ylabel('Mean across all 40 seeds');axes[0].legend(fontsize=8)
a=[v['old']['unique'] for v in r['rows']];b=[v['new']['unique'] for v in r['rows']];axes[1].scatter(a,b,alpha=.7);lo=min(a+b)-1;hi=max(a+b)+1;axes[1].plot([lo,hi],[lo,hi],color='gray',ls='--');axes[1].set_xlabel('0.4.1 unique ordinary modules');axes[1].set_ylabel('0.4.2 varied-v1');axes[1].set_title('All 40 seeds; mirrors not new sources');fig.tight_layout()
for ext in ['png','svg']:fig.savefig(out/('metrics.'+ext),dpi=160)
p=out/'metrics.svg';p.write_text('\n'.join(s.rstrip() for s in p.read_text().splitlines())+'\n')
