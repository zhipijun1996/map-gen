"""Standalone descriptive figure with explicit successful-map denominators."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from branch_routes.tools.setup import ROOT

def main():
    out=ROOT/'structure_routes/comparison';data=json.loads((out/'metrics.json').read_text())['summaries'];names=['v4','v5','returns','merge'];labels=['0.5.1 / v4','0.6.0 / v5','0.7.0 / returns','0.7.0 / merge'];fig,(a,b)=plt.subplots(1,2,figsize=(12,4.5),layout='constrained');colors=['#9aacc2','#e38a31','#407bd2','#25966b']
    counts=[data[n]['all60']['statuses'].get('PASS',0) for n in names]
    a.bar(labels,counts,color=colors);a.set_ylim(0,65);a.set_ylabel('Maps passing own contract / 60');a.set_title('Same 40 regression + 20 predeclared new seeds')
    for x,value in enumerate(counts):a.text(x,value+1,str(value)+'/60',ha='center')
    bottom=[0.0]*4
    for kind,label,color in [('single_return','Single room','#9aacc2'),('multi_return','Multi-room return','#e38a31'),('core_merge','Other-core merge','#407bd2'),('forward_merge','Forward merge','#25966b')]:
        vals=[data[n]['all60']['branch_counts_all_successes'].get(kind,0)/(counts[i]*6) if counts[i] else 0 for i,n in enumerate(names)];b.bar(labels,vals,bottom=bottom,label=label,color=color);bottom=[x+y for x,y in zip(bottom,vals)]
    b.set_ylim(0,1);b.set_ylabel('Share of target reward branches');b.set_title('Successful maps only; denominators differ');b.legend(loc='upper center',bbox_to_anchor=(.5,-.18),ncol=2)
    for ax in [a,b]:ax.tick_params(axis='x',rotation=12)
    fig.suptitle('v6 adds hard branch-style requirements; not equivalent workloads / no physics validation',fontsize=11)
    fig.savefig(out/'success-and-reward-structure.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
