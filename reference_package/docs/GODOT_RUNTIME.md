# Godot Standard / Web / 桌面算法实现建议与验收

本轮只交付可执行 Python 参考、冻结成功/失败样例和兼容向量。没有 Godot 生成器，没有通过引擎、Web 导出或设备测试；不得因模块 ZIP 包含 .gd 文件就标记为 Godot 算法包。

## 推荐路线及边界

优先由 map-gen 维护纯数据 GDScript 组件：输入仍为公共请求、配置和已加载模块库，输出仍是结果/map/content_store。它不认识主游戏 LevelPlan、Node、Scene、RunSession、钱包、Factory 或伤害服务。gunman-rush 维护 Provider→内部 Plan 的适配及 Stage/Runtime 消费。

Godot Standard 和 Web 不以运行 Python 子进程、C#/.NET 或额外本地扩展为第一方案；桌面也用同一 GDScript 核心。先跑通同步数据函数，再按主游戏调度需求封装增量 job/step。Web 不能默认依赖 worker/线程能力，可按固定数量操作切片；切片只暂停，不额外消耗 RNG、不重排候选。场景创建与游戏服务仍在主线程。

先实现编译库解析/索引、整数占用与接口匹配、实际图和封口规则，再移植评分、生长、回退、奖励/Boss 和导出。冻结样例先供宿主装配验证；算法语言移植作为独立版本和证据，不把第一张地图加载成功当作算法移植完成。

## 必须保持的确定性细节

1. **RNG**：现有 `python-mt19937-v1` 是 CPython Random 的完整调用语义，不只是 MT19937 的名字。包括整数 seed 的绝对值/多字初始化、53-bit random、getrandbits 的位/word 顺序、randrange 的 bit_length 与拒绝采样、shuffle 的调用顺序、uniform 的运算顺序、getstate/setstate（版本3及624 words/index）和回退时恢复点。Godot RandomNumberGenerator 不能只设同 seed 就代替；`x % n` 不能代替 randrange。即使候选只有一个，参考调用仍可能消耗 RNG。
2. **数值**：搜索位置用整数 Block/doubled-Block；GDScript float 是 binary64，但常规 Vector2 可能经 float32，搜索阶段不能提前转 Vector2。保持 scalar 运算次序、`log/hypot`、中间舍入与分数比较；向量文件同时保存浮点值和 binary64 bits。不同 libm 的差异若影响排序必须报告，不能加 epsilon 或改权重让旧样例看似一致。
3. **顺序**：保留 catalog.modules/ports/实际候选的枚举顺序，以及原代码明确 sorted 的位置。Python 稳定排序的分数相等时保留原入列顺序；Godot 不保证等价稳定 sort 时，使用原入列 index 作次序，而不是新增按模块名排序。集合仅作成员关系的地方不能引入另一套可见枚举顺序。
4. **指纹编码**：现有 canonical JSON 的 int/float 表示、Unicode、key 排序、数组顺序与 UTF-8 字节是协议一部分。Godot JSON 的数字解析/字符串化不自动等于 Python canonical；不能直接把 JSON.stringify 的 SHA 认作相同。对 Schema 整数显式保真，对非整数/数值 token 与边界提供兼容序列化或明确新的实现身份。Python seed 当前不受 int64 限制；GDScript 若只支持某个范围，必须明确拒绝/声明兼容域，不能截断。
5. **预算**：候选几何求值、lookahead/预留也计入原操作预算；计数点、超过上限的边界、终端份额、修复与回退次数不能改变。操作切片与 UI 进度不改变内容。墙钟/外部取消不是内容确定性的保证；分别验证受控 clock/操作点的终止和真实平台响应性，不改默认90秒或目标来掩盖性能问题。
6. **状态**：输入固定、库不可被请求修改、缓存/RNG 属于 job；回退恢复快照和 RNG 后才能重试。取消不发布部分图、不换 seed、不回退小图。进度只是值快照，不把 SceneTree 或 callback/service bag 放入公共请求。

`determinism/vectors.json` 是本轮真实 CPython 执行产生的可运行基准，含 0、负数、930001、大于 int64 的整数 seed、随机操作序列/恢复、等分排序和实际 shape_cost。`reference.py verify` 会重算它。它不是已经通过的 GDScript 实现。

## 迁移验收门槛（先定义，再实现）

| 层次 | 可执行验收 |
|---|---|
| 协议 | 拒绝未知 Schema/实现/配置、缺失引用、库 SHA 不符；成功有完整 map/store，所有失败无可用图 |
| RNG/数值 | 对向量逐值和 binary64 bits 核对，含保存恢复、边界 seed、相等分数稳定顺序；不支持域明确拒绝 |
| 参考重放 | 当前默认成功/真实失败请求完整重放；拓扑、位置、镜像、Route、封口、原有敌人/奖励、主路及操作计数与冻结基准比较，不修改旧预期 |
| 扩大回归 | 既有40 seed 固定输入及未见请求集；所有成功、失败、预算状态保留，不筛失败。新增实现和原参考各自产生独立证据 |
| 调度 | 相同请求不同 step 大小、暂停/恢复、并发请求结果一致；受控操作点取消/预算无残留可用图 |
| Godot Standard | 实际 headless 运行纯数据核心、Schema/内容静态检查及真实 Runtime/Factory 消费测试；不把 Python 测试当引擎结果 |
| Web/桌面 | 各做实际导出和运行，Web 验证无子进程/网络模块下载依赖及主线程切片；记录时间、操作数、包/内存、取消响应和实际内容哈希 |
| 玩法 | 主游戏完成出生、跨缝、镜像/封口、奖励独立领取与恢复、Boss/离图；静态通过不代签动作或用户手感 |

语言实现应获得独立实现/算法包版本。新实现标识参与既有 fingerprint，所以即使布局相同，map_id/身份摘要也可能按声明变化。迁移报告必须分列身份差异与地图内容差异：身份按各实现规则验证；冻结公共布局/图/内容及搜索计数另行严格比较，不把 private Python 调试容器强加给 GDScript。

本包的完整确定性重放是 Python 参考自身的检查，不能直接拿它忽略新实现身份后宣称“逐字节全等”。旧文件永不改写；新实现若改变布局/排序/随机/数值行为，必须新建实现/算法版本和独立预期，提供同输入旧新差异，不能改旧向量、删字段或放宽检查冒充兼容。发布实际 Godot 包时再把已经验证的新实现身份纳入兼容表/Schema允许值；本轮不预注册一个不存在的运行时。
