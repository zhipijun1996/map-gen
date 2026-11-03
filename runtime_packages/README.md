# 独立候选交付

- [阶段A 0.3.1](STAGE_A.md)：stable-v2结果不变，增加可取消预载、库复用和细分调度。[独立包及SHA](releases/0.3.1/receipt.json)，[47例原生](../validation/runtime-scheduling-A/replay/summary.json)，[实际Web与输入到取消延迟](../validation/runtime-scheduling-A/web/summary.json)。性能目标未全达到，奖励封口缺陷仍保留。
- [阶段B 0.4.0](STAGE_B.md)：独立算法stable-v3-reward-space，修充分的封口—领奖区域排除。[独立包及SHA](releases/0.4.0/receipt.json)，[新预期](../validation/runtime-reward-B/replay/summary.json)，[逐seed差异与所有奖励独立审计](../validation/runtime-reward-B/validity.json)，[实际Web](../validation/runtime-reward-B/web/summary.json)。A的结果一致证据不代签B。

两者仍是Godot Standard纯数据GDScript候选、模块1.1.0、runtime-map/v2。0.3.0和Python参考不修改。当前开发源码在godot_runtime，安装应以所选版本独立ZIP为准，不能混用两个版本的组件。结果、请求/配置/模块锁和manifest均随包提供；生成不运行Python或查询样例。宿主bindings/source_record/调度信封及节点装配保持独立。

算法种子/目标/默认参数不为通过而调整。每个包在仓库外实际解压执行verify_bundle；source commit与所有文件SHA见manifest/receipt。实际物理与主游戏可玩性、手机和硬帧时限均未签通过。不自动合并或部署。

0.4.1 性能修订继续 stable-v3-reward-space，保持 0.4.0 全结果语义；[调用及缓存合同](../performance_revision/README.md)、[旧新实际性能和未验证项](../performance_revision/REPORT.md)。它独立版本化，原包保持原样。

[0.4.1 独立候选包与准确换锁交接](../performance_revision/HANDOFF.md)（含 SHA、固定下游版本准入位置及未验证项）。
