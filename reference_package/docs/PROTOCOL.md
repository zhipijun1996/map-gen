# 公共生成与参考交付契约

公共生成协议由 map-gen 拥有。以下均复用已存在的名称和语义：

| 入口 | 版本/含义 |
|---|---|
| `generate(request, library, config, hooks=...)` | 同步纯数据 API；本包是 Python 参考实现 |
| 请求 | `mapgen/generation-request/v1`，`schemas/request.schema.json` |
| 配置 | `mapgen/generator-config/v1`，`schemas/config.schema.json` |
| 结果 | `mapgen/generation-result/v1`，`schemas/result.schema.json` 描述已有输出 |
| 地图 | `mapgen/runtime-map/v2`，`schemas/runtime-map.schema.json` |
| 实例内容 | `pcg/compiled-module-content/v1`，由锁定模块库完整变换后交付 |

`mapgen/reference-package/v1` 只是外层产物 manifest，不是第二套生成请求、地图或主游戏 Plan。旧固定地图包 0.1.0 的 v1 文件、哈希和历史预期原样保留。

## 身份与兼容性

包版本 `0.2.0`、算法 `stable-v2`、实现 `mapgen/interface-v1` 分别表示分发版本、搜索语义和参考实现身份。新增打包/验证工具不改变原算法源码、默认请求/配置和生成指纹。manifest 的 source.commit 是包含打包输入的真实代码提交；样例 provenance 的 algorithm_source_commit 是被逐文件核对的原算法基线，两者不混用。

模块版本、ZIP SHA、原 catalog SHA、源 commit、package/catalog Schema 和 Foundation 版本分别从原锁及模块 manifest 记录。兼容仅限这些条件和当前已实现的编译格式；1.1.0 的本地证据不自动扩展为主游戏最新 main、任意接缝、镜像/封口或完整玩法认证。`runtimeFingerprint` 和宿主锁可从原 ZIP manifest 查询，不建立另一份 actor/Cell 注册表。

## 输入及指纹

请求是生成开始时的值快照：seed、能力及净空、真实起终点模块/Port、起点 Block 位置、区域/模块过滤、AIR 阶段候选。配置包含目标、形态、评分、搜索和预算；默认候选库包含全部 115 个模块，不能为了映射主游戏 plains 就静默把冻结请求的空区域过滤改成“平原”。

能力名用 `shot_recoil`，不把内部 recoil 别名交给宿主。净空来自真实玩家外形，不是可随意减小以通过检查的难度参数。最低必要能力和原生档位仍受源证据范围限制。生成不逐帧读取玩家血量、资源或机关状态。

复用 `mapgen.contracts.canonical` 的 UTF-8 编码：JSON keys 排序、无空白分隔、`ensure_ascii=False`、禁止 NaN/Inf。数组顺序保持，整数和浮点的 JSON 表示不混为同一字节串。

- `request_sha256 = SHA256(canonical(request.to_dict()))`。
- `config_sha256 = SHA256(canonical(config.to_dict()))`。
- 原有 `request_fingerprint` 的含义保持为 `SHA256(canonical({request, config, library_sha256, implementation}))`，其中实现为 `mapgen/interface-v1`。它已经包含配置和模块库，不能改称仅 request 的摘要。
- `map_id` 仍为 `map-` 加完整输入指纹前 24 位。它是生成身份，不是地图内容哈希或主游戏旧存档哈希。
- 样例 `map_content_sha256` 绑定 canonical `{map, content_store}`；完整确定性结果哈希只去除 `metrics.generation_seconds`。不得再删搜索计数、失败状态、内容或未知项来获得一致。
- manifest.files 保存实际文件字节 SHA；这与 canonical 语义摘要是两种明确不同的校验。ZIP 自身 SHA 在外层 sidecar，不能循环写进 ZIP 内。

来源完整性依赖可信仓库提供的 ZIP SHA，文件清单不是签名或引擎认证。所有核心配置/请求字段必须显式提供，未知字段、版本、策略名和不兼容绑定会拒绝。

## 结果、引用与坐标

`GenerationResult.to_dict()` 原样提供 status、request_fingerprint、map、content_store、metrics、diagnostics。成功地图的每个 `content_ref` 必须在 content_store 中唯一存在；不允许缺件、未用额外内容、绝对路径或 `..`。参考包还提供相同数据的 map.json、content_store.json 与逐引用 JSON，校验器要求它们与完整 result 一致。

`content_ref` 在内存 API 中是 store key，在样例目录中才是相对该样例根的文件路径。`source_scene_ref/source_compiled_ref` 的 module_pack 前缀指向锁定模块 ZIP 内的原资源，供追溯/行为复用；它不是另一份已装配地形，也不能当作每实例物化内容。

Block 大小取实际库，本样例 128px。位置以所属矩形左上角为局部零点，X 右/Y 下，`world_pixel=origin_blocks*block_size_pixels+local_pixel`，允许负原点。实例内容、Port、路线及封口已归一化和完整水平镜像；镜像标记用于追溯，不再次变换内容或应用 source_affine/源场景偏移。镜像不反转 Route 身份或 from/to。

全部 Port 使用真实 ID、变换后的 face、surface 和初始 permission。连接 a/b 是端点排序，方向必须由出发 out/到达 in 权限推导。未声明的 Route 不补齐；未用 Port 全部实体封口，保留路线须避开封口和玩家净空。三条主路是不同模块序列，不是三条完全不共享的玩法路线。

## 生命周期、失败与宿主服务

`GenerationHooks` 是调用 API 的独立进度/取消适配，不塞进 JSON 请求或主游戏 LevelRequest 的服务袋。checkpoint/failure 回调得到副本；调用方修改副本不能改搜索状态。同步函数可由宿主调度，主游戏 SceneTree/工厂/服务不进入搜索线程。

候选求值前检查取消，然后递增操作数；超过上限时可记录上限+1 并返回 BUDGET_EXHAUSTED。墙钟按配置的候选检查间隔检查；null 禁用墙钟，不禁用操作预算。它不是全程即时抢占保证，不能承诺跨设备在相同墙钟边界有相同终止点。宿主取消/超时必须单独记原因，不伪称模块库无解。

| 状态 | 消费规则 |
|---|---|
| PASS | 校验后消费 map 与完整 content_store |
| INVALID_INPUT | 输入/绑定/库不兼容；不运行替代请求 |
| SEARCH_EXHAUSTED | 有界搜索未完成，不是 UNSAT 证明 |
| BUDGET_EXHAUSTED | 操作或墙钟预算耗尽，保留原因/计数 |
| CANCELLED | 取消，丢弃结果，不发布诊断候选到游戏 |
| REJECTED | 最终静态审计未过 |
| ERROR | 实现/回调等异常，保留诊断 |

所有非 PASS 结果 map 为 null、store 为空，失败样例不写可用 map/content 文件。上层若采用新请求重试，必须是显式有身份的另一次请求；本包不换 seed、不减目标、不自动回退小图。

外层 `reference.py verify/replay` 打印的是校验收据，不是 GenerationResult。其 REJECTED 表示文件/参数/契约检查失败，不应当作一个可装配的生成结果；生成命令真正运行 API 后才返回其生成状态。

宿主拥有持久 run_id、玩家、钱包、伤害、epoch、领奖/恢复与工厂。对象身份按 `run_id / map_id / instance_id / local_object_id` 限定，重复模板不得共享生命/领取事务。保存实际生成结果及版本，不升级后仅凭 seed 重建旧图。

出生点仍 UNRESOLVED；Boss 标记只描述入口/战场职责，具体本体、封印、战后完成由宿主明确绑定。主游戏内部 LevelPlan、Stage、存档和服务类型不进入公共协议。

## 后续附加危险边界

地图级移动齿轮由 map-gen 后续决定布置并输出，map-edit 提供真实模块的边界/路线/禁入与已认证约束，主游戏执行轨迹、碰撞、时钟、伤害和恢复。本轮不布置、不增加随机布怪，也不预填未使用的危险数组/大量预留字段。已有 content 内的 saws/moving_platforms 是模块作者内容；gear-seal/1 是未用 Port 的封口，都不能冒称已实现的地图级移动齿轮系统。
