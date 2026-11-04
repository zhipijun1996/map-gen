"""Final evidence joins. No oracle rewrite or seed filtering."""
import copy,gzip,hashlib,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'validation/runtime-iteration-20261104'
def read(p):
 if not p.exists():p=p.with_suffix(p.suffix+'.gz')
 raw=p.read_bytes();return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
def norm(r,identity=False):
 r=copy.deepcopy(r);r['metrics'].pop('generation_seconds',None)
 if identity:
  r.pop('request_fingerprint');r['diagnostics'].pop('implementation',None)
  if r['map']:r['map'].pop('map_id');r['map']['generator'].pop('implementation');r['map']['generator'].pop('request_fingerprint')
 return r
def active(row):return sum(p['total_usec'] for p in row['profile']['phases'].values())/1e6
def dist(rows):
 values=sorted(active(r) for r in rows if r['status']=='PASS' and r['case'].startswith(('validation-','calibration-','unseen-')))
 return dict(count=len(values),mean=statistics.mean(values),p50=statistics.median(values),p95=values[int((len(values)-1)*.95)],max=max(values))
core={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'godot_runtime/addons/mapgen').glob('*.gd')}
default=read(E/'default/summary.json');varied=read(E/'varied-v3/summary.json');ub=read(E/'unseen-baseline/summary.json');uv=read(E/'unseen-varied/summary.json');checks=read(E/'checks/checks.json');reach=read(E/'reachability.json');live=read(E/'live-controller/summary.json');diversity=read(ROOT/'runtime_iteration/comparisons/metrics.json')
for run in [default,varied,uv]:assert run['status']=='PASS' and run['source_sha256']==core
assert checks['status']==reach['status']==live['status']==diversity['status']=='PASS' and len(core)==19
base_cfg=read(ROOT/'profiles/stable-v3-reward-space.json');new_cfg=read(ROOT/'profiles/stable-v3-varied-v1.json');expected=copy.deepcopy(base_cfg);expected['scoring']['repeat_module']=8;assert new_cfg==expected
native={n:read(E/(n+'.json')) for n in ['native-041-final','native-042-default','native-042-varied']}
web={n:read(E/n/'report.json.gz') for n in ['web-041','web-042-default','web-042-varied']}
comparisons=[]
for platform,runs,labels in [('native',native,['native-041-final','native-042-default','native-042-varied']),('threaded_web',web,['web-041','web-042-default','web-042-varied'])]:
 for i in [1,2]:
  before,after,alternate=[runs[k]['records'][i] for k in labels]
  assert norm(before['result'],True)==norm(after['result'],True)
  assert norm(after['result'])==norm(read(E/'default'/('validation-'+str(int(after['seed']))+'.json.gz'))['result'])
  assert norm(alternate['result'])==norm(read(E/'varied-v3'/('validation-'+str(int(alternate['seed']))+'.json.gz'))['result'])
  comparisons.append(dict(platform=platform,seed=before['seed'],old_wall_usec=before['wall_usec'],default_wall_usec=after['wall_usec'],varied_wall_usec=alternate['wall_usec'],old_active_usec=before['advance_cpu_usec'],default_active_usec=after['advance_cpu_usec'],varied_active_usec=alternate['advance_cpu_usec'],default_full_result_equal=True,varied_matches_native_frozen=True))
cancels=[]
for name in ['web-cancel-preload','web-cancel-varied']:
 r=read(E/name/'report.json.gz')['records'][-1];c=r['cancel'];assert c['trusted'];v=r.get('result');assert (v['status']=='CANCELLED' and v['map'] is None and v['content_store']=={}) if v else r['status']=='CANCELLED'
 cancels.append(dict(case=name,input_to_done_ms=c['input_to_done_ms'],queue_ms=c['handler_ms']-c['intent_ms'],handler_to_observed_ms=c['observed_ms']-c['handler_ms'],sdk_cancel_ms=c['finished_ms']-c['observed_ms']))
failure=read(E/'web-failure-varied/report.json.gz')['records'][-1]['result'];assert failure['status']=='SEARCH_EXHAUSTED' and failure['map'] is None and failure['content_store']=={}
assert norm(failure)==norm(read(E/'varied-v3/failure.json.gz')['result'])
paired=[]
for before,after in zip(ub['records'],uv['records']):
 assert before['case']==after['case'];paired.append(dict(case=before['case'],old_status=before['status'],new_status=after['status'],old_active=active(before),new_active=active(after),ratio=active(after)/active(before)))
report={'status':'PASS','baseline_main':'b15c32e045347e0fcf282d541ea3eaa4661f0835','baseline_archive_sha256':'f5c84e5e51dff01d16429783b957c0d5214056b9d2fea47a830baac12ecedb4e','algorithm':'stable-v3-reward-space','implementation':'mapgen/gdscript-candidate-0.4.2','tested_source_sha256':core,'default_unchanged_cases':47,'varied_regression_cases':47,'additional_unseen_cases':20,'controller_replay':live,'default_distribution':dist(default['records']),'varied_distribution':dist(varied['records']),'unseen_old_distribution':dist(ub['records']),'unseen_varied_distribution':dist(uv['records']),'unseen_pairs':paired,'timing':comparisons,'diversity':diversity,'checks':checks,'reachability':reach,'cancel':cancels,'web_real_failure_empty':True,'warm_web':read(E/'web-warm/summary.json'),'rejected_profiles':[{'profile':'variety-pilot-v1.json','passed':38,'cases':40,'failed':['calibration-271038','validation-930009']},{'profile':'variety-pilot-v2.json','passed':39,'cases':40,'failed':['validation-930018']}],'scope':'candidate; actual game not modified or executed; native/Web scopes separate; no physical or subjective approval'}
(E/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines=['# 0.4.2 实验与交付报告','','原包0.4.1保持原样，实际基线main为b15c32e045347e0fcf282d541ea3eaa4661f0835。默认配置不改；可选varied-v1只把重复模块评分惩罚5改为8。算法、Schema版本、模块包1.1.0、90秒/500000预算、32/6/3目标、最大长短边比3和封口32像素均不改。','','## 结果与确定性','','原默认47例完整对照通过（含原40 seed、成功/真实失败、17/128批次与三阶段取消）；仅排除实现身份/指纹/map_id和generation_seconds。所有布局、完整内容、Route方向、镜像、封口、奖励、随机状态及搜索计数一致。8001项有向图正反可达等价/整数key检查通过；原生Job还覆盖1/17/128/4096批次、结果快照、库复用和取消隔离。','','选定varied-v1的原40 seed全部生成PASS，连同真实失败、三种批次和三个取消共47例通过。原40是用于回归/选配置的已知集合，不能声称未见验证；另预先固定930021–930040共20个额外seed，在选定配置后只执行一次，旧0.4.1和新配置均20/20 PASS，没有reroll/筛除。两组通过相同独立源内容/实际有向图/封口/全部普通及目标奖励检查。','','读取主游戏main 48cddb6的实际历史controller输入（原capture源a0a9006）：只有jump/shot_recoil，净空12.0/18.0。保留JSON浮点类型，从原0.4.1准确复现指纹214cdc2359984f665e7b4a2609f3f055df155e10c13cd46b57dd983e13b23b74；新默认完整结果只差身份/耗时，可选新配置也生成并独立审计通过。此为算法重放，没有重新执行主游戏/SceneTree/装载/物理，也没有授予额外能力。','','## 速度实测','','同一锁定Godot 4.7.2.stable.custom_build.gunman_sd1.ed1daf0bf，二进制SHA eeaec2b65dc3234168be1e1cbcc89731514bbb78dfb2c1b502920c50830a0638。Web为threaded release/Compatibility/软件Chromium/COOP+COEP，默认advance(1)、每tick至多128单位、软8ms。所有表格是独立数据宿主，不是正式游戏；active为advance调用内单调钟之和，不等于OS线程CPU计数。墙钟差额包含让帧/渲染/宿主记账。','','| 环境 / seed | 0.4.1默认墙钟s | 0.4.2默认s | 0.4.2 varied-v1 s |','| --- | ---: | ---: | ---: |']
for r in comparisons:lines.append(f"| {r['platform']} / {int(r['seed'])} | {r['old_wall_usec']/1e6:.3f} | {r['default_wall_usec']/1e6:.3f} | {r['varied_wall_usec']/1e6:.3f} |")
lines+=['','默认与旧版同结果，是纯计算优化的对照；varied-v1产生不同地图，不能把其全部速度差异归为计算优化。不同seed不保证都变快：额外20个seed中新配置较慢的有 '+str(sum(r['ratio']>1 for r in paired))+' 个，最差相对比为 '+f"{max(r['ratio'] for r in paired):.2f}"+' 倍。原生整批 active 统计（秒）如下：','','| 批次 | mean | p50 | p95 | max |','| --- | ---: | ---: | ---: | ---: |']
for key,label in [('default_distribution','本轮默认40'),('varied_distribution','本轮新配置40'),('unseen_old_distribution','额外20旧0.4.1'),('unseen_varied_distribution','额外20新配置')]:
 d=report[key];lines.append('| '+label+' | '+' | '.join(f'{d[k]:.3f}' for k in ['mean','p50','p95','max'])+' |')
lines+=['','0.4.2没有改变预载实现，不能宣称预载提速。两版默认首轮Web预载分别 '+f"{web['web-041']['records'][0]['wall_usec']/1e6:.3f}"+' / '+f"{web['web-042-default']['records'][0]['wall_usec']/1e6:.3f}"+' 秒；新版本另一次冷/热完整预载为 '+', '.join(f"{r['wall_usec']/1e6:.3f}" for r in report['warm_web']['records'])+' 秒，均重新核验ZIP和657成员。已验证library可复用，两seed测试使用同一库。结果复制/序列化与每阶段max/p50/p95/p99另在原始native/Web报告。首次varied Web轮与对照页浏览器启动有重叠，保留为web-042-varied-first；最终表只用其后的独立运行，全部原件保留。','','## 重复模式与地图观感','','[40张同seed交互对照](comparisons/index.html)，可切换模块布局与静态平台/封口/领奖矩形。完整原始result/content_store独立保留，视图没有作为生成输入。颜色依源ID稳定，镜像不计新模块；额外按去名称/合并镜像的平台几何和Port-Route结构统计。','','| 40图均值 | 原默认 | 可选配置 |','| --- | ---: | ---: |']
for key,label in [('mean_unique','普通源模块种类'),('mean_unique_platform_geometry','平台几何类型'),('mean_unique_port_route_topology','源Port/Route结构类型'),('mean_repeat_instances','重复普通实例'),('mean_repeated_neighbor_pairs','重复邻接对'),('mean_neighbor_pair_jaccard','跨seed邻接集合相似度'),('mean_normalized_occupancy_jaccard','归一化占用相似度')]:lines.append(f"| {label} | {diversity['old'][key]:.3f} | {diversity['new'][key]:.3f} |")
lines+=['','本轮主要改善局部模块及邻接重复；宏观占用相似度0.332→0.337没有改善，旧/新精确重复布局均为0。不能用不同颜色、镜像或模块名称假装宏观探索结构/动作体验已经更多，也未验证玩家主观重复感。主游戏后续仍需真实内容装载和试玩。','','## 热点和未采用试验','','原0.4.1 native诊断显示930001 graph self约2.20s、growth_options约1.35s、reachable约0.90s。采用：整数pair key代替分组/匹配中的临时字符串，权限判断去临时数组；同一目标Boss的多次正向BFS改为复用一次反向可达集。原有边和Route不反向，反向图只做内部等价查询；缓存仍是独立job的既有64图有界缓存。没有新增全局可变缓存、查询预存地图、Python运行时或主游戏依赖。','','放置/前缀大缓存收益很小、几何计划缓存更慢，未采用。patch和两seed的完整结果/耗时保留。评分第一组14/8/14导致38/40（271038、930009失败）；第二组只改repeat=10导致39/40（930018失败），全部原请求、配置、结果及失败原样保留。最终选择repeat=8，无seed分支、无隐式回退到旧配置、无预算放宽。样本不是所有seed稳定性的证明。','','## 取消、检查与剩余限制','','| 实际trusted Escape | 输入到完成ms | 事件队列ms | handler到观察ms | cancel内ms |','| --- | ---: | ---: | ---: | ---: |']
for r in cancels:lines.append('| '+r['case']+' | '+' | '.join(f'{r[k]:.3f}' for k in ['input_to_done_ms','queue_ms','handler_to_observed_ms','sdk_cancel_ms'])+' |')
lines+=['','这些包含输入排队，不是仅量cancel函数。真实Web jump-only失败与原生同结果且map=null/content_store={}。原生预算1在第2次拒绝、极短墙钟在原256间隔拒绝、foundation123、decimal409/seed4、hypot1005、geometry13、缓存/共享库、Python接口14/参考7、prototype与旧20seed重放通过。Web实际完成两seed默认/新配置完整map/content_store重放，均与对应原生（仅除耗时）相等。','','长原子步骤仍存在，advance单位16检查点不是毫秒承诺；逐阶段分布在Web summary。未测本版非线程Web、设备、正式游戏整段、全部物理/跨缝/出生和奖励领取。0.4.2保持candidate。本轮只读主游戏来源，普通出发仍是其旧Provider，本版不是自动正式接入。SDK安装需19文件整包pin与新版本准入；varied-v1需显式换配置，不能沿用旧实例选择、机制必出现假定或恢复身份。','','工具原件也保留：初次Web导出缺少显式exclude_filter产生错误日志，补齐测试preset后重新导出；首次对照页file URL被浏览器策略拒绝，随后仅为生成的对照目录开启loopback预览并验证40项选择/两种模式，服务器与浏览器均已关闭。它们不冒充算法失败或地图物理验收。']
(ROOT/'runtime_iteration/REPORT.md').write_text('\n'.join(lines)+'\n');print('PASS final source/determinism/validity/native-Web/60 seeds/controller/cancel/report')
