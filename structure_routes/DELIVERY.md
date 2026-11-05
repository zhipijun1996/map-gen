# 0.7.0-experiment交付记录

- 算法：`experimental-v6-structure-first`。
- 实现：`mapgen/gdscript-experiment-0.7.0+121edabc61b9`，完整25个运行文件。
- 实际源码commit：`6a0116a2aac18302196834fcd80432197784b78e`。
- 产物commit：`47bd5b68197fca87b4c02ebd78f584b5ae2a2e51`；后续交接文档提交不改写包内来源。
- 独立包：[不可变ZIP下载](https://raw.githubusercontent.com/zhipijun1996/map-gen/47bd5b68197fca87b4c02ebd78f584b5ae2a2e51/runtime_packages/experiments/0.7.0-experiment/mapgen-godot-experiment-0.7.0.zip)。
- SHA256：`364c35d0b0a7f022541a98791db772863d8fd3c61ce9bcc75d2d41e4df8302fb`，大小4361119字节。
- [完整收据](../runtime_packages/experiments/0.7.0-experiment/receipt.json)：仓库外独立解压verify_bundle 206项与CLI完整重放PASS。

包是research-prototype，production_ready=false、default_replacement=false，实际主游戏和整图物理NOT_RUN。不是新的正式游戏锁，不能将verify通过等同所有seed生成成功。

[调用与安装合同](HANDOFF.md)：纯数据GDScript，preload_job/generation_job API形状和runtime-map/v2转换合同不变；新增结构配置Schema及阶段，需精确算法/实现准入、25文件锁与新的恢复身份。模块仍1.1.0 SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`。不下载latest。

[版本登记](VERSIONS.md)、[完整报告](REPORT.md)、[60张对照](comparison/index.html)、[汇总图](comparison/success-and-reward-structure.png)。本轮对比v4/v5/v6；0.7两配置不是两种独立算法。60例结果为56/60、60/60、58/60、13/60，额外结构硬要求分别报告。原日志中的失败及早期进程异常保持原样，原四历史拒绝和所有旧包不改。

同步四方原生计时、真实Web四成功及一真实失败完整重放、32项Web审计、32项API、8项隔离与11条批次/取消/失败合同均有执行证据。没有自动GitHub工作流checks，不用可合并状态代替验证。所有失败map=null/content_store={}。

本轮未修改主游戏/map-edit，未自动合并、部署或发布Release。新归并配置失败率和耗时不适合默认接入；新折返结构/重复指标有收益，但仍有两次失败与尾部代价，需要保留为研究结果。
