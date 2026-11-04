# 安装与调用合同

本次不替换默认算法、不自动合并、不修改主游戏。两包有不同用途，不能混装：

| 项目 | 0.5.1性能候选 | 0.6.0-experiment研究原型 |
|---|---|---|
| 运行文件 | 完整20个 | 完整22个 |
| 算法 | stable-v4-reward-branches | stable-v5-joint-reward-plans |
| 实现 | mapgen/gdscript-candidate-0.5.1+002f012d94cb | mapgen/gdscript-experiment-0.6.0+3738e5100505 |
| 配置 | 0.5.0原v4配置 | 新v5 joint-v1，含planning |
| 旧地图 | 布局/内容/计数一致，身份不同 | 新行为，新预期 |
| 状态 | candidate | research-prototype，不作默认替代 |

模块ZIP锁继续1.1.0、SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`；地图runtime-map/v2，request/result/config版本v1。研究包使用包内扩展配置Schema，不能与旧v4配置互换；Python参考包不支持新v4/v5算法。

选择一个包，将完整addons/mapgen安装，按manifest更新所有运行文件SHA；以package.implementation和algorithm精确更新Job/Provider版本准入及source_record包锁。包内source-lock.json提供运行文件锁。0.5.1虽行为等价，仍必须更新实现指纹、map_id和恢复身份，不能冒用旧身份。现有安装器若锁死19文件或旧算法需显式升级清单；不把新包覆盖进旧锁而跳过校验。

现有预载、job、Provider和地图转换接口不变，无需复制求解器或重写装载架构：

```gdscript
const Load = preload("res://addons/mapgen/preload_job.gd")
const Job = preload("res://addons/mapgen/generation_job.gd")
const Data = preload("res://addons/mapgen/data_json.gd")
var config = Data.parse(FileAccess.get_file_as_string(config_path)).value
var load_job = Load.create(zip_path, expected_sha)
# 宿主每帧推进，直到完成；期间可cancel、读progress/profile。
load_job.advance(1)
# 必须先检查完成且result().status=="PASS"，再使用library。
var library = load_job.result().library
var job = Job.create(request, library, config)
job.advance(1)
# 仅完成且status=="PASS"时使用result的map和content_store。
```

示例展示接口顺序；实际帧循环、暂停/取消与主线程节点装配由宿主控制。软操作预算不保证毫秒。请求保留真实能力及玩家净空，seed支持±9007199254740991范围内整数，超范围拒绝不截断。共享已验证library可复用；可变状态及缓存归各job，取消不污染其他job。仅验证单线程交错，未验证跨Thread共享。

Content_store已物化实例坐标与镜像，宿主不要重复镜像；完整引用必须解析。Route方向、原内容/敌人/普通奖励/目标奖励/封口保留，不新增移动齿轮或随机布怪。branch诊断不成为游戏装配依赖。run/stage/actor token、bindings、source_record、LevelPlan、SceneTree、玩家、钱包和Factory不进入算法或请求指纹。

独立解压后使用锁定Godot4.7.2（依赖锁在dependencies）：

```sh
godot --headless --path /absolute/unpacked-package \
  --script res://tests/verify_bundle.gd -- /absolute/modules-1.1.0.zip

godot --headless --path /absolute/unpacked-package \
  --script res://tests/generate.gd -- /absolute/modules-1.1.0.zip \
  /absolute/request.json /absolute/config.json /absolute/result.json
```

包内profiles/config.json是显式配置；samples含真实request/config、完整result/map/content_store及物化引用。模块ZIP作为明确参数，包内tests/dependencies/modules.zip仅供同SHA测试。verify逐文件验SHA并实际重放冻结样例，失败必须无地图；不是以样例查询代替生成。新源码commit、ZIP SHA和独立验证收据见同目录receipt.json及包manifest。

0.5.1保留0.5.0的930005/930024/930031失败。研究原型改善成功率但降低源种类/非单房支路比例，不建议直接默认接入。收益仅为独立原生/Web测试，本轮未运行主游戏；整图动作、接缝和封口物理仍未认证。
