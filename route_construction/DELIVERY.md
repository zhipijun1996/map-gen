# 0.8.0-experiment交付

算法`experimental-v7-joint-route-construction`，实现`mapgen/gdscript-experiment-0.8.0+2271b5d4da0d`，28运行文件。实际源码commit `fe817c40edcb899e6b78ba2f39f591e8adfe7787`；产物commit `13eeb020cdda23cd916b3a2e7b3d923cb80d6d08`。后续文档/PR head不改写包内来源。

- [不可变ZIP下载](https://raw.githubusercontent.com/zhipijun1996/map-gen/13eeb020cdda23cd916b3a2e7b3d923cb80d6d08/runtime_packages/experiments/0.8.0-experiment/mapgen-godot-experiment-0.8.0.zip)
- SHA256：`783d6d815a20d6dad9f6d4acc341593d23c28036b975fffa294fb2f1ba233f6b`
- 大小：4230998字节
- [执行收据](../runtime_packages/experiments/0.8.0-experiment/receipt.json)：仓库外独立解压verify_bundle 248项、CLI完整重放均PASS。

[优化项](OPTIMIZATIONS.md)、[报告](REPORT.md)、[版本记录](VERSIONS.md)、[地图对照](comparison/index.html)、[安装/调用合同](HANDOFF.md)。新API形状和runtime-map/v2转换不变，需显式28文件锁、新算法/实现准入及恢复身份，不自动切正式锁。模块仍1.1.0 SHA 5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723。

同一硬风格80例，旧0.7 merge16/80、新0.8为78/80；两预算失败保持原样。新成功率和速度提升不等于全图质量提升：普通模块图上访问/完成覆盖及Boss流程长度代价在报告显式列出。状态research-prototype，production_ready=false，主游戏与整图物理NOT_RUN。

API32、隔离8、合同14、预算负例1、单段索引28、Web审计32与5项完整原生/Web重放均有证据；所有旧包SHA和20历史seed保护通过。没有自动GitHub工作流checks，不能用可合并状态代替验证。

新增用户功能另见[边界移动齿轮与分岔告示牌设计](../docs/feature-proposals/boundary-hazards-and-signs.md)。已核对115模块，尚未实现，不进入0.8.0冻结结果或runtime-map/v2字段。不改主游戏/map-edit、不升模块、不合并或部署。
