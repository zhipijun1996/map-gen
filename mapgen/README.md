# 显式输入的地图生成核心

本目录是可独立复制/安装的 Python 生成组件，使用标准库，保留 `stable-v2` 的默认搜索行为。运行时不导入任何 `experiments/`、`prototype/` 或 `delivery/` 文件，不修改 `sys.path`，没有全局模块库/玩家能力，也不下载模块或读取默认配置。

版本化分发、完整 runtime-map/v2 样例与主游戏交接见 [Python 参考算法包 0.2.0](../reference_package/README.md)。它补充外层包 manifest、现有结果 Schema 和 `mapgen.artifacts` 的完整结果/引用校验；算法、默认配置和生成指纹规则不变，Godot 运行时仍待实现。

算法、请求和默认参数分别维护：

- [调用 API](api.py)：`generate(request, library, config, hooks=...)`。
- [请求样例](../examples/request-930001.json)：seed、能力/净空、起终点、起点位置、模块筛选及真实 AIR 腿候选。
- [参数配置](../profiles/stable-v2.json)：目标、形态、评分、随机策略、搜索预算和封口厚度。
- [输入校验](contracts.py) 与 [JSON Schema](../schemas)：明确版本，拒绝遗漏、未知字段和不支持的策略。
- [回归结果](../validation/interface-v1/replay/summary.json)：40/40 与冻结版本一致，不通过换 seed 或降低目标实现。

## 最小调用

```python
import json
from pathlib import Path
from mapgen import generate, GenerationRequest, GeneratorConfig, ModuleLibrary

# 文件访问由调用方负责；核心只接收已解析的快照和库。
request = GenerationRequest.from_dict(json.loads(Path("examples/request-930001.json").read_text()))
config = GeneratorConfig.from_dict(json.loads(Path("profiles/stable-v2.json").read_text()))
library = ModuleLibrary.from_zip(
    "module-pack.zip",
    expected_sha256="5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723",
)
result = generate(request, library, config)
if result.status == "PASS":
    runtime_map = result.map
    content_store = result.content_store
else:
    print(result.status, result.diagnostics)
```

模块 ZIP 是用户明确提供的输入；也可用 `ModuleLibrary.from_bytes(data, expected_sha256=...)` 传入宿主已持有的字节。库可在多个请求间复用；每次生成拥有自己的 PreparedLibrary、能力、参数、随机状态和缓存。输入对象从字典创建后为不可变快照，调用方后续修改原字典不会改变已创建请求。

`from_dict()` 的结构错误抛出 `InputError`，调用方可在 UI/API 边界展示。`generate()` 再校验输入并返回结构化结果，原生模块或起终点不兼容为 `INVALID_INPUT`。完整输入指纹包含请求、配置、模块 ZIP SHA-256 和实现版本；同 seed 的不同能力/目标/模块版本不会冒充同一次生成。

## 命令行是 I/O 适配层

```sh
python -m mapgen \
  --request examples/request-930001.json \
  --config profiles/stable-v2.json \
  --library .cache/legacy-real-v2/modules.zip \
  --library-sha256 5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723 \
  --out /tmp/mapgen-new-930001
```

所有输入路径和库哈希必填，没有隐藏的当前实验目录。缺少 ZIP 时先由宿主准备；0.1.0 交付包的 `dependencies/` 内含原 ZIP。CLI 拒绝覆盖已有输出目录；成功退出码 0，其余生成状态退出码 2。可运行 `python -m pip install .` 安装核心和 `mapgen` 命令；profile、请求及 Schema 留给调用方明确选择，不会作为隐藏默认读入。

成功输出 `result.json`、`map.json` 和 `content/Mxx.json`。失败只输出带诊断的 result，不生成伪装为可用地图的 map。内存 API 不写磁盘，也不要求先构建交付 ZIP。

## 请求字段

| 字段 | 语义 |
|---|---|
| `seed` | 整数种子，不被替换 |
| `player.abilities` | 原生能力名称数组，如 `shot_recoil`；内部兼容别名不作为公共输入 |
| `player.clearance_half_extents_pixels` | 作者路径对封口的保守净空，默认 `[12,18]`；应取自真实玩家外形，不是降低难度的滑块 |
| `terminals.start/boss` | 真实模块 ID 与真实 Port ID；显式检查方向权限和 Boss arrival 声明 |
| `start_origin_blocks` | 起点占用矩形的整数 Block 原点，默认 `[0,0]` |
| `module_filter.regions` | 按 catalog 的真实区域字段过滤，目前名称为“平原”“森林”；空数组表示全部 |
| `module_filter.include_ids/exclude_ids` | 真实模块 ID 白名单/黑名单；空白名单表示全部，未知 ID、重叠和过滤掉终端都报错 |
| `air_loop` | 是否执行 AIR 阶段、实际入口腿/回程腿模块 ID；要求源模块声明对应材质的 Route，不制造接口 |

默认请求保留旧实验的全部 115 个候选模块，因此 `regions=[]`，不是只包含平原。改为 `["平原"]` 会筛成 106 个模块，属于明确改变输入，布局自然可能改变。所有模块仍统一考虑完整水平镜像，没有 per-module 镜像白名单。

默认 AIR 阶段保留参考版的随机调用顺序，但入口/回程腿候选为空，不宣称生成了真实 AIR 回路。显式指定真实模块后仍须通过有向路线、连接、净空和整图检查。

能力仅用于静态 Route 过滤；原作者能力/原生玩家档位证据保留，未提供 Godot 动作与连续资源认证。生成开始后固定请求，不追踪实时血量、精力或机关状态。

## 参数分组及范围

全部参数来自配置文件，没有在算法中回填默认值。固定的数学/契约定义（二维坐标、Port 奇偶性、方向权限、节点模型等）属于算法不变量，不作为可关闭的检查开关。

默认 profile 作为回归基准。业务调参另存新的 JSON 并显式传入，旧输出和旧预期原样保留，不为了迎合新参数改写历史结果。

| 分组 | 参数与默认值 | 影响 |
|---|---|---|
| `goals` | `growth_target=32`、`reward_target=6`、`main_paths_required=3` | 生长实例数包含起点；最终实例还包含闭环/Boss/奖励。奖励和路径数量已贯穿搜索、装配、审计和导出 |
| `shape` | `target_ratio=1.5`、`soft_tolerance=1.35`、`max_aspect=3` | 宽/高软目标、容忍带、最终长短边比硬门槛 |
| `scoring` 形态 | `perimeter=.35`、`aspect=60`、`left_bias=0`、`height_bias=0` | 周长、形态和坐标偏好 |
| `scoring` 生长 | `auto_connection=24`、`repeat_module=5`、`growth_noise=3` | 自动接缝奖励、重复惩罚、随机扰动幅度 |
| `scoring` 扩展 | `usable_exit=8`、`bidirectional_exit=3`、`terminal_slot=2`、`dead_end=-24`、`vertical_exit=8`、`distinct_direction=4` | 真实 Route 与几何后继相关评分 |
| `scoring` 奖励 | `reward_reserve=5`、`reservation_repeat=5`、`reservation_area=.1`、`reward_noise=4`、`reward_near_radius=8`、`reward_near_penalty=5` | 预留见证、奖励候选排序与分散；半径单位为 Block 原点距离 |
| `scoring` 其他 | `closure_noise=2`、`boss_distance=1` | 闭环排序扰动、Boss 远近排序 |
| `search` 生长 | 前沿 22、精查短名单 18、保留候选 5、预留起始实例数 24 | 分别由 `growth_frontier_limit/growth_shortlist/growth_choice_count/reserve_from_growth_count` 控制 |
| `search` 闭环 | 尝试 3、深度 3、Beam 18、源前沿 24、目标距离 40、剩余距离 32 | `close_attempts/close_depth/closure_beam_width/closure_source_limit/closure_target_distance2/closure_distance_limit2`；末两者为 doubled-Block Manhattan 单位 |
| `search` 终端 | Boss 候选 5、奖励候选 5 | `boss_choice_count/reward_choice_count`，不再复用生长候选参数 |
| `search` 预算 | 候选求值 500000、90 秒、检查间隔 256、回退 128、深度 3、终端状态 128、修复 8 | `candidate_expansion_budget/per_seed_timeout_seconds/budget_check_interval/max_growth_backtracks/max_rewind_depth/max_terminal_states/max_layout_repairs` |
| `seals` | `thickness_pixels=32` | 实际封口向内厚度，须小于模块 Block；开口大小从真实库的 Block 尺寸取得 |
| `random` | `python-mt19937-v1`、`uniform_top_k` | 第一版明确只支持参考版随机算法和选择规则；不支持的名称报错，不静默忽略 |

旧版共享的生长/闭环短名单、Boss/奖励候选数已经拆开。默认相同数字保持参考行为；改动其中一个不再暗改另一阶段。

`growth_target>=2`，`reward_target>=0`，`main_paths_required>=1`。正整数搜索项必须为正，闭环次数/修复次数/生长回退总数可以为 0；超时为正秒数或 null（禁用墙钟限制）。浮点参数必须有限，权重除 dead_end 外非负。未知参数/拼写错误直接拒绝，详细结构见 Schema。目标过高可能返回搜索/预算失败，不代表该目标或模块库已证明无解。

当前预留分数在前 K 个候选确定后重排，而首选仍是均匀抽样；增大 `reward_reserve` 不会变成按分数加权抽样，主要改变顺序与后续回退。本轮保留这项已测行为，任何选择策略调整应另建算法版本。

## 输出和接入边界

`GenerationResult` 返回 status、fingerprint、map、content_store、metrics、diagnostics。状态为 `PASS/INVALID_INPUT/SEARCH_EXHAUSTED/BUDGET_EXHAUSTED/CANCELLED/REJECTED/ERROR`。失败时 map 为 null，content_store 为空，没有换 seed、减目标或备用地图。

成功 map 使用 **`mapgen/runtime-map/v2`**：真实模块/Port ID、实例位置、已物化内容引用、完整 Port、封口、有效 Route、实际图、参考主路、输入快照及未完成的玩法锚点。content_store 是以 content_ref 为 key 的完整编译内容字典，可直接传递，不必写 JSON。三/四条主路指不同模块序列，不是互不重叠的玩法路线。

v2 从固定交付格式中移除了 0.1.0 版本、固定目标数和固定 seed 的限制，增加完整输入指纹/快照及内存内容交付。原 0.1.0 交付包继续使用 runtime-map/v1，原文件/哈希未改；消费者接收新接口时须明确识别 v2，不能把旧的固定包校验器当作任意地图的接口。

矩形原点乘 `coordinates.block_size_pixels`，再加已物化局部像素坐标。内容已镜像，标记用于来源追溯，不二次应用源偏移或负 scale。起点/奖励/Boss 的真实身份完整导出；实际出生落点、Boss 本体/结束流程仍由主游戏绑定。原怪物、奖励及未知物理注记保留，不新增随机刷怪/掉落策略。

诊断包含请求自己的原始求解状态、失败/回退记录、检查结果和计数，内部求解别名只用于调试，主游戏消费 map 的真实 ID。除实测时间外，默认输出内容与搜索计数可重放。墙钟预算受机器负载影响；以候选操作预算作为可复现的主要边界。

## 取消与进度

```python
from threading import Event
from mapgen import GenerationHooks

cancel = Event()
result = generate(request, library, config, hooks=GenerationHooks(
    cancelled=cancel.is_set,
    on_checkpoint=lambda event: print(event["phase"], event["expanded"]),
    on_failure=lambda event: print(event["reason"]),
))
```

回调得到数据副本，不能通过修改回调参数改变搜索状态。候选求值和放置实例前检查取消；墙钟按显式检查间隔检查。可注入单调 clock 做宿主/测试适配。同步 generate 可由宿主放入 worker 线程；本轮没有实现 Godot 的异步生成、场景实例化或引擎移植。

## 验证

```sh
python -m unittest discover -s tests/interface -v
python tests/interface/replay.py \
  --library .cache/legacy-real-v2/modules.zip \
  --library-sha256 5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723 \
  --request examples/request-930001.json --config profiles/stable-v2.json \
  --out /tmp/mapgen-interface-replay
```

[14 项接口测试](../validation/interface-v1/tests.log)覆盖独立运行、并发隔离、无文件/网络访问、参数生效、两奖励四主路、净空、起点绑定、区域过滤、预算/取消和 Schema。[完整 40-seed 对照](../validation/interface-v1/replay/summary.json)核对原始实例、独立图、主路、完整内容与搜索计数；两个代表的完整新结果压缩保留。旧实验原样保留并运行原保护检查。
