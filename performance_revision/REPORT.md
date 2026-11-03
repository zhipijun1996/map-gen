# 0.4.1 性能与一致性报告

原件：0.4.0 / stable-v3-reward-space；新实现：mapgen/gdscript-candidate-0.4.1。输入、90 秒搜索配置、500000 候选上限、seed、目标和模块内容不变。本表是本机单次对照，附第二个独立 fresh 复验，不是统计性能保证。机器原始结果、阶段分布、取消事件及全部来源在 validation/performance-0.4.1/；包内有汇总 evidence/report.json。

## 同输入旧新实测

Godot 4.7.2.stable.custom_build.gunman_sd1.ed1daf0bf，二进制 SHA eeaec2b65dc3234168be1e1cbcc89731514bbb78dfb2c1b502920c50830a0638。Web 使用下游锁定的 threaded release 模板、Compatibility、COOP/COEP、软件 Chromium。两个版本都由单主线程调用 advance(1)，每 tick 上限 128、软 8ms。active 是每次 advance 内单调钟耗时之和，包含算法和调用内记账；不含主动让帧，不是 OS 线程 CPU 计数。残差包含让帧、渲染、桥接和宿主基准脚本，不能全部归为纯算法。构造请求/Job、引擎启动和导出也不在此阶段计时中。

| 环境 / 阶段 | 旧墙钟 s | 新墙钟 s | 旧 active s | 新 active s | 墙钟下降 |
| --- | ---: | ---: | ---: | ---: | ---: |
| native / preload  | 3.890 | 0.756 | 3.879 | 0.755 | 80.6% |
| native / generate 930001 | 9.467 | 6.036 | 9.418 | 6.017 | 36.2% |
| native / generate 930007 | 8.344 | 5.279 | 8.304 | 5.262 | 36.7% |
| threaded_web / preload  | 26.374 | 4.246 | 14.283 | 2.360 | 83.9% |
| threaded_web / generate 930001 | 57.561 | 34.501 | 31.409 | 19.159 | 40.1% |
| threaded_web / generate 930007 | 51.814 | 27.192 | 27.516 | 14.627 | 47.5% |

旧 Web 930001 残差 26.152 秒，新版 15.341 秒。下游原 preload 27.072 秒在此复现为约 26.4 秒；下游 SDK wall 71.843 秒在这里旧版约 57.6 秒，差距尚未因果归因。未运行其 218920072 字节 PCK、宿主物理或截图/审图工具，不能用这里的独立结果签主游戏 300 秒 consumer 通过。原报告图间 20–40 秒含工具往返/审图，未计为算法 CPU。

第二个独立浏览器 fresh 的 930001：preload 4.251 秒，generate 35.238 秒；完整结果除时间与首个 fresh 相等。同一上下文重新完整预载的冷/热墙钟为 4.112, 4.330 秒，均重新核验 ZIP 和 657 文件。热预载没有跳过校验；复用已验证 library 则可直接创建下一 job，主测试的 930007 使用同一 library。

## 热点与实际改动

原生诊断包装器的 self time（有额外计时开销，不能当发布性能）显示：930001 graph 3.366s、reachable 1.769s、growth_options 1.940s；配置检查 127538 次。原预载的 module_json 约 2.19s、catalog_json 约 1.07s，ZIP entry 约 0.48s，文件 SHA 约 0.06s；JSON 是主要优化对象。诊断中间版本配置调用降到 74289 次；原图/可达调用数仍为 3297/7761。完整诊断和未采用的较慢试验也保留。

- 使用绑定模块 SHA/实现的可重建源 JSON 派生缓存；保留整数类型和 binary64 位。缓存缺失/不匹配走原解析路径，篡改 ZIP 仍拒绝。每次读取完整 ZIP、解压原文件、验证整包 SHA 与全部 657 个成员；没有减内容或改成预存地图查询。
- 候选仍先执行原 candidate tick；相同整数严格矩形相交测试提前到纯 make() 分配之前，省去必被拒绝候选的 Port/镜像对象创建。
- job 内复用模块局部路线图、以不可变数组替代 JSON 状态键、用完整结构比较的图驻留池和引用身份复用可达性结果。缓存不共享求解可变状态，不消耗 RNG。
- 稳定排序显式以原始索引打破相同评分；比较器纯计算。可达性每八个节点检查取消，减少解释器协程开销。一个操作仍为 16 检查点，但总操作数会下降。
- progress 直接构造相同字段，减少每次推进的临时 Dictionary。最终审计/导出内容和结果快照合同保留。

新原生 930001 阶段 active（按 advance 入口归属，跨界调用计在入口）为：
  closure_search=0.217s, created=0.002s, export=0.008s, final_audit=0.015s, final_decorate=0.016s, final_gate=0.010s, goal_aware_terminals=3.162s, growth=2.464s, init=0.006s, prepare=0.008s.

Web 单次推进分布（毫秒；原始 report 另有每阶段 p50/p95/p99/最大及 tick 分布）：

| 阶段 | p50 | p95 | p99 | 最大 | tick 最大 |
| --- | ---: | ---: | ---: | ---: | ---: |
| preload  | 0.164 | 5.235 | 8.595 | 31.536 | 34.690 |
| generate 930001 | 0.269 | 3.665 | 6.490 | 29.820 | 32.685 |
| generate 930007 | 0.236 | 3.361 | 5.894 | 31.110 | 34.891 |

最大长步仍超过 8/16ms；原生首次加载缓存脚本约 75ms（跨阶段计在 zip_entries），Web 新最大推进约 32ms。原版 Web 最大推进约 23–28ms，因此总耗时改善不能宣称尾延迟改善。缓存加载、ZIP 单成员解压、原生排序和完整结果深拷贝仍有原子工作；没有硬帧/手机时延保证。软 8ms 只是单位完成后的让出目标。

## 快照、序列化及宿主边界

| 环境/seed | result() ms | 宿主再次 duplicate ms | canonical 序列化 ms | 引擎 JSON ms |
| --- | ---: | ---: | ---: | ---: |
| native/930001 | 5.604 | 10.116 | 52.966 | 17.097 |
| native/930007 | 5.199 | 4.477 | 46.805 | 16.642 |
| web/930001 | 5.475 | 6.019 | 68.360 | 22.875 |
| web/930007 | 7.500 | 4.600 | 59.514 | 22.500 |

固定宿主 runtime_map_generation_job.gd:295 使用 job.result().duplicate(true)，:332 再次复制 actual 后进入 Provider；:249/:289 每 tick 记录 progress。完整调用位置、原 blob 和 URL 见 upstream/host_calls.json。这些确实存在，但本次几毫秒的独立复制计时、下游原 validate 137.161ms 不能解释全部 72 秒生成。额外约 14 秒的宿主差距没有同场 CPU 栈证据，本轮不归责宿主具体函数。后续需在同一次下游运行记录 SDK phase/call total、frame/tick wall 和完整包时钟，沿已有 begin→preload→generate→validate→assemble→physics→commit 归属，而不是扩大 90 秒限额。

## 真实输入到取消完成

| 场景 | 输入→完成 ms | 事件队列 ms | handler→宿主观察 ms | cancel 内 ms |
| --- | ---: | ---: | ---: | ---: |
| derived_json | 23.785 | 10.205 | 6.945 | 6.635 |
| prepare | 29.185 | 24.650 | 4.480 | 0.055 |
| growth | 11.810 | 3.760 | 4.790 | 3.260 |

这些是 Playwright/CDP 发送的真实 trusted Escape 事件，使用 event.timeStamp→最终完成时 performance.now，包含队列等待；不是只计 cancel()。搜索取消时已有展开，结果 CANCELLED、map=null、content_store={}。原生另覆盖 growth/final_audit/export 和 created/prepare；并行交错 job 取消左侧后右侧 930007 仍通过且 88856 次展开。只证明这些观测，没有所有阶段/设备的最大响应保证。

## 行为、失败及保护检查

47 原件对照通过：40 个原 seed 全部保持完整结果、另有默认成功、真实 SEARCH_EXHAUSTED/196 失败、17/128 批次和三阶段取消。总计 43 PASS / 1 SEARCH_EXHAUSTED / 3 CANCELLED。jobs 另验证 1/17/128/4096 批次全结果相等、独立结果快照、输入快照、完成幂等及预算。取消发生位置随检查点改变可变化；取消之后不能额外推进。

| seed | 原指纹 | 新指纹 | 展开数 |
| --- | --- | --- | ---: |
| 930001 | 13f7f7f480168da132e64f478919450ca8bbe179e6614b9f30b5d0ac31c65772 | f1d24aa1d5d8f3087202b3e933708d4f42a74cb1465947413e40e5037391caf8 | 87175 |
| 930007 | deee1d69cc42840dfc5fae6648e8fc72f016dc2a450da53c94b787d30018f485 | 84d94b05e86a00a507ef0de8cac9f407a6dbd9dd7662a505ac182402c8ead918 | 88856 |

只投影 root request_fingerprint、map_id、map.generator implementation/request_fingerprint、diagnostics implementation、metrics.generation_seconds。没有投影布局、图、内容、RNG 状态、证明、拒绝计数或候选数。Web 两 seed 还与本实现原生完整结果（仅除时间）相等；Web 真实失败与旧失败按同投影相等，无可用 map/store。

foundation123、decimal409/seed4、hypot1005、reward_geometry13、budget5、缓存/共享库合同、jobs、Python 接口14/参考7、prototype 和旧20 seed replay 通过（原16可接受/4已知拒绝保持）。支持 seed 范围继续 [-9007199254740991,9007199254740991]，超出拒绝，不截断。缓存从锁定 ZIP 使用源 JSON 路径重建后逐字节 SHA 相等，所有源 JSON 递归检查类型/浮点位相等。

保留首次检查失败 checks-first：Python 参考测试因漏设 MAPGEN_REFERENCE_MODULE_ZIP 未启动，补上显式锁定路径后 7 通过；旧 jobs 取消断言硬写第17次展开，但单位布局优化后首次观察为30。改为断言观察到至少17次、cancel 后展开不变且空结果，原失败日志保留。没有改旧包/旧生成预期；其他检查原通过项未重复执行。

浏览器 console/pageerror 原日志保留。此次候选各浏览器运行没有 pageerror；这不是主游戏 audio/场景或整图可玩检查。此轮只实测 threaded Web，包里沿用的非线程示例导出 preset 未在本轮运行。

## 下游换锁的准确边界

固定 PR129 仅更换 JSON 锁仍会被版本准入拒绝：runtime_map_generation_job.gd:340 固定 version=0.4.0，runtime_map_v2_provider.gd:143 固定 implementation=...0.4.0、:151 固定 package.version=0.4.0；安装器也固定 archive/implementation/18 文件摘要。下游显式升级时应同步这些受锁版本值与新 manifest 的 19 文件 pin，保持原 provenance 相互校验和算法名 stable-v3-reward-space。调度循环、Provider 转换合同及地图数据结构无新增要求。本仓库只读核对，不修改主游戏；不能声称固定下游 head 已仅换锁运行了新包。

不复用旧实现指纹、旧来源存档或旧宿主内容身份。新包 release head/source commit/ZIP SHA 按实际交付填写；原模块/输入 SHA 不变。下游应使用原 8ms/128/advance(1)、两原请求、原 90 秒及原 300 秒整段 consumer 验证，不用本仓库独立 fresh 代签。map-edit 无新增字段需求；仍 1.1.0。没有添加危险/随机布怪，没有合并或部署。
