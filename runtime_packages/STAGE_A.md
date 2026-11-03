# 阶段A：0.3.1 调度候选（stable-v2）

本版本只改变调度、预载和纯计算缓存，不修奖励冲突。0.3.0、Python参考包和旧预期保持原样。实现身份`mapgen/gdscript-candidate-0.3.1`参与原指纹；算法仍stable-v2，输入/配置/结果v1及runtime-map/v2不变，模块锁仍1.1.0/SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`。

安装包内`addons/mapgen`到相同res路径。纯数据组件不依赖LevelPlan、SceneTree、玩家或Factory；预载器是独立I/O适配器，不执行包内脚本/场景。

```gdscript
const PreloadJob=preload("res://addons/mapgen/preload_job.gd")
const GenerationJob=preload("res://addons/mapgen/generation_job.gd")
const Protocol=preload("res://addons/mapgen/protocol.gd")
var load_job=PreloadJob.create(explicit_zip_path,Protocol.PACKAGE_SHA)
load_job.advance(1) # 反复推进，可cancel()；期间result不返回部分library
if load_job.is_done() and load_job.result().status=="PASS":
    var library=load_job.result().library # 多个请求复用，不重复ZIP/JSON预载
    var job=GenerationJob.create(request_dictionary,library,config_dictionary)
    job.advance(1)
    var progress=job.progress()
    # 退出或换请求时，由同一拥有者串行调用job.cancel()。
    if job.is_done():
        var result=job.result() # 只有PASS具有完整map/content_store
```

使用data_json.gd读取输入，保留整数/decimal精度。seed支持±(2^53−1)，整数原点±10^9，距离分量±2×10^9；超出拒绝、不截断。request/config显式传入，不包含run/stage/actor token、bindings、source_record或主游戏类型。

一个advance单位是16个细分检查点，合法预算1..4096，不是毫秒或固定候选数。候选求值/原500000预算、90秒墙钟及检查点语义保持；宿主暂停会消耗墙钟时间。相同job不可重入/跨线程并发推进，取消必须投递给其拥有者，丢弃挂起job前调用cancel。完成结果的快照拷贝耗时另行记录，不能当作免费操作。

改动：ZIP分块SHA和逐文件校验；JSON可取消遍历及精确decimal缓存；库的只读内部视图；请求自己的图/可达缓存（哈希命中仍比较完整图，防碰撞）；稳定排序/图遍历/配置/最终检查拆分；最终诊断移除无用的重复拷贝，公开result仍返回快照。新增检查点和缓存不抽随机数、不增加算法求值计数。

证据：40seed+冻结成功/失败42例完整结果一致（只分离实现身份及耗时），另有批次17/128和3个取消样例，共47例。真实Godot Standard4.6.3和单线程Web/Chromium执行通过。Web真实Escape事件测得：预载输入到完成15.2ms（含14.5ms排队），生成8.4ms（含7.7ms排队），不是只量cancel()执行时间。原生另保留外部输入截止时刻到完成的排队/推进延迟。

**性能目标未全部达到。** 本轮目标advance(1)各阶段p99≤4ms、最大≤8ms；Web默认完整图最大一次32.1ms，部分p99超过4ms，宿主8ms一帧调度目标也有越界。Web可推进预载墙钟27.449s，默认图78.916s；这些包含让帧与并行验证环境，不是比原同步版本更快的承诺。逐阶段总时间、最大值、p50/p95/p99及结果拷贝在evidence报告。ZIP单文件解压、部分快照、字符串/小规模几何仍为原子工作，后续需进一步细分，不能宣称稳定60fps。包为candidate，不是生产就绪或地图可玩认证。

独立验证：`godot --headless --path <解压根目录> --script res://tests/verify_bundle.gd -- <显式ZIP路径>`。samples是校验参考，生成器从不查询预存地图。原封口—奖励缺陷在此版本仍存在；A的结果一致证据不能代替B验收。

主游戏PR127最新核对head `e7d703f47c97f09bd5c5d48e24f0a400c958ad40`。实际Provider签名已为`load_level(request,map,content_store,selected_ids,spawn,source_sha256,bindings,source_record,binding_id="seam")`。这些新增参数属于宿主：bindings/selection及实际内容文件SHA由其验证，source_record绑定mapgen_commit、协议和library_sha；不伪造未写出的文件SHA。先经现有来源验证，再将算法PASS结果交Provider；入队/装配每批/提交前核宿主token与请求指纹，节点装配在主线程。不要将新实现的map_id当旧冻结图身份，不二次镜像/source_affine，不删除未知内容绕过宿主拒绝。spawn/Boss仍未解决，移动齿轮和随机布怪未实现。
