# Godot算法候选0.3.0交接

算法/交付源commit：`508b558e8a9925862e8a26c20fea008b9a772007`。工作分支`feature/godot-data-candidate-v0.3`从PR2 head `0d338c2309d4e17bd8e9b128f745eb93938e99b2`继续；PR2未合并，因此审查PR以其分支为base，避免重复审查Python交付。gunman-rush PR127最新head已复核为`9e97b553b7b51cbc64922ed94281061202e3e58b`。

| 产物 | 路径与SHA-256 |
| --- | --- |
| Godot候选算法包，1,899,913字节 | [mapgen-godot-candidate-0.3.0.zip](releases/0.3.0/mapgen-godot-candidate-0.3.0.zip)；`9ea87854c96cf7c2189b4c6ad25a8056454a3150721bead79c335aca8678acd0` |
| 实际Web测试导出，11,323,381字节 | [mapgen-web-conformance-0.3.0.zip](releases/0.3.0/mapgen-web-conformance-0.3.0.zip)；`d928e0a329e6ebd8f0358c29a273b446aaf6ad59030d60ef4cd4df29c1e01ed4` |
| manifest/来源/解压校验 | 包内manifest.json；[receipt](releases/0.3.0/receipt.json)；[实际ZIP解压及二次构建结果](../validation/godot-candidate-0.3.0/package/report.json) |

`runtime_target=godot-standard-gdscript`，`readiness=candidate`、`production_ready=false`。这次是实际GDScript算法，不是Python进程或预存地图读取。Python0.2.0包、0.1.0地图包和所有旧实验原件未修改。

协议入口：[GenerationJob](addons/mapgen/generation_job.gd)、[协议/身份](addons/mapgen/protocol.gd)、[真实ZIP适配器](addons/mapgen/module_archive.gd)、[调用合同](docs/HOST_API.md)。继续request/config/result v1、runtime-map/v2、模块1.1.0，Schema只增加新实现允许值。seed支持±(2^53−1)，不截断。

真实样例在包内`tests/samples/{success,failure}`，保留未改的Python参考request/config/模块锁/来源及完整result（内含完整map/content_store）。新实现原始结果和逐项差异在仓库[42例对照](../validation/godot-candidate-0.3.0/replay-precision/summary.json)，每例目录有request、完整actual/reference压缩JSON、计数及引擎日志。失败样例无可用地图。身份差异与布局/图/内容/计数分开核对。

已完成：真实模块读取与全量水平镜像、CPython随机兼容、生长/回退/闭环/AIR/Boss/奖励求解、原门禁与独立审计、完整v2输出、创建/推进/进度/取消/结果，以及独立候选包。默认930001输出46实例/55连接、6目标奖励/3主路，保留18原敌人/11奖励site；32项调度检查、42例完整重放、数值及库全字段对照、原生和实际Web、独立解压及可重复构建均通过。Python接口14、参考合同7和历史20seed保护通过。

限制必须随包转交：实测原生advance(1)最大22.16ms；Web advance(128)最大517ms、4096最大6.865秒。算法操作数有界，尚不提供硬帧时限。库预载仍是显式阻塞阶段。测试在并行验证环境与软件Chromium中执行，不是隔离性能基准或手机认证。完整性能/取消及早期失败见[报告](docs/RESULTS.md)。整个地图物理和主游戏可玩性仍NOT_RUN；spawn/Boss锚点仍未解决。

给gunman-rush的接入步骤：

1. 安装包内`addons/mapgen/`到相同res路径，保留版本/manifest锁；不要复制求解器进主游戏业务代码。
2. 先按[README](README.md)在主仓之外运行`tests/verify_bundle.gd`，模块ZIP显式传入。再从真实controller/tuning构造能力快照，调用`GenerationJob.create(request,library,config)`，串行小批次推进。不要把run/stage/actor token塞进request。
3. 宿主保存token/fingerprint信封，在入队、每批主线程节点创建及提交前检查；退出先cancel job，CANCELLED或旧token不提交。调度器需承认上面的原子工作长帧限制。
4. 将PASS的map/content_store送现有RuntimeMapV2Provider。先复验既有M16/M18/M21切片；新map_id与实现指纹单独记账，旧冻结SHA锁原样保留。不要二次镜像/source_affine，不执行模块包旧宿主。
5. 完整46模块的机制、敌人/奖励、spawn/Boss绑定和整图装配/手机性能仍按主仓第二轮清单推进。未知内容保持拒绝，不删除后冒充完整支持。本轮未改主仓或部署网站。

map-edit本轮无需为算法读取改包或升级1.1.0。后续具体缺口是`game-plains-windchime-lesson`封口配置下的安全出生与departure净空候选，以及`game-plains-boss-arena`的Boss/终端空间约束；helper entry/exit不具备这项认证，详见调用合同。实际玩家授权、BossFactory/完成结算属于宿主。移动齿轮与随机布怪本轮没有实现。
