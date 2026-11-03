# 主线交接与按需维护

2026-11-03 完成已交付成果的审阅与依赖合并。main 原为 `178c40164c2f7371ce1c8a56cde658e84a4f42c2`；五项成果合入点为 `a369ff87df282a74a2a0948a9233eb761fd7e7cb`，其文件树与受审 PR6 head 完全一致。本文件及同轮核验记录是随后新增的主线收口文档，不是新的算法、交付版本或包源码身份。

## 合入结果与审阅

| PR | 成果 | 原 head | 普通 merge commit |
| --- | --- | --- | --- |
| [#2](https://github.com/zhipijun1996/map-gen/pull/2) | Python 参考包 0.2.0 | `0d338c2309d4e17bd8e9b128f745eb93938e99b2` | `231b6ffb041f1069c9ff39437a52dd2af288871f` |
| [#3](https://github.com/zhipijun1996/map-gen/pull/3) | Godot 候选 0.3.0 | `93c5221a9708d079c2864f3c14b415e81bb5de07` | `cdeea80d3f04f3d1a2a0f799308cf2e97d23e601` |
| [#4](https://github.com/zhipijun1996/map-gen/pull/4) | 调度优化 0.3.1 | `a8efe1db0a5557fdbc4956f95f3bc7763c29e3ff` | `893a4cc9dbf9c56a968e1a78a33f5997bc9b1f7a` |
| [#5](https://github.com/zhipijun1996/map-gen/pull/5) | 奖励空间修正 0.4.0 | `6bf07ab5a655ea056461b935ae4354e15ef83482` | `deba9226c887dd04657c1f32229cf305b874739e` |
| [#6](https://github.com/zhipijun1996/map-gen/pull/6) | 性能修订 0.4.1 | `c35871446cc0a3939e1a38171435f42cdc64a359` | `a369ff87df282a74a2a0948a9233eb761fd7e7cb` |

逐次将已包含父成果的子 PR 目标改为 main，核对实际差异与原依赖差异相等，再以保留祖先的普通 merge 合入。每次核对双父提交与最终树，无 squash/rebase、无冲突解决、无 reset/覆盖用户修改。依赖分支继续保留。

审阅涵盖公共协议/引用解析、GDScript 数据边界和 RNG/数值/失败合同、增量预载与取消、普通和目标奖励的充分排除检查，以及 0.4.1 缓存绑定/完整文件核验/排序和图缓存。未发现本次合入的新阻塞；已有 candidate 限制保留。原 0.2.0、0.3.0、0.3.1、0.4.0、0.4.1 包均重新核对 ZIP SHA 和 manifest 的全部文件摘要。

各 PR head 和五个 merge commit 的 GitHub check runs、commit statuses、workflow runs 均为空；仓库没有对应 workflow。这里没有自动 CI 通过结论，也没有新增 CI 工程。复用各版本已归档的完整回归/性能/Web 原件，本轮补做锁定工具链的仓库外独立重放、源身份/19 文件/模块锁/引用解析、祖先/树对照和仓库保护检查。

本轮 [审阅及包核验](../validation/main-closeout-20261103/review.json)、[合入及 CI 实况](../validation/main-closeout-20261103/merges.json)、[独立 verify_bundle 原日志](../validation/main-closeout-20261103/verify_bundle.log)。旧文档中“尚未合并”等文字属于当时工作线快照，保留原件，不改写历史收据。

## 给 gunman-rush 的固定来源

使用 **0.4.1 candidate**，目标 `godot-standard-gdscript`，算法 `stable-v3-reward-space`，实现 `mapgen/gdscript-candidate-0.4.1`。Python 0.2.0 继续为参考实现；独立 0.4.1 是实际 GDScript 运行组件，仍不标生产就绪。

不可变下载 URL：

<https://raw.githubusercontent.com/zhipijun1996/map-gen/c35871446cc0a3939e1a38171435f42cdc64a359/runtime_packages/releases/0.4.1/mapgen-godot-candidate-0.4.1.zip>

- 仓库路径：`runtime_packages/releases/0.4.1/mapgen-godot-candidate-0.4.1.zip`，3,608,539 字节。
- ZIP SHA-256：`f5c84e5e51dff01d16429783b957c0d5214056b9d2fea47a830baac12ecedb4e`。
- 包实际源码 commit：`8eefdbd140ce10defe1570ab8eefb6729382f8b3`。
- 原始产物提交 / release head：`c35871446cc0a3939e1a38171435f42cdc64a359`。
- main 合并及文档收口提交只是新的仓库身份，不能替换上述包内 source 或产物身份。
- 模块仍为 **1.1.0**，SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`；公共地图仍为 **runtime-map/v2**，请求/配置/结果 Schema 仍为 v1。

包内 `manifest.json` 列出全部文件摘要、19 个 `addon_files`、完整模块锁与源身份。`samples/success/`、`samples/gears-930007/`、`samples/failure/` 保存精确输入和完整结果；两个成功样例还包含独立 map/content_store 及全部 89 个引用文件。样例只供验收，不参与运行时求解。

独立验证命令（PACK 是解压包根目录的绝对路径）：

```sh
GODOT --headless --path PACK --script res://tests/verify_bundle.gd -- PACK/tests/dependencies/modules.zip
```

本轮在仓库外临时目录，用原锁定 `4.7.2.stable.custom_build.gunman_sd1.ed1daf0bf` 实际执行，179 项通过。引擎二进制 SHA `eeaec2b65dc3234168be1e1cbcc89731514bbb78dfb2c1b502920c50830a0638`。19 个运行文件与包内实际 source commit、PR6 及受测源向量一致；本轮没有改包或重建版本。

## 0.4.0 → 0.4.1 升级步骤

以下准确位置来自已核验的 gunman-rush PR129 `46eb3960a592374b5fb99d7df588962a3680f86b`，完整只读来源见 [host_calls.json](../performance_revision/upstream/host_calls.json)。下游如已有新提交，应核对相同准入职责的当前位置。

1. 先校验旧 0.4.0 的 18 文件原 pin；明确执行本次升级，按新包 manifest 安装整个 addon。更新原文件并新增普通数据脚本 `derived_library.gd`，新锁共 19 个 `.gd`。禁止混装、盲覆写或沿用旧 18 文件白名单。
2. `tools/install_mapgen_candidate.py` 的 archive URL/SHA、implementation、package version、19 文件摘要和输出 lock 同步新身份。旧升级分支只支持 0.3.0→0.4.0，需明确增加本次 0.4.0→0.4.1 的旧新 pin 校验。保留原模块 ZIP 和两个原请求/配置字节，不下载 latest。
3. `experiments/generation/runtime_map_generation_job.gd:340` 的 `lock.version` 准入同步 0.4.1，保留与 Protocol 实现/算法的一致性检查。
4. `game/world/levels/providers/runtime_map_v2_provider.gd:143` 的实现准入同步 `mapgen/gdscript-candidate-0.4.1`，`:151` 的 algorithm package version 同步 0.4.1。算法名保持 `stable-v3-reward-space`，provenance 的 ZIP SHA/source commit/release head 使用上述真实来源。**只改 JSON 锁会被固定下游拒绝。**
5. 原请求/配置、90 秒搜索上限、候选预算与目标不改；沿用 `advance(1)`、每 tick 至多 128 单位和软 8ms。以新 Protocol 计算真实指纹，重新执行主游戏原双 fresh/300 秒 consumer，并分别记录 SDK、让帧、装载/物理和工具时间。

API 与地图转换合同兼容，主游戏无需重写求解器、调度循环或装载架构，也不复制算法。`PreloadJob.create(path, sha)` → 逐帧 `advance` → 通过后的 library 复用 → `GenerationJob.create(request, library, config)`；继续 progress/cancel/is_done/result，只有 PASS 有完整 map/content_store。可选第三参数 false 强制源 JSON 解码，普通调用无需增加参数。

纯算法不依赖 LevelRequest/LevelPlan、SceneTree、Factory、玩家或钱包。run/stage/actor token 留在宿主信封；bindings/source_record、物化内容的准入、节点装配与实际物理由主游戏拥有。一个单位仍为 16 检查点，不能解释为毫秒。

## 指纹、恢复及收益边界

实现身份参与确定性指纹。新 request_fingerprint、map_id、来源/宿主内容身份不能冒充旧版本；持久恢复不得复用旧来源身份，也不能回填旧 fingerprint。0.4.1 与 0.4.0 的完整结果仅分离明确的实现身份和耗时，布局、完整内容、Route、镜像、封口、奖励、随机状态和搜索计数不变。

| seed | 0.4.1 request_fingerprint | 展开数 |
| --- | --- | ---: |
| 930001 | `f1d24aa1d5d8f3087202b3e933708d4f42a74cb1465947413e40e5037391caf8` | 87175 |
| 930007 | `84d94b05e86a00a507ef0de8cac9f407a6dbd9dd7662a505ac182402c8ead918` | 88856 |

复用的独立实测 Web 对照：预载 26.374→4.246s；930001 生成 57.561→34.501s；930007 生成 51.814→27.192s。原生生成 active 降低约 36%，Web 约 39%/47%。这些是既有独立数据项目的观察，**不是本轮重跑，也不是主游戏实际收益**。完整 [性能与局限报告](../performance_revision/REPORT.md)、[0.4.1 交付原件](../performance_revision/HANDOFF.md)、[47 例完整对照](../validation/performance-0.4.1/final/replay/summary.json) 和 [实际 Web 原件](../validation/performance-0.4.1/final/web/summary.json) 均保留。

Web 最大单次推进约 32ms、原生冷缓存加载约 75ms；软 8ms 不保证硬帧时限。独立旧版约58s与原主游戏约72s的差距未因果归因。主游戏218MB PCK、原双 fresh/300秒、全图物理/跨模块 Motor、手机与硬帧保证仍不能由本仓库证据代签。失败依旧无可用 map/content_store；不降目标、删内容或放宽预算来获得通过。

## 后续维护

本轮没有修改主游戏或 map-edit，没有升级模块1.1.1、增加随机危险/随机布怪、部署网站或另发版本。0.1.0固定地图包、所有旧算法包、冻结预期及原验证/失败证据保持原样。map-edit 对本次换锁无新增字段需求；已有全图玩法与资格缺口不因主线合入自动消失。

转入按需维护：等待主游戏提供明确的兼容、性能或生成问题及可复现来源，再处理对应任务；不主动展开下一轮基础工程。
