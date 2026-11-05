# v8职责生长实验交接

算法`experimental-v8-role-aware-growth`，实现版本`0.9.0-experiment`（完整实现后缀由运行文件摘要生成，见source-lock与包receipt）。以PR #13 head 776b3cd4046896cfe2ea19ef6e6f8b4b8fca4372为仓库基线，运行算法基线为冻结v7/0.8.0。分支experiment/role-aware-growth，不自动合并/部署。

实际结果：原40seed 40/40，新10seed 8/10；v7分别39/40和10/10。共同47成功图的分叉相邻11.15→7.89，大型双口1.64→4.00，核心流程覆盖49.06%→51.64%。不是全面稳定性升级；默认算法不切换。

协议继续generation-request/v1、generator-config/v1、generation-result/v1与runtime-map/v2；显式配置新增growth_roles，属于新算法分支。原目标/预算/净空不变，模块1.1.0 SHA256 5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723。新实现和配置参与指纹，旧恢复身份不能混用。

运行入口：README的setup/run命令；包内可用tests/generate.gd读取模块ZIP、请求、配置和输出路径，或正常创建GenerationJob并advance/cancel。新增观察统计在diagnostics.details.growth_roles，包含重试观察计数、最终实例职责及父节点。宿主不需复制求解器；当前未接主游戏。

交付包runtime_packages/experiments/0.9.0-experiment及receipt记录不可变源码commit、ZIP SHA、完整运行文件摘要、独立解压核验。readiness为research-prototype。真实成功样例、980005预算失败、980010搜索失败和jump-only失败均保留；失败无可用map/content_store。

该实验尚无按动作时间计算的分叉间隔，阶段职责也未扩展为每条路线的完整任务状态。主路线宏构造和奖励构造沿用v7。map-edit不需要为了本实验改外围或升级模块；若调查低频模块应先定位具体连接/封口冲突，再提出有证据的作者修改。无随机布怪或新增危险，地图附加物不参与本轮对比。
