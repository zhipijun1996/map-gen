# 独立运行 0.9.0-experiment

本包为纯数据 GDScript 研究实验（不是正式候选升级），不需要本仓库的 Python 工具。解压后进入包目录，设置 GODOT 为锁定的 Godot4.7.2 可执行文件路径；工具链 SHA 在 manifest.json。

```sh
GODOT=/absolute/path/to/godot-4.7.2
"$GODOT" --headless --path . --script res://tests/verify_bundle.gd -- tests/dependencies/modules.zip
"$GODOT" --headless --path . --script res://tests/generate.gd -- \
  tests/dependencies/modules.zip samples/success1/request.json profiles/default.json result.json
```

verify_bundle 校验全部文件摘要，并实际重放两个成功、两个新样本失败及jump-only失败；只有耗时不参与结果等价比较。生成CLI成功返回0，失败返回1，输入或装载错误返回2。失败结果不能当作可用地图。模块ZIP是明确锁定输入，不自动下载最新版本。

集成时完整复制 addons/mapgen 的30个文件，并使用本包显式配置。先通过 preload_job.gd 的 create(zip_path, expected_sha) 创建预载任务，以 advance(operations) 推进到 is_done()，检查 result().status；成功的 result().library 可供多个生成job复用。用 generation_job.gd 的 create(request, library, config) 创建独立任务，同样 advance / is_done / progress / cancel / result。外部不修改已验证库；输入与结果按原API深复制。取消一个job不会取消其他job。

advance的参数是操作额度，不是毫秒或硬帧保证。由宿主调度推进、接收取消输入和在主线程装配节点。算法不使用主游戏LevelPlan、玩家、钱包、Factory或SceneTree；tests/*.gd中的SceneTree仅为CLI测试入口。run/stage/actor token留在宿主信封，不进入请求。

seed支持JSON整数范围[-9007199254740991,9007199254740991]，超范围拒绝，不截断。实际界限以 schemas/request.schema.json 和 protocol.gd 验证为准。请求、配置、完整模块锁及新实现身份参与确定性指纹，不复用旧版本的恢复/缓存身份。

输出保留runtime-map/v2和完整content_store引用。使用manifest的算法/实现身份准入，不能以旧v7实现冒充本包。新配置growth_roles影响结果，旧包与旧预期原样保留。包内comparison/index.html可本地打开；REPORT.md列出成功率退步及统计口径。README.md的Python命令属于仓库开发复现，独立包请使用本文件命令。

验证范围：原生完整API/隔离、步长等价和取消；两seed实际Web执行与原生相等。没有主游戏装载、整图物理或主游戏性能认证。Web取消延迟未在本轮单独测量。
