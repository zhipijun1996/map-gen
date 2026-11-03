# gunman-rush 调用边界

由主仓安装本仓交付的 `addons/mapgen/`，主仓不复制或再实现求解器。所有核心脚本是纯数据 RefCounted；唯一文件访问适配器为 `module_archive.gd`。不依赖 Node、SceneTree、LevelPlan、Factory、玩家、钱包、主仓脚本、Python进程或预存地图查询。测试的 Node/SceneTree 只是独立运行入口。

```gdscript
const Archive = preload("res://addons/mapgen/module_archive.gd")
const DataJSON = preload("res://addons/mapgen/data_json.gd")
const GenerationJob = preload("res://addons/mapgen/generation_job.gd")
const Protocol = preload("res://addons/mapgen/protocol.gd")

# 显式加载边界：校验ZIP、657个文件、解压并解析真实模块。
# 这是可测量的预载操作，不能算入单帧job推进预算；库可复用。
var loaded = Archive.open_zip(module_zip_path, Protocol.PACKAGE_SHA)
if not loaded.ok:
    return loaded.error
var request_data = DataJSON.parse(request_json)
var config_data = DataJSON.parse(config_json)
if not request_data.ok or not config_data.ok:
    return "invalid JSON"
var job = GenerationJob.create(request_data.value, loaded.library, config_data.value)

# 宿主保存自己的 run/stage/actor token 信封，不塞入request或指纹。
# 每帧可按宿主时间上限反复 advance(1)，检查时间后继续/让出。
var state = job.advance(1) # 合法范围1..4096；操作单位不等同毫秒
var progress = job.progress() # 数据副本，没有节点引用
if should_cancel:
    job.cancel() # 必须在丢弃一个未完成job前取消，解除挂起的续体
if job.is_done():
    var result = job.result() # 数据副本；失败map=null、content_store={}
    # 入队、装配每批和提交前由主仓核token及fingerprint。
    # 只有PASS可交现有v2 Provider；节点装配仍在主线程。
```

不支持对同一个 job 并发/重入推进。无需线程或 SharedArrayBuffer。`advance(0)`、`advance(4097)`返回调用错误且不改变搜索；完成后推进/取消保持结果。取消是在数据检查点退出，不调用宿主树或异步完成回调。进度没有伪造百分比，搜索回退时实例数可下降。

操作预算与算法候选预算分开：前者包括预处理/调度检查点，后者保持参考版的候选几何求值计数（包括lookahead和预留）。候选预算先递增后检查`>limit`，limit=1在第2次求值拒绝；墙钟仍使用原显式配置和检查间隔。墙钟包含宿主暂停，机器负载及暂停可能改变预算失败时点；确定性比较基于未触发墙钟/外部取消的输入及候选预算。调度批次不会抽随机数。

固定种子范围±(2^53−1)，整数原点范围±10^9。用 DataJSON 先读取原始JSON；若宿主已经把seed舍入成float，组件将拒绝它，无法替宿主恢复原值。当前Godot4.6.3 Standard为测试版本，不要求.NET或GDExtension。

输出仍为 `mapgen/generation-result/v1`、`mapgen/runtime-map/v2`，模块仍1.1.0。新增实现身份由现有generator.implementation表达，Schema只增加允许值，不升级或另造地图协议。Python参考及0.1.0历史产物保持原样。

`content_store[instance.content_ref]` 是完整、已物化且已镜像的编译字典，包含原机制、敌人和奖励；`source_scene_ref/source_compiled_ref`仅是模块ZIP内来源引用。世界坐标=`origin_blocks*128+local_pixel`。不要再次镜像、应用source_affine或运行包内旧宿主。未用Port有原齿轮封口，Route from/to不因镜像反转。

身份：`implementation`参与请求+配置+模块SHA指纹。新编码是data_json.canonical的Godot全精度有类型JSON，与Python canonical不同；map_id会随之改变。跨实现报告只明确剔除map_id、generator.implementation和generator.request_fingerprint三项身份字段，完整布局、连接、图、内容、Route、封口、输入与计数另行严格比较。相同Godot实现的批次比较只去掉metrics.generation_seconds。

宿主仍拥有能力快照、LevelPlan转换、调度token、主线程节点创建及服务绑定。player_spawn/boss_completion继续UNRESOLVED，boss_encounter继续HOST_BINDING_REQUIRED；不打开封住的Boss出口，不猜玩家出生，不随机替换怪物或奖励。

本轮不需要map-edit为算法读取新增字段。后续玩法需要具体安全出生候选及departure净空/路径、Boss空间及终端约束、机制叶级语义与源证据；这些缺口不等于要求模块包升级。实际BossFactory/胜负/结算与能力授权属于宿主。移动齿轮仍是后续地图级附加危险，本轮没有布置或新增未使用字段。
