# map-gen 主游戏交付包 0.1.0

这是固定地图的数据交付包，不是可直接启动的 Godot 游戏。目标是让主游戏在保留现有玩家与玩法系统的条件下，装配并验证第一张真实模块地图。

- 地图：seed **930001**，`stable`，生成提交 `41fe15d8b7450a27ff3b3c0e62eb217bffbf2145`。
- 模块：map-edit **1.1.0**，原 ZIP SHA-256 `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`。
- 生成目标及静态检查通过；主游戏加载、连续通行、出生点和 Boss 流程尚待接入验证。

## 从这里开始

1. 解压，在原始交付目录运行 `python verify_delivery.py`。只需 Python 3.10+ 标准库，无需 map-gen 仓库和网络。
2. 阅读 [CONTRACT.md](CONTRACT.md)，将 [MAIN_GAME_PROMPT.md](MAIN_GAME_PROMPT.md) 交给主游戏仓库的 Codex。
3. 游戏读取 `manifest.json` → `maps/seed-930001.json` → 每例的 `content_ref`。JSON Schema 在 `runtime-map.schema.json`；独立校验脚本还检查 Schema 无法表达的几何、图及原数据一致性。
4. 对照 `reference/seed-930001.svg` 或 PNG，装配 46 个实例。允许负坐标，不要只装载正坐标区域。

ZIP 外层有 `.sha256` 校验文件；在 ZIP 所在目录执行 `sha256sum -c mapgen-delivery-0.1.0.zip.sha256`。也可在解压前用仓库内的 `delivery/verify.py ZIP路径` 校验。

## 文件用途

| 路径 | 用途 |
|---|---|
| `manifest.json` | 契约版本、生成版本、模块锁、文件哈希和地图入口 |
| `maps/seed-930001.json` | 真实模块 ID、布局、完整 Port、连接、封口、保留 Route、实际图和玩法锚点 |
| `content/Mxx.json` | 每实例完整、已归一化且已镜像的编译内容，含原有怪物和奖励 |
| `module_pack/` | 原模块 ZIP 的逐字节解压副本，供资源和运行时行为复用 |
| `dependencies/map-edit-modules-1.1.0.zip` | 原始模块 ZIP，供独立追溯和校验 |
| `reference/` | 单图参考、源实验记录、配置、物理未知项与验证范围 |
| `verify_delivery.py` | 无第三方依赖的文件、内容、几何和实际图校验器 |

宿主玩家、共享 Cell 和美术资源不包含在原模块包中。它们由主游戏现有资源或 `module_pack/integration/install_host.py` 按锁补齐。主游戏保留自己的 `project.godot`、玩家与服务；先比对宿主版本，不向现有项目强行覆盖不兼容文件。模块包里的 `host-lock-current-game.json` 指向历史检查提交，不表示主游戏当前 HEAD 已经通过验证。

## 本张地图的固定内容

46 个实例，6 个目标奖励房，11 个奖励点，编译内容中有 18 个怪物记录（13 个 `plains_diver`、4 个 `plains_sentry`、1 个 `plains_charger`）。这些都是选中模块自带的内容，不在接入时重新抽取。6 个目标奖励房之外的奖励保留原关联和未知状态，不宣称全都已获领取认证。Boss 战场的编译敌人列表为空，Boss 本体与战斗生命周期由主游戏绑定。

模块包的原 registry 只加载原始场景；它尚不接受本包的物化内容，也不安装实例齿轮封口。主游戏需要新的地图级适配入口。**仅调用原 `instantiate_module()` 不能还原本图。** 具体边界和加载顺序见契约。

`reference/validation.json` 明确列出未解决项：物化内容加载器、真实出生落点、Boss 触发/结束、宿主兼容与全图物理。起点现有 `entry` 已封口，不能把源内容的 `entry_port` 直接当出生点；Boss 未连接的 `exit` 也已封口，不能默认它是战后出口。

本包保证数据忠实于已通过的固定实验，并可独立核查；不包含 Godot 算法移植、主游戏修改或全图物理认证。不要把文件校验通过解释为已经可通关。
