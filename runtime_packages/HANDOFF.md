# 两阶段交接

主游戏核对head：`e7d703f47c97f09bd5c5d48e24f0a400c958ad40`；map-edit审计head：`2ec243842567a56a49b84fc93ce4aa750b11ff5f`。

| 阶段 | 源码commit | 独立包与SHA-256 |
| --- | --- | --- |
| A，0.3.1，stable-v2调度 | `24ae03e8b3c0b80dbc22d8ec0b68ac973466e6be` | [ZIP](releases/0.3.1/mapgen-godot-candidate-0.3.1.zip)，`68b9d5efe5e6e1b38998a84d1a8bac1d0cf2830b8740aaa669c36eb053d76252` |
| B，0.4.0，stable-v3-reward-space | `b21c889077ec97eb11a210d0ceab4fbddd862e48` | [ZIP](releases/0.4.0/mapgen-godot-candidate-0.4.0.zip)，`7aa3f0e573675c3bb41e2a2a5b23254c4005bb8eaef9756535e3a6480988d778` |

每包都在独立临时目录从实际ZIP解压，执行`tests/verify_bundle.gd`通过。manifest列所有文件SHA、算法/实现/协议/模块锁、支持域和来源。模块ZIP仍1.1.0，SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`；不自动升级。0.3.0与Python参考、旧seed/参数/产物未改。

A是独立[PR4](https://github.com/zhipijun1996/map-gen/pull/4)：42例完整旧结果一致，含批次及取消47例通过；**保留原奖励缺陷**。有可取消预载和库复用、细分搜索/检查/导出及纯缓存；新增实现身份参与指纹，布局/图/内容/计数不变。详细调用和性能见[阶段A合同](STAGE_A.md)。

B独立版本并建立新预期：40seed均生成PASS、全部布局改变。独立检查旧图33/40有完整领奖区域排除，新40图493个site（249普通/244目标）没有发现此完整排除，所有源内容/图/封口校验通过；默认930001仍6目标/3主路，连接55→58、求值90831→87175。13项几何/真实模块测试和预算/不回退负例通过。[逐seed新旧差异及证明](../validation/runtime-reward-B/validity.json)、[新完整原始结果](../validation/runtime-reward-B/replay/summary.json)、[阶段B合同](STAGE_B.md)。这些不构成完整领奖路径/站立或地图物理认证。

两个阶段都实际执行Godot Standard4.6.3原生及单线程Web导出/Chromium，浏览器使用trusted Escape事件时间戳量输入到取消完成：A预载15.2ms/生成8.4ms，B预载27.5ms/生成21.9ms，包含排队和宿主调度，未用cancel()函数耗时替代。[A Web](../validation/runtime-scheduling-A/web/summary.json)、[B Web](../validation/runtime-reward-B/web/summary.json)与各自原生报告按阶段保存总时长、每次推进max/p50/p95/p99、帧越界和结果快照耗时。

**性能目标未全达到。** 目标advance(1)各阶段p99≤4ms/max≤8ms；实测Web默认最大A32.1ms/B26.2ms，部分阶段p99超标。ZIP单文件解压、部分快照和小规模几何仍有原子耗时；操作单位16检查点不是毫秒保证。A/B的不同布局/运行负载不能直接比较优化倍数。候选不标生产就绪；主游戏完整物理/可玩性、手机和硬帧预算仍未验证。

主仓应安装选定ZIP的整个`addons/mapgen`，不混装版本、不复制算法。使用PreloadJob显式加载并复用库，以真实能力快照/配置创建GenerationJob。宿主保存run/stage/actor信封，串行推进与取消；结果入队、节点创建每批、最终提交都核token/fingerprint。纯算法不认识LevelRequest/LevelPlan、bindings或source_record；现有Provider九参数用法见两份合同。bindings/selection及实际map/content字节的SHA由宿主核验，不伪造source_record。新B布局不能盲用旧固定实例选择；未知内容保持拒绝。未自动合并、未发布网站。
