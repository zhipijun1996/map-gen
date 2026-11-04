# 新算法候选调用合同

包版本0.5.0，算法`stable-v4-reward-branches`；实际实现身份为manifest中的`mapgen/gdscript-candidate-0.5.0+<源码摘要>`。源码摘要和20个运行文件的完整SHA一起锁定。源commit、ZIP SHA以发布目录receipt为准；仍为candidate，不是生产或物理认证版本。

## 安装与调用

将独立包的完整`addons/mapgen/`安装到项目同名目录，更新全部20文件锁；新增`reward_branch_planner.gd`，不能沿用19文件清单。宿主版本准入同时允许包内精确实现身份和新算法，不使用只匹配0.4.2的规则。继续显式输入模块ZIP1.1.0（SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`），不下载latest。

```gdscript
const PreloadJob = preload("res://addons/mapgen/preload_job.gd")
const GenerationJob = preload("res://addons/mapgen/generation_job.gd")
const Data = preload("res://addons/mapgen/data_json.gd")

var config = Data.parse(FileAccess.get_file_as_string(config_path)).value
var preload_job = PreloadJob.create(module_zip_path, module_zip_sha256)
# 宿主逐帧advance(1)，读取progress/profile；取消调用cancel。
preload_job.advance(1)
# preload_job.is_done()且result().status=="PASS"后：
var library = preload_job.result().library
var job = GenerationJob.create(request, library, config)
job.advance(1)
# job.is_done()且result().status=="PASS"时，才使用map/content_store。
```

以上代码展示接口顺序，不是完整逐帧循环；调度方式继续使用现有宿主实现。verified library可供多个job复用；每个job拥有自己的候选、RNG、缓存、核心图和奖励支路状态，取消不污染其他job。advance单位不是毫秒保证；推荐继续小批推进，不能把大批4096的耗时视为单帧承诺。

本轮验证单线程交错job，没有验证跨Thread并发共享库。完整content_store已经按实例物化坐标和镜像，宿主按runtime-map/v2装配，不再对内容重复镜像。

相同输入及实现的结果确定性，以未被墙钟预算或取消中断为条件；宿主让帧时间也计入原墙钟预算，检查间隔仍为256次候选展开。

运行示例配置为`profiles/stable-v4-reward-branches.json`。旧v3配置不自动转换或作为失败回退；新配置的`diversity`是本算法必需的显式参数。使用包内候选配置Schema；request/result仍v1、地图仍runtime-map/v2。Python参考实现没有移植本轮新算法，不接受此配置；独立静态审计的身份投影不表示Python生成结果与GDScript一致。

支持seed整数范围仍为±9007199254740991，超范围拒绝、不截断。请求保留真实能力及净空，不为增加可选模块授予double_jump/grapple/wall_climb。源模块、能力、净空、配置、seed和实现身份参与既有指纹；不得沿用旧map_id或恢复身份。run/stage/actor token、bindings、source_record、SceneTree、玩家与钱包留在宿主。

## 地图与奖励支路

Provider的数据转换、完整content_store引用解析及主线程装配接口继续使用runtime-map/v2。新增的支路记录在`result.diagnostics.details.reward_branches`，不是必需的游戏装配协议；主游戏不复制求解或支路规划算法。source_record应记录新包、实现、配置和模块锁。

支路记录包括实例集合、入口、目标奖励实例及两段有向路径。`forward_merge`表示到同一条已验证主路径上更靠后的核心实例；`core_merge`表示回到不同核心实例，未证明在该主路径上的先后顺序；`multi_return`为多模块且只连接原核心分叉的折返；`single_return`为单房折返。向前归并不表示物理上禁止返回。所有新增连接模块都是完整源模块，不移动或裁剪奖励，不补隐式反向Route，不打开未连接Port。

奖励支路增加的连接模块在32个生长目标完成后参与终端搜索；它们是实际新增实例，不计成额外目标奖励，也不降低32生长/6目标奖励/3主路线。搜索仍计入原500000候选和90秒总预算。不能只按每图总模块种类判断改进，需同时看核心种类、实例数和归一化重复指标。

实际content、敌人、普通奖励和目标奖励、Route、镜像、封口均继续完整输出。出生位置、Boss战完成、机制服务和动态实体执行仍由宿主解决。没有新增移动齿轮或随机布怪。

## 独立验证

在独立解压目录、使用锁定Godot4.7.2执行：

```sh
godot --headless --path /absolute/mapgen-godot-candidate-0.5.0 \
  --script res://tests/verify_bundle.gd -- /absolute/modules-1.1.0.zip
```

包内亦携带同SHA模块ZIP作为测试输入。verify逐文件核SHA，并实际生成冻结成功/失败样例、对比完整结果；只排除generation_seconds。失败、取消、预算耗尽的map为null且content_store为空。样例不是运行时地图查询库。

独立生成新请求（输出完整result，含map/content_store）：

```sh
godot --headless --path /absolute/mapgen-godot-candidate-0.5.0 \
  --script res://tests/generate.gd -- /absolute/modules-1.1.0.zip \
  /absolute/request.json /absolute/config.json /absolute/result.json
```

检查报告区分原生、Web及主游戏：真实主游戏装载和玩家试玩本轮未执行。静态可达、作者路径与奖励空间检查不等于完整物理证明，不标生产就绪。
