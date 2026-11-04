# 奖励规划优化实验：性能候选与研究原型分开

基线：PR #9 head `47e661f9f6049d8fb701007c6af85efe2ead1e03`；0.5.0和更早包、冻结预期原样保留。本轮不改默认入口、不合并或部署。

- **0.5.1 candidate**：只优化0.5.0的查询与排序计算，算法仍`stable-v4-reward-branches`。完整地图、内容、RNG和搜索计数保持一致；优先供下一步性能接入评估。
- **0.6.0-experiment research-prototype**：算法`stable-v5-joint-reward-plans`，联合选择奖励支路、提前保护已知可行空间、反向索引实际有向接口。两能力样本成功率提高，但模块种类和非单房奖励支路下降，**不作为默认质量升级**。

两者都是实际纯数据GDScript求解，继续模块1.1.0和runtime-map/v2。目标32生长/6目标奖励/3主路线、90秒/500000候选、128终端状态、8修复、回退深度3及宽高比上限3不变；没有额外授予能力或改变净空。完整结果由API计算，不查预存地图。

[实验报告](REPORT.md)记录收益、失败和退步；[调用合同](HANDOFF.md)说明独立运行；[40张对照](comparison-v7/index.html)可本地直接打开，含旧版失败与新图；[全部模块频率](comparison-v7/module-usage.csv)采用37个共同成功seed。

复现开发环境（独立交付包无需这些仓库路径）：

```sh
python -m joint_routes.tools.setup_perf --out /tmp/mapgen-perf
python -m joint_routes.tools.setup --out /tmp/mapgen-joint
python -m joint_routes.tools.run --help
python -m joint_routes.tools.build --help
```

源码、请求、配置、所有成功/失败及中间拒绝实验保存在`validation/joint-reward-20261104`；选择规则见`selection.json`。候选包最终源码commit、SHA、验证收据见`runtime_packages/releases/0.5.1`与`runtime_packages/experiments/0.6.0-experiment`，不发布GitHub Release。
