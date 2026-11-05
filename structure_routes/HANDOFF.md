# 0.7.0-experiment调用合同

算法experimental-v6-structure-first，runtime_target=godot-standard-gdscript，readiness=research-prototype，production_ready=false。不能当作0.5.1原样换锁的生产候选；本实验有已记录的真实失败和额外奖励结构硬要求。新地图、新RNG调用、新搜索计数、新实现身份，不沿用旧恢复身份。

25个运行文件完整安装到addons/mapgen，按manifest/source-lock逐文件锁定，不能混用20/22文件清单。新增solver_basis.gd、structure_planner.gd、motif_catalog.gd，基础几何、最终审计和导出仍为冻结旧实现的复用。精确implementation见manifest及selection.json，版本准入需要同时匹配algorithm和implementation。

请求/结果仍v1，地图runtime-map/v2。候选专用配置Schema仍v1，新增必需topology对象，旧v4/v5配置不接受，不隐式转换。profiles/returns.json和profiles/merge.json是两种显式目标，不是失败回退链。reward_modes长度须等于reward_target，backbone_min/max须合法且不超过growth_target。

支持seed整数±9007199254740991，超范围拒绝不截断。模块继续1.1.0、SHA 5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723。玩家能力、净空、输入浮点类型、配置和模块锁参与现有确定性指纹。run/stage/actor token、bindings、source_record、LevelPlan、SceneTree、玩家、钱包及Factory留在宿主。

API形状与旧候选相同：

```gdscript
const Load = preload("res://addons/mapgen/preload_job.gd")
const Job = preload("res://addons/mapgen/generation_job.gd")
const Data = preload("res://addons/mapgen/data_json.gd")
var config = Data.parse(FileAccess.get_file_as_string(config_path)).value
var loader = Load.create(module_zip_path, expected_sha)
# 宿主逐帧推进；期间可progress/profile/cancel。
loader.advance(1)
# 完成且loader.result().status=="PASS"后：
var job = Job.create(request, loader.result().library, config)
job.advance(1)
# 只有完成且job.result().status=="PASS"时才装配map/content_store。
```

代码展示调用顺序，实际帧循环与节点装配属于宿主。新增进度阶段motif_catalog、structure_backbone、structure_domains，另有原growth、closure_search、reward_branches和最终检查/导出阶段；宿主应显示未知阶段名而不是依赖旧阶段穷举。操作预算不是毫秒保证。

已验证library只读复用；motif目录和候选域属于单个job，每次可由真实模块重建，不是第二套模块来源。取消清空结果，不污染其他job。仅验证同线程交错，不承诺跨Thread共享。推进批次不应改变结果，但墙钟预算和取消中断除外，宿主让帧时间仍计入原90秒墙钟预算。

未使用Port全部合法封口，不能为满足归并打开闲置接口。作者有向Route不反转；坐标使用整数/倍增整数。保留普通奖励、目标奖励、敌人和完整模块内容。content_store已物化镜像与坐标，必须完整解析引用，宿主不重复镜像。forward_merge只证明在冻结实际主路径上向后归并，不证明物理上禁止返回。

独立解压后，以dependencies中的锁定Godot4.7.2验证：

```sh
godot --headless --path /absolute/mapgen-godot-experiment-0.7.0 \
  --script res://tests/verify_bundle.gd -- /absolute/modules-1.1.0.zip

godot --headless --path /absolute/mapgen-godot-experiment-0.7.0 \
  --script res://tests/generate.gd -- /absolute/modules-1.1.0.zip \
  /absolute/request.json /absolute/profiles/returns.json /absolute/result.json
```

包内包含同SHA模块ZIP作为测试输入，完整成功、SEARCH_EXHAUSTED、BUDGET_EXHAUSTED和jump-only失败样例。verify对比完整结果，只去generation_seconds；样例不用作运行时地图查询库。主游戏无需复制算法或改写runtime-map/v2转换，但本轮未在主游戏运行，不建议自动切换正式游戏锁。
