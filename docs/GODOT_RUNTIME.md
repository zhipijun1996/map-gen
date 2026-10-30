# Godot 真实模块生成器 0.1.0

正式调用入口位于 `godot/addons/mapgen/`，全部为 GDScript，运行时不使用 Python、网络或原型占位库。Python 仅安装、打包、研究和出报告。既有 `prototype/`、`src/mapgen/` 与历史实验保持独立。

这是可运行的接入候选。随机布局的几何/声明路线检查、场景装配和小图连续输入回放分别记录；不能将小图的通过推广为任意随机地图、封口子集或所有运行状态的物理认证。

## 安装与版本

用 Godot **4.7.2-stable official / ed1daf0bf**。固定包 `map-edit modules 1.0.0`，ZIP SHA256 为 `35a9fcec22bf9defcb93d3683e3b3aed4f928526fe099a72f6b5168a7bb20db3`。完整锁见 `godot/configs/package-lock.json`。验证包内每个原始文件和依赖锁的文件；任何冲突拒绝覆盖。

开发/构建阶段执行：

```sh
python3 tools/runtime/install.py --target godot
godot --headless --path godot --editor --import
godot --path godot
```

离线交付 ZIP 已带全部锁定依赖，解压后直接用上述 Godot 打开，无需安装脚本或网络。首次 Godot 导入会生成 `.godot`、`.uid` 和 `.import` 缓存，不修改 ZIP 中的原始 Module 文件。

原生路线证据绑定主游戏 `12f6cb006d7119598e3235f4ca4f7323e4c9d092`。安装器还支持明确选择包内当前主游戏 API 配置：

```sh
python3 tools/runtime/install.py --target /path/to/gunman-rush --host-profile current-game --host-source /path/to/matching-game-checkout
```

此配置锁定 `5f55716a838a754a938997920ff18cb3b17452b5`，依赖文件必须精确匹配。保留主游戏自己的 `project.godot`、Player、服务和生命周期；不安装第二套全局游戏类。较新游戏提交需要发布新的依赖锁/兼容证据，不能强制覆盖。当前游戏配置只有上游 API 接入证据，尚无本次连续路线复验，安装器会关闭原生主机的备用布局，避免跨主机冒用认证。

## 主游戏调用

在游戏启动的加载界面打开一次模块包，完成哈希校验并缓存能力池，不要每次进入区域重新读取整个包。资源加载和实例创建分开；布局求解不访问玩家实时状态。

```gdscript
extends Node
const Package = preload("res://addons/mapgen/package_adapter.gd")
const Generator = preload("res://addons/mapgen/generator.gd")
const Assembler = preload("res://addons/mapgen/assembler.gd")
var library = Package.new()

func boot_library() -> Dictionary:
    # 启动加载界面调用一次；后续区域复用此 reader。
    var opened = library.open("res://module_pack", Package.read_json("res://configs/package-lock.json"))
    if opened.ok:
        library.pool(Package.read_json("res://configs/plains.json"))
    return opened

func load_region(seed_value: int, stable_map_id: String, world: Node2D,
                 existing_player: PlayerController, services: Dictionary) -> Dictionary:
    var config = Package.read_json("res://configs/plains.json")
    config.instance_namespace = stable_map_id # 例如 run-42/region-7；随地图保存。
    var solver = Generator.new()
    var begun = solver.begin(library, config, seed_value)
    if not begun.ok:
        return begun
    while not solver.done:
        solver.step(1) # 调用 solver.cancel() 可在下次 step 终止。
        await get_tree().process_frame
    if not solver.result.ok:
        return solver.result
    existing_player.active = false
    var assembler = Assembler.new()
    begun = assembler.begin(library, solver.result.layout, world, existing_player, services)
    if not begun.ok:
        return begun
    while not assembler.done:
        assembler.step(1, 8000) # 自动后台预载；尚未完成时不会阻塞 threaded_get。
        await get_tree().process_frame
    if not assembler.result.ok:
        return assembler.result
    existing_player.motor.global_position = Package.point(solver.result.layout.spawn.position)
    assembler.activate() # 区域初次出生；普通 Module 接缝不再次调用 load_region。
    existing_player.active = true
    return {"ok": true, "assembler": assembler, "layout": solver.result.layout,
            "fallback": solver.result.fallback}
```


services 必须提供宿主已有的 `policy: FrameDamagePolicy`、`lifetime: DemoLifetime`、`wallet: RunWallet`、`meta: MetaProgression` 与 `region_state: PlainsRegionState`。示例完整处理循环见 `godot/example/main.gd`。示例宿主在新地图初次出生时设置位置；Assembler 从不创建 Player、应用调参、补血或补充射击资源。跨接缝不调用 reset、profile initializer 或资源恢复方法。父节点必须只有平移，不能缩放/旋转。

`begin()`/`step()` 的返回值属于协议，不可只检查是否存在 layout。失败原因包含能力池不满足、接口缺口、步数/时间/重试预算、奖励放置失败、碰撞、封口路径相交等。诊断保留被排除的具体 Module、内容版本、Port 子集和原因。

## 区域参数与确定性

`configs/plains.json` 是版本化区域配置。第一轮仅使用精确见证的 `move + jump + shot_recoil` 与默认玩家调参；能力不是向上兼容集合。需要其他原生 profile 的模块、需要外部邻接平台的路线和初始权限不允许的路线会被排除。`mapReady:false` 本身不排除已有路线证据。

可调项：`module_budget` 是实例数量上限，**不是保证恰好生成该数量**；`target_branches` 控制主路分叉/汇合回路数；`reward_density × module_budget` 向上取整为必达奖励数量。可选 `allowed_module_ids` 限定有证据支持的区域池。`search` 控制步数、候选数、Beam、连接长度、重试和墙钟预算；`repetition` 按面积放大大模块的重复成本。当前骨架优先选择具有两个左、两个右 ROCK 接口且实际路线互通的枢纽，连接搜索支持四种方向与匹配的地貌。其他骨架/能力配置需要独立验证。

固定输入、包锁、引擎、稳定遍历顺序和搜索操作预算时，Park–Miller 整数 RNG 的输出可复现，分步调用批次大小不改变布局。墙钟预算仅中断/回退，不保证同一设备负载下每次走到相同步数。计时、资源加载完成帧不参与 RNG。

## 实例、封口与实际路线

保存 `mapgen/layout/1`：每个实例有稳定 `instance_id`、Module/内容版本、Block 原点、identity 配置、真实 `connected_port_ids` 与 `sealed_ports`。一个模板只保留一份内容，不为 Port 子集复制。当前正式配置只平移，镜像与角落迁移会明确拒绝。

Port 的归属是 owned rectangle，不是编辑器画布原点：`world2 = 2*originBlocks + local2`，实际场景再加 `sceneOriginOffsetPixels`。邻接必须精确同点、反向、同地貌且满足初始权限。占用检查使用完整矩形。

`gear-seal/1` 是 map-gen 覆盖层，保留上游 `original-all-ports` 的原认证范围，直接绑定原场景后附加组件，不向旧 Registry 谎报所有口已连接。每个封口在 owned rectangle 内覆盖接口所在完整边界 Block 的 128 像素通口，向内厚 32 像素，复用原齿轮绘制与 ENVIRONMENT 伤害消费者，并有独立实体碰撞。它不是墙攀标签或钩点。已连接的口不加封口。

封口后删除任一端点被封的 Route，对保留的作者路径进行玩家碰撞尺寸扩张后的保守净空检查；相交的组合退出搜索。此项是**作者路径静态检查，不是实际轨迹或所有机关状态证明**。兼容性按实际候选子集增量记录。完整有向图采用 `port/in → module_route → port/out → seam → neighbor/in`，不会借同一个 Port 将两条内部路线随意拼接。

奖励从路线的 `requiredRewards` 或版本化 `reward_route_overrides` 映射到具体 reward site。到达其入口且奖励路线出口能继续到目标才计入；不能由“此模块有宝箱”推断任意路线经过宝箱。S13/HQ04 的旧元数据缺少奖励关联，当前显式适配记录在区域配置，仍保留证据层级。

## 保存、重建、卸载与回退

`assembler.save_layout("user://map.json")` 保存布局与版本锁；读取 JSON 后重新 `begin()`，重新检查几何、内容版本、连接、封口与路线。齿轮按保存参数重建，不依赖临时节点名称。调用 `unload()` 并等待 queued 节点退出后才能复用实例 ID，原 Player、Wallet、Lifetime 保留。此接口保存生成结果，**不等于任意时刻完整敌人/机关/玩家进度存档**；该进度由主游戏服务层扩展。

宿主应传入持久的 `instance_namespace`（例如 Run ID + 区域实例 ID）。未传入时由区域 ID 和 seed 派生；同一 seed 的不同新局仍应提供不同 Run ID。备用布局只重绑定实例身份及其图引用，保留几何/内容/原物理证据，避免不同地图的敌人和奖励交易共用旧身份。

默认备用布局有固定文件 SHA，绑定相同模块包、运行主机、区域身份、精确能力、玩家配置与封口版本。步数耗尽等失败可返回 `fallback:true`、失败原因、请求参数和实际降级规模。备用小图有真实连续回放证据，但可能减少规模/奖励数；不把它伪装为满足原规模请求。配置不兼容时返回失败，不借用其他区域/能力的备用图。

## 验证与边界

固定 seed 数据、全部失败原件、物理输入轨迹、录屏与性能在 `reports/runtime-v1/`。运行：

```sh
python3 tools/runtime/check.py --godot /path/to/Godot_v4.7.2-stable_linux.x86_64
python3 tools/verify_progress.py --replay
python3 tools/runtime/report.py
python3 tools/runtime/build.py
```

`check.py` 同时检查退出码和脚本错误日志，不能用测试 PASS 标记掩盖脚本中断。重复本地运行前另存旧报告。随机地图的装配检查不包含真实玩家遍历；连续录屏是自动输入回放，非人类盲测。

节点预算是模块创建的软预算：原生模块的一次 `_ready/bind_player` 不可中途打断。后台预载消除了大部分首载停顿，原模块动态建 Cell/纹理仍可能超过 8ms；准确峰值见报告，不能宣称硬实时。要稳定降低长尾，需要模块包提供可分步创建接口或离线烘焙场景缓存。浏览器导出还需保留被哈希校验的原始文件；普通 Godot 导出会重映射脚本/图片，不能未经校验直接宣称 Web 交付通过。
