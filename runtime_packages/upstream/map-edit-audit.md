# 模块包运行时接入准备审计（2026-11-03）

## 基线与结论

- 工作分支：`audit/runtime-integration-readiness-20261103`；起始/比较 main：`9b712fe814ef228b368c0eb9adf660e39de29e37`。最终审计提交由 PR 固定，不把后续分支内容当 main。
- 历史输入：用户指定的 [1.1.0 ZIP](https://raw.githubusercontent.com/zhipijun1996/map-edit/47aefebe07f4f0e7471f3d1546214502a6b2aade/releases/map-edit-modules-1.1.0.zip)，**先核 SHA 再打开**：`5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`，1,750,444 bytes。
- ZIP 内实际来源提交是 `02b5cb53b06d7009225b2ecff9351f315e46b12e`；下载 URL 的 `47aefebe…` 是含该产物的仓库提交，两者不能互换。
- 裁决：1.1.0 是完整、非空、可校验且有明确固定宿主依赖的模板输入；**还不是“任意封口/镜像后可在最新主游戏完整游玩”的证明**。本轮不修改 Module、玩家物理、经济、历史包或认证，不合并/发布。

证据入口：[`input-checks.json`](../../evidence/runtime-integration-audit-20261103/input-checks.json)、[`baseline-diff.json`](../../evidence/runtime-integration-audit-20261103/baseline-diff.json)。工具和精确复现命令见 [checks.md](checks.md)。

## A. 当前 main 与历史包实际差异

| 项目 | main `9b712fe8` | 历史 1.1.0 |
|---|---|---|
| 正式目录 | `modules/catalog.json`，82 个 | 包内 `catalog.json`，115 个 |
| schema | `map-notes/module-archive/v1` | `map-edit/delivery-catalog/v1` |
| 更新引用 | 仍是 `content/task-a-workshop` | manifest 固定来源 `02b5cb53…` |
| 共同稳定 ID | 81 个；其内容版本**全部不同** | 同 ID 不能直接当同版本 |
| 仅 main 存在 | `game-forest-thorn-mouth-geometry-default` | 未纳入此 ID |
| 仅包内存在 | — | 34 个，完整 ID 列表在 `baseline-diff.json.packageOnly`，包括环岛、两/三怪、升井、HQ 和 S 系列 |
| 原生编译字段比较 | 共同项中 80 个存在字段差异，只有 `game-plains-micro-landing` 的原生 Cells 等价 | 比较排除了源哈希、旧相机包围、端口封装等元数据，浮点容差 `1e-7`；不是只比名字 |

主线仍有多轮实施目录；那里的原件不自动成为 `modules/catalog.json` 的正式版本。统一库/1.1.x 的分支改动尚未合入 main。本轮仅记录，不恢复这 34 个模块、不迁移或清理历史目录。完整逐 ID 内容版本、文档 ID、占地、偏移和差异字段均在机器证据中。

已执行：main 82 项的 1,663 个已绑定产物哈希全部匹配；main 82 + 历史包 115 份原件共 197 份通过仓库既有 `validateGenerationContract`（包括内容版本重算）；包内 657 文件集合/哈希、原件 SHA、稳定 ID、版本和 Route 端点一致。历史源文档 ID 在 main 可能是 `generated-*`，正式稳定身份取 catalog 的 `id`；包内文档 ID 已规范化。

包的 schema/Foundation 分别是 `module-package/v1`、规范 1.2、模型 1.0、generationContract 2。原件表达对象与 Route；compiled-content 的 stable_id/source_sha256 均与对应原件绑定一致，是离线原生数据，不能再把它当另一套编辑原件。本轮未对 115 项全部重编译或重做物理认证。对本文两个机制样本，复用了 `godot_package.audit_cases`，main 对象与冻结输入几何匹配。旧 `verify_package` 在干净 main 因 `pcg/prototype/godot` 外部原生资源未安装而中止；这是工具/环境依赖，**不是 Module 物理失败**，详见 [`legacy-verifier.json`](../../evidence/runtime-integration-audit-20261103/legacy-verifier.json)。没有为绕过它而写认证标记。

包内 115 项均为 `qualification.status=verified_scoped`，但 **`mapReady=false`**；共 311 条显式 Route，115 个配置全部是 identity、无换边、无封口的原全口见证。不能把包完整性或生成候选资格等同于整图可玩交付。逐项初态与原认证排除范围见 [`delivery-scope.json`](../../evidence/runtime-integration-audit-20261103/delivery-scope.json)。

依赖与运行范围：

- 包内共享脚本/场景/资源引用和两份宿主锁均纳入逐文件校验；字面量资源引用及已审查的动态敌人白名单均在两份宿主锁/包 manifest 内声明，详见 [`dependency-checks.json`](../../evidence/runtime-integration-audit-20261103/dependency-checks.json)；任意计算资源路径不属于静态证明范围。动态资源以锁定的外部资源集合安装。原图谱 `runtimeFingerprint=434d2227…` 来自带来源信息的作者树，发布时 index 去掉了 `sourcePath`。工具从 manifest 来源提交取回该 index 后成功重算，而非把发布图谱哈希误称为原 fingerprint。
- 原生资格宿主 `12f6cb006d7119598e3235f4ca4f7323e4c9d092`：1,389 个文件；当时主游戏 API 宿主 `5f55716a838a754a938997920ff18cb3b17452b5`：1,600 个文件。后者仅有 API/加载范围，不是全路线新认证。
- 本轮只读核对主游戏 main `30e36c9abe223f26e666ceaf796e3fe9cb58e10f`：原生锁仅 751 文件同路径字节相同，113 改变、525 原路径不存在；API 锁为 1,012 相同、89 改变、499 原路径不存在。主要脚本已移至 `game/`。**路径/字节变化不单独证明 API 坏了，但不能原样覆盖安装旧锁到新主游戏**。选定公开方法和 24×36 身体仍在；没有对整个最新主游戏重跑兼容认证。证据：[`external-source-checks.json`](../../evidence/runtime-integration-audit-20261103/external-source-checks.json)、[`host-api-observations.json`](../../evidence/runtime-integration-audit-20261103/host-api-observations.json)。
- 镜像/部分 Port 在生成阶段可选，不代表经过物理认证；`configurations` 是原有全口/原向见证，原件中的 transform 描述也不是自由使用许可证。包 registry 仅装载原始平移场景，不会处理已物化镜像内容或自动封口；主游戏需要消费 map-gen 的完整物化结果。

## B1. 风铃教学起点：接口点不是已验证出生点

对象：`game-plains-windchime-lesson`。包版本为 `sha256:b2ee44df5422a7b4dd9be1358a075c46cefb00992de802607389f6f94ecfa433`；main 版本是 `sha256:9e932540ae915a982f8e0f0f318d5b6b34345c4112f2243f5ab6c9c99a1350b5`。

| 坐标/内容 | 1.1.0 原件 | 1.1.0 占用矩形局部像素 |
|---|---|---|
| bounds / 场景偏移 | `[0,76,512,384]` / `[0,-76]` | 占用 `[0,0,512,384]` |
| entry 接口 | `[0,268]` | `[0,192]` |
| entry 接岸/内部标记 | `[24,282]` | `[24,206]` |
| 主要地面 | `[0,300,480,40]` | `[0,224,480,40]` |
| 风铃 / 门 | `[170,235]` / `[320,80,24,220]` | `[170,159]` / `[320,4,24,220]` |
| exit 接口 / 接岸 | `[512,268]` / `[496,282]` | `[512,192]` / `[496,206]` |
| 出生候选 | `[48,282]`、`[64,282]`、`[140,282]` | `[48,206]`、`[64,206]`、`[140,206]` |

原件→生成局部：`local = source - bounds.position`。已物化的生成内容直接 `world = origin_blocks*128 + local`；只有装载原始源场景时才使用 `sceneOriginOffsetPixels`，不能再减一次偏移。

**定向验证假设**：未镜像、map-gen stable-v2 默认厚 32 的左口实体封口 `[0,128,32,128]`，只连接 exit；用户未提供这张图的实际封口/镜像/邻居快照，不能称为其整张图验收。

真实 Godot、锁定原生玩家结果（[`godot-probes.json`](../../evidence/runtime-integration-audit-20261103/godot-probes.json)）：

- entry 接口 `[0,192]`、接岸 `[24,206]` 与封口相交；默认 `[0,0]` 也不满足内部完整身体初始放置。没有把它们宣布为安全出生点。
- 三个候选均能站稳，实际开一枪使原生风铃门打开，再走到出口接岸约 `[495.92,205.93]`，HP=5。未射铃对照停在门前约 x=307.99；证明并非绕过原玩法的走直线。
- main 的占地是 `[-128,76,768,384]`，偏移 `[128,-76]`，不是包中的 4×3。相同生成局部候选对应源 `[-80,282]`、`[-64,282]`、`[12,282]`；三个也在同样封口假设下实测通过，到达 main 自己的出口接岸约 `[743.93,205.93]`，未射铃停在 x=435.99。**不能把 main 的右岸/原坐标抄进 1.1.0**。
- main compiled `world_bounds=[-256,-52,1024,640]` 来自旧测试安全/观察范围；占用必须取原件 bounds/catalog，不拿这个字段重新定位 Module。

裁决：缺少独立出生声明/验证的事实成立。map-gen 只验证了 start departure，目前源码明确输出 `anchors.player_spawn.status=UNRESOLVED`；若宿主直接拿 entry 或 `(0,0)` 出生，是未处理未解决输入。候选可供后续起点声明，但本轮不写入源库、不认证镜像、其他封口厚度、实际下一模块接缝或任意初态。

## B2. 环岛 C 封口：已确认生成配置冲突

对象：历史 1.1.0 的 `idea-orbit-choice-001`，`sha256:ee5cdeb5d7672eb1c9fbe9c502273114039a346817b8bf5ea7a7dd65045a1317`；**不在 main 正式 catalog 中**。其 bounds `[0,0,640,512]`、偏移 `[0,0]`，所以本题生成局部数值与这个版本源数值恰好相同，不代表其他模块也可忽略偏移。

原玩法：A 侧落岸，射铃启动环形载台，选时跳向 C 顶台；顶台 `[288,32,64,16]` 是可穿平台，角色中心在约 `[320,14]` 站稳，进入领取区域 `[300,-10,80,56]`。这里身体上缘为 y=-4，会使用 C 口上方净空。包内 6 条有向 Route 存在，但它们的 `resourceProfile.requiredRewards` 全为空。原始资格只覆盖无封口的全口配置，没有 C 关闭后领取的资格。

题设封口 `[256,0,128,32]` 下：

- 对 24×36 身体，封口禁止的角色中心区域为 `[244,-18,152,68]`（封口按半身宽高膨胀）。领取区域**完整包含于禁止区域内**；不仅是某条测试路径失败。
- 原站位身体 y∈[-4,32]，会撞封口；即使站到封口上面，中心 y=-18 又不在领取区域 y≥-10 内。领取实现要求**落地且角色中心点在领取区域**，不是精灵相交或“箱子附近按键”。
- 原生身体的 4 个区内查询均撞到该封口；独立的原内容对照在 `[320,14]` 站稳后由原生服务实际领取 4 金币。对照没有修改/打开被审计的封口夹具，没有移动奖励或添平台。全域几何证明见 [`closure-geometry.json`](../../evidence/runtime-integration-audit-20261103/closure-geometry.json)。

责任判断：

| 分类 | 结论 |
|---|---|
| 缺少声明 | 1.1.0 漏了奖励—Route 关联，也未表达“奖励站位依赖 C 口净空”的封口兼容范围。 |
| 缺少证据 | C 关闭、镜像及任意封口组合没有原生资格，原包通过不能继承。 |
| 明确缺陷 | 本题生成结果的实体封口封死了整个合法领取中心区域，属于生成配置冲突。map-gen 当前仅保护保留 Route 的作者路径，C 相关路线被裁掉、奖励又无关联时，不能保护这个领奖站位。 |
| 宿主语义 | 未提供实际接入分支代码，不能据此判宿主实现错误；正确实现原领取语义也不能在该封口中领取。不能放宽领取/碰撞、移箱或拆封口来掩盖。 |

本轮不修模块。优先让生成器拒绝该组合，选择另一个已满足目标和净空的配置/模块；若设计要求该布局在 C 关闭后仍可取箱，需另提布局修订并变更内容版本、重验受影响路线，不在此次审计中改造。

## C. 五项奖励的逐项结论

精确包内版本、原件、奖励参数及各 Route 的空列表见 [`reward-baseline.json`](../../evidence/runtime-integration-audit-20261103/reward-baseline.json)。下表均针对历史 1.1.0 实际内容；只第一项还存在于 main 正式目录，且 main 内容版本不同。

| 对象 | 已可确认的关联 | 原 1.1.0 缺什么 / 本轮核到什么 |
|---|---|---|
| `generated-75b420…` / visible-cache | `entry-to-exit` → 8 金币 | 6 路线没有领取声明；后续 3 组真实领取后出界记录可复核。能力是 move/jump/**wall_climb**，不能按只有 jump/recoil 的玩家使用。 |
| 两怪 / reward | `A-to-B` → 4 金币 | 原测试 required_rewards=[]、expected_reward=0；后续 3 组实际事件、钱包和出界可复核。 |
| 三怪 / reward | `A-to-B` → 4 金币 | 同上；上口仍依赖外部接应台 `[272,-32,96,12]`，不是模块内新增地形。 |
| 升降井 / reward | `A-to-B` 带取箱策略 → 4 金币 | 原策略 x=192、领取区 x≥196，确实漏箱；后续只改测试行走到 x=220 领取再回 x=192 出井，3 组通过。外邻台 `[144,-32,96,12]` 条件保留。 |
| 环岛 / reward | `A-to-C` → 4 金币 | 原包没有关联；后续 3 组开放 C 配置真实领取后出界可复核；**不支持本题关闭 C**。 |

后续证据是未合入 main 的 `c2e23fec3ec424a7b8e41552bbe2c4ed2a6c8afd` 中的独立报告与不可变归档，**不是 1.1.0 自带资格**。本轮核了报告/归档哈希，解压验证 15 份原始输出的 SHA、原生事件、金额、无重置、领取后完整身体出界，并逐字段确认其 owned Cells 与 1.1.0 相同；附加试验邻台均在占地之外。归档 SHA：`38c5bcd0f214377c2b003ade4e705dfd8503be0d39460e918fb88d266c247d9f`。详见 [`later-reward-evidence-check.json`](../../evidence/runtime-integration-audit-20261103/later-reward-evidence-check.json)。

可确认真实关联；缺的是把事实及精确范围纳入消费者选定版本的声明。没有按距离猜测，也没有删除奖励。当前 main 的不同版本不能直接获得这些资格。其他未测路线、任意相位、能力替代、镜像和封口组合继续 UNKNOWN。最小补证方法是锁定同一内容/能力/配置，用原生领取事件+钱包变化+随后抵达出口复核；三怪/升井需显式外邻夹具，关闭 C 则先拒绝几何冲突而不是重跑撞墙。

## D. 机制接入资料

见 [mechanisms.md](mechanisms.md)：两个完整编译样本、main 与历史包各自精确版本、平台/锯/门参数、原生 API 和宿主服务。只读样本自动从已核 SHA 的 ZIP 复制到审计证据目录，不是恢复模块或第二套源库。主游戏不需要运行旧 `demo.tscn`、不使用会创建玩家/全局服务的演示宿主。

## 交接行动与是否需要新包

给 map-gen：

1. 继续锁 1.1.0 + ZIP SHA，不从 main 或后续包静默替换。对版本不同的同 ID 拒绝混用。
2. 将 `player_spawn=UNRESOLVED` 保留为未解决输入。按实际封口、方向、玩家配置验收内部候选，再输出明确源版本绑定的出生数据；不要用 departure/entry 代替。
3. 封口检查同时保护奖励领取/站立净空和必要机制，不只检查剩余 Route 折线。拒绝本题 C 组合；保持奖励，不以删奖励消除冲突。新配置仍标物理 NOT_RUN。
4. 后续 5 项关联需显式选择声明版本后回放固定 seed；使用 wall_climb 等真实能力和三怪/升井外邻约束，不推断反向或镜像资格。

给主游戏：

1. 未解决出生时拒绝开局或报告未完成，不能默认为 `(0,0)`/entry。按实际输入验证本报告候选；本轮不是最新主游戏完整起点认证。
2. 生成内容已物化时只加地图 Block 原点；禁止重复加源偏移或重新从 source_scene 覆盖物化 Cells/封口。
3. 用自己的玩家、FrameDamagePolicy、钱包和生命周期；实例 ID 持久化，保持本地敌人/奖励 ID。按“落地+中心在区域”触发原生领取，保证重复调用不重复发奖。
4. 用当前 `game/` 路径下原生类接入平台、锯、门，先做本文机制小样与卸载/重载/重复领取验收。不要把旧宿主资源锁覆盖到当前工程，也不要直接复制旧演示宿主。
5. 在自己的实际接入分支上复验未实现机制、封口和整图；本轮未获得该分支/实际 seed 快照，无法给它贴通过标签。

给 map-edit：明确 main 正式源库与已发布包的治理关系，独立审阅未合入的统一库/后续证据；不在此次审计恢复、迁移或合并。给接入方保留固定版本资料，另行提出缺少声明的最小修订。

**此次审计不需要新包，也未发布。** 封口选择及未解决出生的消费问题可先由下游处理。若需要机器可读的新奖励关联/安全出生范围，或让包直接支持最新主游戏资源/API，则需要另立最小修订：选定正式源版本，保持稳定 ID；只补已有 Route 的 requiredRewards/明确作用范围，约定出生数据与源/配置绑定，更新适配器资源依赖映射并复验。布局真需改时单独列出 affected Cells/Route、递增内容版本；依赖/API变化需重跑原生装载/机制/领取/生命周期验收。完成来源合入决策、固定宿主及下游回放后，才考虑显式升级模块包，不能自动把当前 main 或后续 1.1.1 当作替代品。
