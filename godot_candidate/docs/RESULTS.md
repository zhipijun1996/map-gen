# 0.3.0候选结果

实际算法代码commit与完整文件SHA以独立包manifest.source和release receipt为准。包目标为`godot-standard-gdscript`，readiness为candidate，production_ready=false。Python参考0.2.0仍为`python-reference`，原ZIP SHA保持`25f05861b68a99eee1e9d588eb2cab761e30c85b7cc109b0536292fcc98867f6`。

| 实际检查 | 结果与证据目录 |
| --- | --- |
| 冻结数值与库 | foundation-final：支持域的CPython随机流、状态/恢复、shape binary64、稳定排序；409个decimal token、4个边界seed；115模块/139模板全部字段与顺序、278份完整内容一致。两个大整数seed明确不支持，未记作通过。 |
| 距离精度 | precision：1,005个CPython hypot向量逐bits通过。旧候选sqrt写法在114个向量差1 ULP，已修正，原Python预期未改。 |
| 完整生成 | replay-precision：原40个seed+冻结成功/失败共42例，42/42通过；完整map除声明身份外、完整content、实际图、Routes、封口、选择及搜索计数一致，并经独立语义校验。 |
| 默认成功 | 930001：46实例、55连接、31镜像、40封口、6目标奖励、3主路，90,831候选求值；原18敌人和11奖励site保留。 |
| 真实失败 | 同seed、原失败能力快照：SEARCH_EXHAUSTED/growth_exhausted，196候选求值，2条原失败记录；map=null/store={}。不是无解证明。 |
| 调度/取消 | jobs-precision：同请求批次1/17/128/4096完整结果一致；32项预算、取消、导出不提前发布、快照、并行隔离及幂等检查。 |
| Web | web-final：Godot4.6.3 Standard真实单线程导出，Chromium154执行完整128/4096两种批次，成功/失败重放、取消、基础/精度向量、PCK原数据SHA及结果一致；无页面异常。 |
| 仓库保护 | protection：Python接口14项、参考合同7项通过；prototype及全部20个历史seed的原地图/原拒绝重放通过，历史4拒绝保留。 |

早期`replay/summary.json`为41/42，`web/summary.json`为FAIL：失败诊断少记录一次，地图和196求值已一致。对应源码与失败证据保留在`603dbd1`；`9f5b31d`修复并补导出取消检查点。后续修正整数hypot，再完整重跑40seed；没有更新旧预期、筛选失败或换默认请求/目标。

身份差异只来自新实现及其编码：默认Godot fingerprint为`9a5c671e93a6cbe2a11dde3e54fe2e722810bb5745d694f1b59921f6444639d7`，Python为`ffc781684ea67dc383a842034f95e5aa07118a8d89c65ac6821ab8099df55410`。跨实现只移除map_id、generator.implementation、generator.request_fingerprint三项做map语义比较；其他全部字段和content不忽略。Godot自身不同批次只忽略metrics.generation_seconds，原始结果均归档。

性能是候选限制：40例原生PASS用时约6.14–15.07秒（同机两任务运行，包含宿主推进/最终输出），不承诺设备速度。最终原生调度检查：批次1最大22.16ms，17最大52.92ms，128最大264.25ms，4096最大4.630秒，取消89µs。实际Web预载+首批向量约4.53秒；默认批次128最大一次推进517ms，4096最大一次6.865秒；取消响应观察值200µs，浏览器计时有分辨率限制。这些是真实长帧证据，不能把操作预算写成16ms保证。

下一轮性能工作：细分图/配置检查、稳定排序和快照等原子工作；将ZIP/JSON预载也做可调度适配；在真实主游戏和手机量测。未改变默认90秒来过关。算法输出的源机制不等于宿主已消费；整个地图物理、spawn→departure、Boss及结束结算、敌人奖励事务、主游戏取消提交和实体手机均未在本仓认证。
