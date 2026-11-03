# Godot 性能候选 0.4.1

这是 `stable-v3-reward-space` 的独立实现修订，运行目标为 Godot Standard / 纯 GDScript，继续 `runtime-map/v2` 与模块包 1.1.0。候选状态，不代表整图物理可玩或主游戏整段 Web 验收通过。

基线为 PR5 `6bf07ab5a655ea056461b935ae4354e15ef83482`，原包源码 `b21c889077ec97eb11a210d0ceab4fbddd862e48`。原 0.4.0、0.3.x 及 Python 参考包和预期保持原样。下游证据固定在 gunman-rush PR129 `46eb3960a592374b5fb99d7df588962a3680f86b`，原文和原请求字节见 `upstream/`。

## 调用合同

无需重写调度或 Provider：保持 `PreloadJob.create(zip_path, expected_sha)` → `advance(1)` / `progress()` / `cancel()` / `is_done()` / `result()`，取得通过的 `library` 后调用 `GenerationJob.create(request, library, config)`。一个单位仍为 16 检查点，1..4096；检查点位置及单位总数可改变，不是搜索候选数，也不是毫秒保证。继续每 tick 至多 128 单位、软 8ms，让帧由宿主决定。

```gdscript
const PreloadJob = preload("res://addons/mapgen/preload_job.gd")
const GenerationJob = preload("res://addons/mapgen/generation_job.gd")
var preload_job = PreloadJob.create(module_zip_path, module_sha)
# 宿主逐帧推进并检查其自身 lifetime / opaque ticket。
preload_job.advance(1)
# 完成且 status == PASS 后，library 可在同一 owner 中供多个 job 复用。
var job = GenerationJob.create(request, preload_job.result().library, config)
job.advance(1)
# 终态才读取完整结果；失败没有可用 map/content_store。
var result = job.result() if job.is_done() else {}
```

只有 `PASS` 是可用地图，必须同时保留完整 `map`、`content_store`，按原相对 ref 解析。`result()` 返回独立深拷贝；每 tick 不应调用它取得进度。算法不依赖 SceneTree、LevelPlan、Factory、玩家/钱包或主游戏 bindings/source_record。run/stage/actor token 仍仅在宿主信封，不进入请求和指纹。节点装配、玩法锚点和实际物理由宿主负责。

实现身份改为 `mapgen/gdscript-candidate-0.4.1`，因此原请求指纹、map_id、generator/diagnostics 实现字段会变化；不得改写旧指纹来假装原件一致。公共 Schema 的版本与算法名不变。对照投影仅排除这些明确身份字段及 `metrics.generation_seconds`，完整其他结果逐项比较，包含随机状态、搜索计数、内容、Route、镜像、封口和奖励拒绝证据。生成上限仍 90 秒 / 原 500000 候选 / 原检查间隔，不因性能测试放宽。

## 可重建缓存与库所有权

`addons/mapgen/derived_library.gd` 是新增的普通 GDScript 数据资源，显式绑定完整模块 ZIP SHA 与本实现身份。它只包含原 JSON 的类型/浮点位精确保真编码，不含请求、预生成地图、搜索结果或随机状态。仍在每次预载时读取/解压 ZIP、检查整个 ZIP SHA、核验所有 657 个 manifest 文件。缓存不是第二个模块源；源 ZIP 缺失或篡改照样拒绝。缺少/不匹配/载荷摘要失败时走原 JSON 解码路径，不会悄悄放宽校验。缓存和源数据全量比较、损坏绑定负例见校验收据。

可选第三参数 `PreloadJob.create(path, sha, false)` 强制从 JSON 重建；原两参数调用兼容。`build_derived.gd` 放入独立项目后用锁定 Godot 执行可重新产生相同 `.gd`：

```sh
GODOT --headless --path PACKAGE --script res://build_derived.gd -- MODULES_ZIP REBUILT_GD
```

只有工具/派生数据的生成需要此入口，运行时不用 Python。打包工具将 ZIP 原件作为输入，不下载 latest。预载实例的解码 Dictionary、所有求解/拓扑/可达性缓存属于各自 job；已验证 library 只供读取。公开 `read_json()` 是快照，取消一个 job 不改变 library 和其他 job。

宿主换锁时按新 manifest 的 `addon_files` 更新安装 pin 集合：原 18 个 `.gd` 更新，新增 `derived_library.gd`，总共 19 个正常脚本资源。它随正常 Godot 资源导出，无额外二进制路径/导出白名单需求。模块 ZIP 及两个请求/配置沿用原锁，检查输入 SHA 不变。固定下游还需同步 Job/Provider 的版本准入值，准确行号见 `REPORT.md` 和 `upstream/host_calls.json`；仅改 JSON 锁会拒绝。旧存档来源应保持旧身份，不应跨实现冒充恢复。主游戏的实际接入与 CI 在下游进行，本仓库不修改主游戏。

## 验证与复现

`REPORT.md` 区分纯算法 active advance 时间、预载、让帧残差、结果快照/序列化及宿主/工具。真实 Web 使用与固定下游相同的 4.7.2 custom、threaded release 模板、COOP/COEP、advance(1)/128/8ms；运行在独立纯数据项目，不能代签主游戏 218MB PCK、Stage/Motor 或默认双 fresh 300 秒脚本。

包内独立验收（模块 ZIP 已作为明确测试依赖锁定）：

```sh
GODOT --headless --path PACKAGE --script res://tests/verify_bundle.gd -- PACKAGE/tests/dependencies/modules.zip
```

`manifest.json` 校验全部交付文件，并重放成功、930007 和真实失败样例。详细证据与 SHA 见 `evidence/`。源码仓库的定位/重放工具在 `performance_revision/tools/`；`regression.py` 将当前完整结果与不变的 0.4.0 原件比较。历史样例和证据不得覆盖。

没有模块库字段需求或升级到 1.1.1。本轮不增加随机危险、随机布怪，不完成全图物理认证，不声明硬帧或手机时延保证。

开发复现工具：`setup_bench.py --out DIR --source godot_runtime/addons/mapgen` 建立独立项目；`regression.py --project DIR --out NEW_REPORT --godot GODOT` 比较原 47 例；`web_bench.py --project DIR --out NEW_REPORT` 驱动真实导出项目（先用下游锁定引擎执行 import/export-release Web）。这些开发工具使用显式锁定的 `.cache/legacy-real-v2/modules.zip`，先将原 ZIP 放到该位置并核对 SHA；候选包的运行/校验入口不依赖此路径。
