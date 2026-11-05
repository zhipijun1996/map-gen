# 0.7.0结构生成算法实验

新算法`experimental-v6-structure-first`，实现版本0.7.0-experiment，精确实现和25个运行文件锁见selection.json。工作基线是PR #10 head 941c7205bcdef017ef443a7edb438c019ff7ca87，旧0.5.1/0.6.0及全部历史包和预期不改，不替换默认算法。

这是实际可执行的纯数据GDScript架构原型：先选择结构要求和骨架生长数量，落实真实START/Boss与三条静态路径，再从真实两模块motif和有向归并候选中做有限域联合选择，锁定奖励边界后填充普通模块。不是完整的任意拓扑语法/整图约束求解器；骨架闭环与有向归并候选枚举仍复用旧的有界计算组件。它改变算法行为、随机调用、搜索计数和布局，不能冒充0.5.1等价性能补丁。

两配置同一算法：returns要求六条multi_return；merge要求一条forward_merge和五条multi_return。均无single_return回退。额外结构要求与原32/6/3基础目标分开比较；预算仍90秒/500000候选/128终端状态/8布局修复/128生长回退/深度3。32为START加普通生长，不含Boss、闭环或奖励连接模块。

目录：

- [版本登记](VERSIONS.md)：旧算法边界与各原型失败。
- [完整报告](REPORT.md)：成功率、耗时、结构收益、退步和未完成项。
- [60个seed效果对照](comparison/index.html)：四种算法/配置，含全部失败；模块频率按共同成功图统计。
- [调用合同](HANDOFF.md)：完整独立运行方法。
- plan.json、selection.json：测试前固定的seed、配置和源码锁。

开发复现：

```sh
python -m structure_routes.tools.setup --out /tmp/mapgen-structure \
  --profile structure_routes/profiles/returns.json
python -m structure_routes.tools.run --project /tmp/mapgen-structure \
  --out /tmp/mapgen-results --godot /absolute/godot \
  --controller --seeds 930001,930007 --config structure_routes/profiles/returns.json
```

模块ZIP作为明确输入，继续1.1.0 SHA 5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723；地图runtime-map/v2。所有中间试验、成功、失败、退出异常、输入及源码快照在validation/structure-first-20261105。独立包在runtime_packages/experiments/0.7.0-experiment，receipt记录SHA和实际源码提交。没有下载latest、Python运行时求解或预存地图查询。

本轮不改主游戏/map-edit，不发布网站，不自动合并。整图动作/接缝/奖励领取物理和正式游戏收益未验证，保持research-prototype。
