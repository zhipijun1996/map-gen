# map-gen Python 参考算法包 0.2.0

`runtime_target=python-reference`，`readiness.stage=reference-only`。本包包含可执行 Python 参考生成核心和冻结的 runtime-map/v2 样例，供主游戏验证公共协议、内容解析及后续算法移植。

**本包不是 Godot Standard/Web/桌面游戏内可执行的算法组件。** 模块依赖 ZIP 中虽有 Godot 资产/脚本，它们不是已经移植的生成算法。未执行主游戏场景加载、动作、跨缝或全图物理认证。

算法仍为 `stable-v2`，实现仍为 `mapgen/interface-v1`；打包版本为 `0.2.0`。请求 v1、配置 v1、结果 v1、runtime-map/v2 的语义保持不变。新增结果 JSON Schema 只是描述已有 `GenerationResult.to_dict()`，没有另建生成协议。实际打包源 commit、原算法基线、各文件 SHA 在 manifest/provenance 中分开记录。

## 独立运行

先从可信仓库取得 ZIP 与 `.sha256`，在 ZIP 所在目录执行：

```sh
sha256sum -c mapgen-python-reference-0.2.0.zip.sha256
unzip mapgen-python-reference-0.2.0.zip
cd mapgen-python-reference-0.2.0

# Python 3.10+，标准库即可；不会下载模块或访问原仓库
python reference.py verify --module-zip dependencies/map-edit-modules-1.1.0.zip
python reference.py replay --case all --module-zip dependencies/map-edit-modules-1.1.0.zip

# 输出目录必须不存在，并放在交付目录外
python reference.py generate \
  --request samples/success/request.json --config profiles/stable-v2.json \
  --module-zip dependencies/map-edit-modules-1.1.0.zip --out /tmp/mapgen-new-result
```

模块 ZIP 是每次调用的显式输入。本包附带构建时指定、锁定的 1.1.0 ZIP，方便完全离线验证；也可传另一份 SHA 相同的文件。依赖 SHA 为 `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`。不同版本或哈希会拒绝，不默认下载“最新”。宿主游戏的玩家/资产不包含在这个 Python 算法包中。

`verify` 校验完整文件清单、源码/配置/样例哈希、输入指纹、完整内容引用、真实模块身份、坐标/镜像/封口、有向图和目标，以及 RNG/数值向量。`replay` 重新执行当前 API 并比较冻结结果，仅排除 `metrics.generation_seconds`。退出码 0 表示这些校验通过；生成失败或校验失败为 2。验证失败样例时命令可以成功完成，其生成状态仍明确是 SEARCH_EXHAUSTED。

文件完整性校验忽略运行产生的 `__pycache__`，不忽略别的新增/删除文件；请保持交付目录只读。校验器提供本协议的结构和语义检查，不是任意 JSON Schema 的标准库实现。Schema 可另用标准 JSON Schema 引擎检查，本轮开发测试也会检查。

## 内容入口

| 文件 | 用途 |
|---|---|
| `manifest.json` | 算法包版本、源 commit、算法/实现标识、runtime target/readiness、协议入口、模块兼容约束与所有文件 SHA |
| `mapgen/` | 可直接调用的 Python 核心及结果验证工具，零第三方运行依赖 |
| `profiles/stable-v2.json` | 原样默认配置，32 个生长实例、6 个目标奖励、3 条主路和形态门槛不变 |
| `schemas/` | 现有请求、配置、runtime-map Schema，及补齐的现有结果 Schema |
| `dependencies/` | 明确指定的原模块 ZIP、模块锁、已测试 Python 环境与零运行依赖锁 |
| `samples/success/` | 原样 seed 930001 请求、配置、模块锁、完整 result、map、content_store、逐引用内容和 provenance |
| `samples/failure/` | 同 seed/配置/模块，只具备 jump 的真实失败请求；无 map.json、无内容目录 |
| `determinism/vectors.json` | CPython MT19937、恢复、排序和二进制浮点向量 |
| `call_example.py` | 显式输入的 API 调用示例 |
| `docs/PROTOCOL.md` | 公共协议、指纹、引用和宿主责任 |
| `docs/HOST_HANDOFF.md` | 主游戏实际接口核对、准确使用方法及 map-edit 缺口 |
| `docs/GODOT_RUNTIME.md` | Godot Standard/Web/桌面纯数据 GDScript 路径和迁移验收标准 |

## 样例结果

成功样例是首个既有验证 seed `930001`，未改 seed、目标、评分或原模块；与接口基线的完整确定性结果一致。包含 46 个实例、55 个连接、31 个镜像、40 个封口、18 个怪物记录、11 个奖励点和 6 个目标奖励实例。主游戏应接收 **map 与 content_store 两件完整数据**，不能只取布局列表。

失败样例仍是 `930001`，唯一请求差异是能力集改为 `jump`。当前真实模块的声明路线在该请求下不能继续生长，返回 `SEARCH_EXHAUSTED`，`map=null`、`content_store={}`；配置和目标没有降低。它证明失败通路和拒绝消费规则，不证明物理上无解，也不证明 jump 是模块的最低必要能力。

生成成功只表示现有静态契约通过。出生点仍未认证；Boss 标记只到达入口，没有 Boss 本体/战后通路；附加奖励的未确认关联、宿主档位及镜像/封口物理范围继续保留为未知。

主游戏请从 [HOST_HANDOFF.md](docs/HOST_HANDOFF.md) 开始。不得把 Python 子进程当作 Web 游戏内方案，不把主游戏内部 LevelPlan 引入本库，不伪造旧 Manifest 来通过原 Stage 的来源要求。
