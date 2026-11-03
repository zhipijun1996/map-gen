# 给 map-gen / map-edit 的第一轮反馈及第二轮清单

依据：宿主 main `30e36c9a` 加本轮有限适配；map-gen `178c4016`、module-pack1.1.0。完整 SHA、输入和真实 Godot 证据见[宿主报告](integration.md)与[证据](../../evidence/mapgen_host_v2_01/README.md)。这是可随宿主PR传递的反馈文件；未擅自修改上游仓库。

## 已实测的宿主要求

| 项目 | 本轮实测与限制 | 交接要求 |
| --- | --- | --- |
| 输入形式 | 冻结 JSON 经 FileAccess→Dictionary→Provider→Plan→Stage→原 LevelRuntime，真实三个模块已装载。Python只运行于开发工具。 | 正式参考包仍交相同 runtime-map/v2 + content_store + request/config/library/implementation/fingerprint及文件SHA，不重新设计地图协议；附 PASS/失败/取消例子和版本锁。 |
| 坐标/镜像 | 原矩形、单向、封口、ellipse已验证；原点平移一次，已物化 sign保留。当前适配只支持128px。 | 保持 coordinates、transform、原 Port/Route/ID 和局部内容完整；不要让宿主重复执行 source_affine，不把 R/L名字当方向。若改 block_size，先声明，当前宿主明确拒绝。 |
| 机制复用 | 精确 ellipse Resource 接原 MovingPlatform，真实玩家骑乘；未导入旧App/安装器/场景脚本。 | map-edit按既有 compiled字段交叶级行为合同、轨迹/phase/x_sign等原义及源SHA；不交会新建玩家、碰撞、wallet/policy的自启动整套宿主。 |
| 同类多实例 | M18/M21同模块完整重复实例，visited/clocks以原实例ID隔离。 | 每实例及本地对象ID稳定，事务身份遵循现有 `run_id/map_id/instance_id/local_object_id`；严禁数组下标、Godot instance_id或Node.name作为长期ID。敌人/奖励跨实例隔离第二轮实测。 |
| 取消/恢复 | 同图reload保玩家/钱包/policy，时钟恢复；旧actor token失效，退出释放原节点和音频。 | 后续结果带request fingerprint与当前run/stage/actor token。CANCELLED或场景已退出不得提交；取消不能回调操作Godot树。需交可取消/有界checkpoint的运行时算法入口。 |
| 源验证范围 | 上游 JSON Schema PASS与宿主实际Motor接缝/骑乘是不同证据；C031只静态核。 | `STATIC_GRAPH_ONLY`、source validation、实际物理证据分开交，不把 author_path 或包内认证直接提升成当前宿主可玩。 |
| 完整地图锚点 | 原整图player_spawn/boss_completion为UNRESOLVED，boss_encounter为HOST_BINDING_REQUIRED。本轮未隐藏这些缺口。 | map-gen继续原协议标未解决；map-edit提供候选安全出生/终端空间与净空资料。宿主绑定实际spawn→departure、BossFactory/arena/结束结算，不擅开已封Boss出口。 |
| 数值 | Godot JSON数字实际读取为float；曾导致930001.0文本和float/int membership宿主错误，均已修复。 | 当前宿主seed只接受有限、整数、绝对值≤2^53−1，再规范化成整数文本。若算法允许更大seed，正式交接先协商无损传输适配，不能静默舍入。 |

## Godot / Web：源码核实，尚未导出实测

- 当前Web preset `variant/thread_support=true`、`variant/extensions_support=false`，Compatibility渲染。**PythonAPI/本地进程不能成为游戏Web运行时调用路径**。线程开关不证明已有算法worker；宿主目前没有该调度器。
- `export_filter=all_resources` 不保证 FileAccess读取的任意JSON入包。当前 include_filter 没有 `resources/levels/mapgen_host_v2_01/*.json`，本轮刻意未改普通导出，因此这个原生入口**尚不能直接当已打包Web入口**。后续须在原export preset/原raw exporter合同增加有限确切数据路径，并对实际PCK逐份读回核SHA，不能开泛目录兜底。
- docs/tools/tests/build为导出排除；来源ZIP和开发Python证据仅在docs，不进游戏。运行时依赖是现有玩家场景、tuning、当前武器定义、RunSession/服务、Input、Underworld表现/原图声和新增椭圆Resource；不依赖map-edit绝对路径或可执行source_scene_ref。
- Web模板不支持任意命令行scene覆盖；需走原 cloud_preview 的场景准入和bootstrap，或正式App明确Provider选择。当前只交原生scene，不复用旧公开URL、不发布。
- 若接网络数据，需要明确同源/CORS、错误/取消/离线策略；`res://`为包内只读，缓存应走既有允许的`user://`策略。当前无网络请求、worker、浏览器/PCK/实体设备证据。

## 运行时算法调用：建议，不是已实现

在新算法包完成前保持 PythonAPI作为开发参考生产者，冻结数据直接替换同协议输入。运行时选型由map-gen提供可在Godot/Web执行的实现或正式桥接包；主仓只保留请求、调度和结果适配，不复制生成算法。

建议调用形态仍为 `generate(request, library, config)` 的数据边界，外加原协议已有的状态/指纹/事件；如果采用分步推进，每帧限额需可量测且与确定随机流隔离。线程/Worker仅计算纯数据，主线程构建节点；异步结果在入队、每批创建及提交前核lifetime/fingerprint。原Python hooks不能直接证明Wasm/Worker可取消。GDExtension若被选中，要单独交Web可用构建及启用扩展的影响验证；当前preset不支持直接装入。

能力快照必须来自真实controller，而非示例请求硬编码：jump enabled/max_jumps、recoil路径/武器/能量policy、hook_enabled、实际collision净空、当前装备/永久升级与tuning指纹。当前示例请求含grapple，但切片玩家明确未授grapple；局部接缝/骑乘成功不证明整图能力满足。LevelRequest已有capabilities Dictionary，不新造第二套能力权威。

## 源问题与宿主迁移需求分别记录

本轮所选内容未发现阻止装载的源几何缺陷。零个简单危险相邻对是选择覆盖缺口，不据此判模块库错误。原始全图还含18敌人、11奖励site、3hazard、12thorn、7saw、9latch、1hook、20HQ cell等本轮未适配内容；字段逐实例清单在证据ZIP `upstream/full-content-inventory.json`。完整装载当前应拒绝，不能删除后宣称成功。

实际发现的宿主错误与修复：JSON整数规范化、ellipse sign类型比较、测试face反例未真正修改、StaticBody检索包含Animatable子类；全部保留失败。旧 build合成脚本污染Godot class cache的问题仅通过本地ignored build/.gdignore和重建缓存解决，无生产逻辑/物理变化。旧正式App依赖legacy Manifest、未接物化敌人/奖励、能力快照不足属于宿主第二轮迁移，不要求上游把旧Manifest字段全塞回v2。

## 第二轮：从切片到完整地图

| 优先级/责任 | 具体消费者与待做 | 验证与回退 |
| --- | --- | --- |
| P0 宿主+map-edit | 依 full-content-inventory 逐类实现现有Plan/Definition机制映射；明确wall/HQ、linear ferry、hazard/thorn/saw、hook、latch及关联敌人原义。不要把旧shot-latch再镜像或按旧node_index索引。 | 每类完整原模块、原身份/phase、真实Motor/伤害及退出；未知字段仍拒绝。每类独立提交，以前一已验提交回退。 |
| P0 宿主 | EnemyFactory/Damageable、RewardGrant/钱包/宝箱现有消费者沿实际actor/reward rows驱动，去掉这条新源对旧encounter_plan/随机奖的依赖；不改经济。 | 同模块多实例不串伤害/奖励；领过不重发、reload不刷怪/钱、取消不提交；单独提交回退。 |
| P0 三仓 | 安全spawn及departure路径、BossFactory/arena/入口封锁/致死优先/原奖励和结束绑定；导出实际能力快照。 | 原生连续动作、全部终端与能力锁反例；保source unresolved直到验过。 |
| P1 宿主 | 将正式App及Plains/GeneratedStage的显示、地图记录、恢复消费者改为Plan+源专属数据，确认每处legacy_generated读取迁走，再引入可选地图Provider。正常出发切换另批。 | 原正式两区回归、完整46实例/所有内容、稳定对象状态、hash/fingerprint拒绝；每批回退上一个已验提交。 |
| P1 宿主 | 批量节点装配预算、资源预载/共享、完整地图相机/边界及Web准入。 | 真实导出PCK隔离加载、浏览器长帧/内存/取消和手机；不要把本轮headless局部结果签性能。 |

## 第二轮：从冻结数据到运行时算法

1. map-gen正式参考包按同v2交 request/config/library/source锁、完整map/content、结果状态、失败/取消样例及复现命令。先在当前冻结入口替换输入并重跑相同测试，确认协议没有漂移。
2. map-gen交Godot/Web可执行算法包和有界调度/取消合同，保随机流归算法包。宿主只接纯数据请求与结果，不粘贴Python算法。
3. 宿主接原lifetime、进度、错误与退回流程；测试退出/换图/重复结果/旧fingerprint，失败不偷偷fallback旧生成器或换seed。
4. 完整记录需绑定request/config/library/content/实现、能力快照及宿主spawn/Boss binding；当前map_hash仅mapSHA+选择ID，不足以证明完整重放。先补真实record/restore消费者，再讨论持久保存，避免顺带改存档schema。
5. 原生通过后再做Web有限导出、实际PCK/浏览器与实体手机验证；未经用户后续发布授权不部署。本轮已提供可评审代码和证据，不等待上游算法完成而复制平行实现。
