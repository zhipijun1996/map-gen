# v8职责生长实验交接

算法`experimental-v8-role-aware-growth`，实现版本`0.9.0-experiment`（完整实现后缀由运行文件摘要生成，见source-lock与包receipt）。以PR #13 head 776b3cd4046896cfe2ea19ef6e6f8b4b8fca4372为仓库基线，运行算法基线为冻结v7/0.8.0。分支experiment/role-aware-growth，不自动合并/部署。

实际结果：原40seed 40/40，新10seed 8/10；v7分别39/40和10/10。共同47成功图的分叉相邻11.15→7.89，大型双口1.64→4.00，核心流程覆盖49.06%→51.64%。不是全面稳定性升级；默认算法不切换。

协议继续generation-request/v1、generator-config/v1、generation-result/v1与runtime-map/v2；显式配置新增growth_roles，属于新算法分支。原目标/预算/净空不变，模块1.1.0 SHA256 5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723。新实现和配置参与指纹，旧恢复身份不能混用。

运行入口：README的setup/run命令；包内可用tests/generate.gd读取模块ZIP、请求、配置和输出路径，或正常创建GenerationJob并advance/cancel。新增观察统计在diagnostics.details.growth_roles，包含重试观察计数、最终实例职责及父节点。宿主不需复制求解器；当前未接主游戏。

交付包runtime_packages/experiments/0.9.0-experiment及receipt记录不可变源码commit、ZIP SHA、完整运行文件摘要、独立解压核验。readiness为research-prototype。真实成功样例、980005预算失败、980010搜索失败和jump-only失败均保留；失败无可用map/content_store。

该实验尚无按动作时间计算的分叉间隔，阶段职责也未扩展为每条路线的完整任务状态。主路线宏构造和奖励构造沿用v7。map-edit不需要为了本实验改外围或升级模块；若调查低频模块应先定位具体连接/封口冲突，再提出有证据的作者修改。无随机布怪或新增危险，地图附加物不参与本轮对比。

## 不可变产物

- 实际源码commit：`27be7c0e1710f5b3c0a2b85ceb31ae428a44cf32`。
- 产物commit：`d1cc57fb67b32ff67ec39ef14936b08e2acae0c5`。
- 实现：`mapgen/gdscript-experiment-0.9.0+45a0e78b9f75`，30个运行文件。
- [独立ZIP下载](https://raw.githubusercontent.com/zhipijun1996/map-gen/d1cc57fb67b32ff67ec39ef14936b08e2acae0c5/runtime_packages/experiments/0.9.0-experiment/mapgen-godot-experiment-0.9.0.zip)。
- ZIP SHA256：`7009f3793e299508918cc920e00525bfcbb5f540d7295cbdef2f0e7d4830839e`。
- manifest SHA256：`c2c4b364f99e7173ece27fef346fb377633069ea0506dbd619656b9f9726f78c`。
- 仓库外独立解压并实际Godot重放：94项PASS，包含2成功＋3失败的完整结果比较及文件摘要。
- 证据审阅122项PASS；它表示证据一致与安全检查通过，**不表示50次生成全成功**。

包内HANDOFF在源码提交时冻结，不回写产物commit；本文件和receipt补充产物定位。安装/调用见[PACKAGE_USAGE.md](PACKAGE_USAGE.md)。未更改当前正式候选、宿主、模块锁或附加物组件。
