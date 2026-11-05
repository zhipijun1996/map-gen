# 独立组件交付

交付物：`runtime_packages/experiments/map-additions-0.1.0/mapgen-map-additions-candidate-0.1.0.zip`。包路径、完整SHA256、实际源码commit、manifest摘要与9个运行文件锁以同目录receipt.json和包内manifest.json为准。状态`research-prototype`，runtime_target=`godot-standard-pure-gdscript`；它是地图附加物组件，不是新的生成算法包，也不替换0.8.0/0.4.1。

独立验证：把ZIP解压到仓库外，进入其中的mapgen-map-additions-candidate-0.1.0目录：

```sh
python3 verify_bundle.py --godot /absolute/locked-godot-4.7.2
```

仅需Python3标准库与Godot，脚本执行真实GDScript，核对所有包内摘要、9个运行文件、两个真实样例、显式商店合成夹具及预算/取消/批次/复制合同。不依赖仓库experiments、旧生成插件或模块ZIP隐式路径，不联网下载模块。后处理输入已带完整物化内容；它不负责调用生成器或替主游戏装载节点。

直接调用示例（所有文件参数用绝对路径）：

```sh
godot --headless --path /absolute/unpacked --script res://tests/run.gd -- \
 /absolute/unpacked/examples/real-930001.json \
 /absolute/unpacked/profiles/default.json /tmp/annotations.json 1
```

真实冻结样例来自v7/0.8.0生成的930001、930007，带原完整map/content_store和输入/来源身份，预期包含PARTIAL及缺口。原生成器仍是原包，不由本包复制或伪造。算法来源、配置、模块锁、请求和完整内容在样例内保留。包内synthetic-shop必须与真实证据区分。测试夹具用于证明商店分类/路由和取消等合同，不能当作主游戏地图。

宿主集成顺序：保留原生成接口 → 成功结果静态校验 → 创建附加物job并推进/取消 → 显式处理PARTIAL/gaps → 主线程装配sidecar中的牌/齿轮节点。保留原地图/内容，不把字段直接塞进严格runtime-map/v2。图和内容引用、结果/指纹与宿主信封边界见CONTRACT.md。主游戏拥有交互、运动伤害、物理、生命周期和资产；不需要复制本组件或生成核心算法。

真实Godot/Web证据及性能拆分见REPORT.md和源码仓库validation/map-additions-20261105；Web UI自动化失败尝试也保留。最后验证结论与包外完整SHA见receipt与实际日志，不能只根据本文声称通过。
