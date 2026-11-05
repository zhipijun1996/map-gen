# 0.8.0研究包调用合同

runtime_target=godot-standard-gdscript，readiness=research-prototype，production_ready=false，default_replacement=false。算法experimental-v7-joint-route-construction、精确实现mapgen/gdscript-experiment-0.8.0+2271b5d4da0d。完整28个运行文件安装并逐文件锁SHA，不能混用0.7.0的25文件清单。新增structure_basis.gd、transit_index.gd、merge_constructor.gd；主体仍为RefCounted纯数据组件。

模块仍1.1.0 SHA 5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723，地图runtime-map/v2，request/result/config版本v1。候选专用Schema增加construction必需配置，不升级公共协议或让主游戏复制算法。

profiles/joint-merge.json为主配置：construction.anchor_growth_count=4、max_anchor_growth_count=8、bypass_depth=2、macro_candidate_limit=96、core_loop_policy=path_gain。topology要求一forward_merge＋五multi_return。legacy-loop-ablation.json仅为显式比较，不作为失败回退。未知/缺失字段、超出合法seed整数范围±9007199254740991均拒绝，不截断。

继续现有API：

```gdscript
const Load = preload("res://addons/mapgen/preload_job.gd")
const Job = preload("res://addons/mapgen/generation_job.gd")
var loader = Load.create(module_zip_path, expected_sha)
loader.advance(1) # 宿主逐帧推进、查询progress/profile、需要时cancel。
# 完成且status=="PASS"后复用library：
var job = Job.create(request, loader.result().library, config)
job.advance(1)
# 完成且status=="PASS"才使用map和完整content_store。
```

代码展示调用顺序，帧循环与节点装配仍由宿主负责。新增阶段transit_catalog、joint_merge、demand_core_routes；保留motif_catalog/growth/structure_domains/reward_branches/最终审计与导出。宿主需容忍未知阶段名称，操作数不是毫秒保证。墙钟预算与取消会中止确定性计算，不因让帧批次额外消耗RNG。

Job/Provider版本准入、source_record及恢复身份使用新实现/配置指纹；不沿用旧map_id。run/stage/actor token、bindings、LevelPlan、SceneTree、玩家、钱包、Factory不进入算法请求或指纹。API形状及runtime-map/v2转换合同保持，主线程装配责任不变。

已验证ZIP库可复用，两个派生目录和搜索状态归单个job，取消不污染另一个交错job。仅验证同线程交错，未验证跨Thread共享。所有派生数据可从锁定源模块和当前上下文重建，不是第二套模块源。

完整模块内容、敌人、普通与目标奖励、作者Route、镜像及未使用Port封口保留；已物化content_store引用须完整解析，不重复镜像。forward_merge是有向图上回到冻结主路径的下游位置，不证明物理上禁止折返。Boss战完成、出生点、宿主服务及动态机制执行仍属于主游戏。

仓库外独立解压，使用dependencies锁定Godot4.7.2：

```sh
godot --headless --path /absolute/mapgen-godot-experiment-0.8.0 \
  --script res://tests/verify_bundle.gd -- /absolute/modules-1.1.0.zip

godot --headless --path /absolute/mapgen-godot-experiment-0.8.0 \
  --script res://tests/generate.gd -- /absolute/modules-1.1.0.zip \
  /absolute/request.json /absolute/profiles/joint-merge.json /absolute/result.json
```

包内同SHA模块ZIP只作为明确测试输入；samples含完整map/content_store及物化引用。verify真实重放，只去generation_seconds。预算负例明确使用candidate_budget=1，不能冒充生成效果测试；所有比较生成仍90秒/500000/原目标。失败或取消map=null且content_store={}。

主游戏、完整物理与可玩性本轮NOT_RUN，普通模块覆盖和Boss路线长度风险见报告，不建议自动切换正式锁。
