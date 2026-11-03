# 给 gunman-rush 的第一轮接入交接

只读核对的最新 main 快照为 **30e36c9abe223f26e666ceaf796e3fe9cb58e10f**。具体文件 Git blob SHA 与 SHA-256 在 `host-review.json`；未修改主游戏，未在 Godot 执行。map-edit 当前 main 同时只读核对为 `9b712fe814ef228b368c0eb9adf660e39de29e37`，不因此自动替换锁定 1.1.0。

## 实际主游戏边界

- `docs/architecture.md` 和 `docs/worklines/game_architecture_01/architecture_closeout.md` 明确：Provider 产出 Plan/拒绝；Stage 调 LevelRuntime，Runtime 调原 Assembler/Factory；运行状态、领奖与恢复仍由现有所有者管理。
- `game/world/levels/level_request.gd` 实际是 root_seed 字符串、region_id、map_index、PlayerTuning、expected_hash、root_bell_mode 和 capabilities 的值输入，不是允许任意获取 Session 的服务容器。
- `PlainsLevelProvider.load_level/ForestLevelProvider.load_level` 目前仍调用旧生成器、旧版本重放及 `LegacyRegionPlanAdapter`，结果是 `LevelBuildResult(plan/error/legacy_generated/resolved_capabilities)`。
- `LevelPlan` 是已解析的暂态内部内容，持有模块 Definition、actor/boss/reward 等；不是公共 MapGen 协议，也不是新存档格式。`LevelRuntime.assemble()` 验证 Plan 后调 build_plan，不生成地图、不抽 RNG。
- `tests/level_plan_runner.gd::bare_plan` 已覆盖无旧 Manifest 的 Plan 装配；但 `GeneratedDemoStage.configure_level` 仍保留 source_view，`PlainsRegionStage._ready/capture_state` 仍读 generated.manifest、encounter_plan、机关及表现来源。因此裸 Plan 能装配不等于完整正式新 Provider 已接通。

## 主游戏如何准确使用本包

1. 按根 README 校验 ZIP、解压，执行 verify 与 replay。先读取 `samples/success/result.json`，只接收 PASS，同时保留完整 map 和 content_store。Python 可用于开发机/CI 的参考生成；本包不是 Web 游戏内的 Python 调用方案。
2. 在主游戏新增此来源的 Provider/公共协议适配器。由它把公共 runtime-map/v2 解析成主游戏现有 LevelPlan；不要把 LevelPlan 代码复制到 map-gen，也不要使 map-gen import 游戏类型。这里没有为主游戏创建第二份工厂或新世界管理器。
3. 第一轮先使用冻结样例的 seed 930001 和其精确输入。后续在线生成时，LevelRequest 的字符串 root_seed/map_index 到公共整数 seed 必须制定有版本、可回放的转换，不能直接 int()、截断或沿用一个未声明的旧 RNG 流。plains/thorn_forest 到 catalog 中文区域的映射及实际能力/净空也由宿主明确转换，不静默改冻结样例以通过。
4. `map_id/request_fingerprint` 是输入身份，不能冒充旧 Manifest.expected_hash；可以使用样例 provenance 的 map_content_sha256 作为新来源的已解析内容校验，并给来源与版本独立身份。持久恢复策略仍由现有主游戏状态/记录系统决定，不伪造 legacy Manifest。
5. 将实例 Block 位置、已物化完整内容、实际接缝和所有封口交给已有 Runtime/Assembler/原生机制适配。每个模板实例的 Definition、actor 状态和奖励事务必须独立；遵守主游戏 LevelModulePlacement 对节点名/身份的校验，不用数组下标代替稳定 ID。
6. 在现有 Stage 入口实际接入伤害、机关、Boss 场地/封印、领取、HUD/路线查询、恢复和离图。替换明确的旧来源适配；不要为了使用旧 Stage 而拼一份假的旧 manifest。主游戏 App/Stage/工厂继续拥有自己的服务和状态，本包只供数据。
7. `samples/failure` 的 SEARCH_EXHAUSTED 应转成宿主拒绝/错误结果，不生成默认 Plan，不回退零点出生或旧图。记录公共状态、指纹及错误原因。

## 当前样例与内部 Plan 的具体接入缺口

| 缺口 | 实际来源与责任 |
|---|---|
| 出生点 | 公共 anchors.player_spawn 为 null。M01 `game-plains-windchime-lesson` 的 entry 被 `[0,128,32,128]` 封口；源 content.entry_port `[24,206]` 落在该区域，不能直接当 spawn。主游戏不得用 LevelPlan 默认 Vector2.ZERO 掩盖；需要 map-edit 的实际安全落点及到所选出口的证据，随后宿主绑定 |
| Boss | M40 `game-plains-boss-arena` 已镜像，真实 entry 朝右，exit 初始封口。内容没有 Boss 本体。宿主用现有 BossFactory/Encounter 明确选择身份和结束政策，不能凭 map_index 或位置猜；map-gen 不复制 BossFactory |
| 敌人身份 | 本图原样保留 plains_diver/plains_sentry/plains_charger 共 18 个编译记录；主游戏 EnemyBehaviorRegistry 实际注册 diver/sentry/charger，引用相应 resources/enemies/plains_*.tres，且 charger 有显式历史 revision。Provider 必须核对 Definition/revision 与批准的 overrides，不能直接把 definition 字符串当 behavior_id 或自行剥前缀宣称兼容 |
| 奖励 | 本图 11 个奖励点，含 6 个目标奖励实例。LevelPlan 的 pickups/caches 和旧 Stage tier/收据消费不等同于 reward_sites.amount。保留模块原生领取机制、用途与稳定事务；不重新抽取，不把所有点一律猜成普通宝箱 |
| 模块机制 | 旧模块 registry 只读原 compiled-content 并在 ready 时创建节点，不接受这份逐实例物化 store。宿主需要在创建前供入完整数据的入口；只改 ready 后 content 或负 scale 不足以还原图 |
| 商人和来源恢复 | 当前公共地图没有商人布置。LevelPlan.merchant_position 默认零值及旧 Stage 的强制商人/来源逻辑不能当作合法生成点；宿主需明确此来源支持范围或另立经验证的配置，不向本包伪造商人字段 |
| 当前宿主资格 | 模块 ZIP 原宿主锁为 12f6cb0 的局部路线资格，current-game 锁只核对历史 5f55716 的 API；不能代签本次主游戏 30e36c9 的动作、镜像、跨缝和连续资源 |

以上是准确的后续接入任务，不表示本轮 Python 包验证失败，也不宣称已完成主游戏完整玩法。

## 需要 map-edit 提供/确认什么

参考包运行本身**没有新增字段阻塞**：现有版本/内容哈希、矩形/偏移、Port、显式 Route、奖励关联、purpose/entryPortIds 和编译内容均直接复用，不要求为了打包重做库。后续玩法接入只针对具体缺口补证据或最小契约：

1. 对 M01 的实际可出生位置与到已选 exit 的安全路线给出可追溯声明/认证；现有 entryPortIds 不等于玩家出生点。
2. 对实际使用的原生敌人/奖励消费者确认可解析的原生身份、来源 Definition/revision、覆盖允许值和领取语义，复用已有宿主锁/原生运行时信息；不在 map-gen 建第二份注册表，不凭 amount 或资源文件名猜主游戏含义。
3. 对保留声明路线的镜像、部分 Port、封口与真实邻居接缝补实际验证范围；需要原生玩家档位或邻居几何的条件继续显式保留。已有字段存在，只缺资格时不要用新增布尔值假装认证。
4. 原 1.1.0 `reward-association-gaps.json` 的五个模块仍有未确认关联：`generated-75b420621682d36fc3b7262784c347f0acea7e55422f7e0abaebbc285fa89198` 的 visible-cache；`idea-0363f85c-16c0-4b5f-b3b0-461335608db7-enemies-2`、`idea-0363f85c-16c0-4b5f-b3b0-461335608db7-enemies-3`、`idea-96ba6bf1-9b60-470a-9128-54ae7ea44af3`、`idea-orbit-choice-001` 的 reward。最后一个出现在本图普通房。仅在有真实证据时补所需关联，不由 proximity 推断或删除奖励。

map-edit 当前 main 的物理 Port 别名告警也需在升级模块包时核对，不能把当前原件告警直接套成锁定 1.1.0 的失败原因。本轮不升级库、不改原件、不扩大能力或放宽目标以获得通过。

未来移动齿轮的模块边界/路线/禁入约束由 map-edit 提供，地图级选择/布置由 map-gen 输出，主游戏执行；本轮没有增加该功能或随机布怪字段。
