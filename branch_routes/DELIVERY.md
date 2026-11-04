# 0.5.0 候选交付

- 实际源码commit：`701582c200c43d9860e2f3aa0d30e858d421079f`。
- 产物commit：`1b000de6b54b07875483af575ef3d13afb79b93e`。
- 实现：`mapgen/gdscript-candidate-0.5.0+dfec9fbf79b7`。
- 算法：`stable-v4-reward-branches`，仍为candidate。
- [独立ZIP不可变下载](https://raw.githubusercontent.com/zhipijun1996/map-gen/1b000de6b54b07875483af575ef3d13afb79b93e/runtime_packages/releases/0.5.0/mapgen-godot-candidate-0.5.0.zip)，4060459 bytes。
- SHA-256：`aae047f5dc0058b5a3d0e6a5639d1df11c15a8cf32db8ab8f7da3819a2cf2309`。
- [20文件安装锁](https://raw.githubusercontent.com/zhipijun1996/map-gen/1b000de6b54b07875483af575ef3d13afb79b93e/runtime_packages/releases/0.5.0/install-lock.json)复用manifest的package/module_package/protocol/addon_files字段，同时给出新配置SHA。
- [独立验证收据](../../runtime_packages/releases/0.5.0/receipt.json)：独立目录解压、Godot verify_bundle 219项及CLI真实生成重放均通过。

上方验证收据在仓库根目录`runtime_packages/releases/0.5.0/receipt.json`；ZIP内manifest保留实际源码身份，不将后续交付说明或PR提交冒充源码。

本版改善模块选择集中和部分奖励支路重复：同批60图每图普通源种类21.37→23.75，覆盖75→80；32条多模块独立折返、17条归并，其中1条严格向前归并。完整对照及局限见[报告](REPORT.md)和[地图](comparisons/index.html)。

四能力独立数据宿主两seed在native/Web提速，但实际两能力请求相对旧默认分别慢约30.5%/4.6%。本候选不能标为正式游戏速度问题已解决，也不能依据四能力收益自动替换正式默认。奖励仍多数单房，宏观占用相似度基本不变；主游戏物理与端到端验证未执行。

接入步骤见[HANDOFF.md](HANDOFF.md)：完整换20文件锁、精确实现/算法准入、新配置及其Schema；Job调用和runtime-map/v2数据转换保持原结构。模块继续1.1.0原SHA，旧0.4.1/0.4.2包保留。新实现及配置产生新指纹，恢复身份不能沿用旧版。没有升级模块1.1.1、随机危险或随机布怪，没有自动合并或部署。
