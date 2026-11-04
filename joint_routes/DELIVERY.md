# 本轮交付记录

源码commit：`97d4e4bc99a97ceac991ccaaf96f78aecd912d22`。产物commit：`d9dbe604707700a0191973a6d03028a80adfa661`。此后交接文档提交不改写包内源码身份。基线为PR #9 head `47e661f9f6049d8fb701007c6af85efe2ead1e03`，工作分支`experiment/joint-reward-planning`，依赖PR #9，不自动合并。

- **candidate**：[mapgen-godot-candidate-0.5.1.zip](https://raw.githubusercontent.com/zhipijun1996/map-gen/d9dbe604707700a0191973a6d03028a80adfa661/runtime_packages/releases/0.5.1/mapgen-godot-candidate-0.5.1.zip)
  - SHA256：`3c7c173e17d67eb04723cb9e856e89c4d974c082274a393818767ebc71940928`
  - 实现：`mapgen/gdscript-candidate-0.5.1+002f012d94cb`；20运行文件。
  - 独立verify_bundle 162项、CLI完整重放均PASS；[收据](../runtime_packages/releases/0.5.1/receipt.json)。

- **research-prototype**：[mapgen-godot-experiment-0.6.0-experiment.zip](https://raw.githubusercontent.com/zhipijun1996/map-gen/d9dbe604707700a0191973a6d03028a80adfa661/runtime_packages/experiments/0.6.0-experiment/mapgen-godot-experiment-0.6.0-experiment.zip)
  - SHA256：`4f6195a01bc6e08774c79299e9bdf51ba9a2585396735ca3db1d3bdeb344c2a7`
  - 实现：`mapgen/gdscript-experiment-0.6.0+3738e5100505`；22运行文件。
  - 独立verify_bundle 211项、CLI完整重放均PASS；[收据](../runtime_packages/experiments/0.6.0-experiment/receipt.json)。

以上为绑定产物commit的不可变原始下载URL，不是latest，也未发布GitHub Release。两个包都包含显式配置、Schema、20/22文件锁、完整成功/失败样例及引用内容、锁定模块ZIP测试输入、Godot工具链锁、调用与验证脚本、manifest和证据摘要。源码与产物路径分离，旧包保持原样。

[调用合同](HANDOFF.md)与[报告](REPORT.md)明确候选区别。优先评估0.5.1的等价性能收益；0.6.0-experiment不作默认替代。实际主游戏装载、性能与物理认证本轮NOT_RUN。

检查：80四能力冻结行为、40两能力旧行为（含3失败）、联合规划40+20两能力、两套32项Job合同、数值9828项、索引/安全界13600项、29项真实Web审计、历史20seed重放均按各自预期通过。0.5.0基线40例中的3例失败仍在原日志中，不改成PASS地图。无GitHub自动工作流checks；本轮执行证据在`validation/joint-reward-20261104`。

模块仍1.1.0 SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`，地图runtime-map/v2。安装需更换完整文件锁、实现准入及恢复身份，Provider转换合同不变；主游戏不复制求解器。
