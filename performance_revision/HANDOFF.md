# 0.4.1 候选交接

源码 commit：`8eefdbd140ce10defe1570ab8eefb6729382f8b3`。工作分支 `feature/godot-performance-0.4.1`，基于 PR5 固定 head `6bf07ab5a655ea056461b935ae4354e15ef83482`；PR5 仍未合并，因此本轮 PR 叠在其分支上。

独立包：[mapgen-godot-candidate-0.4.1.zip](../runtime_packages/releases/0.4.1/mapgen-godot-candidate-0.4.1.zip)，3,608,539 字节。

SHA-256：`f5c84e5e51dff01d16429783b957c0d5214056b9d2fea47a830baac12ecedb4e`。

[构建收据](../runtime_packages/releases/0.4.1/receipt.json)、[独立验证及重建收据](../runtime_packages/releases/0.4.1/verification.json)、[旧新性能/局限](REPORT.md)、[机器报告](../validation/performance-0.4.1/report.json)。包内 `manifest.json` 含源码身份、19 个 addon 文件 pin、全部文件摘要、模块锁和样例入口；`evidence/report.json` 含完整对照及测试来源。

算法继续 `stable-v3-reward-space`，实现改为 `mapgen/gdscript-candidate-0.4.1`；协议仍 `generation-request/v1`、`generator-config/v1`、`generation-result/v1`、`runtime-map/v2`。模块 1.1.0 的 SHA 仍为 `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`。0.4.0 原包 SHA `7aa3f0e573675c3bb41e2a2a5b23254c4005bb8eaef9756535e3a6480988d778` 和旧预期不变。

## 下游使用

1. 按完整 ZIP SHA 验证并解压包，读取 manifest 和 19 个 `addon_files`。运行：

   ```sh
   GODOT --headless --path PACKAGE --script res://tests/verify_bundle.gd -- PACKAGE/tests/dependencies/modules.zip
   ```

   实测引擎为下游原锁定 `4.7.2.stable.custom_build.gunman_sd1.ed1daf0bf`，二进制 SHA `eeaec2b65dc3234168be1e1cbcc89731514bbb78dfb2c1b502920c50830a0638`。包的运行和校验不需要本仓库目录或 Python。

2. 明确执行 0.4.0→0.4.1 换锁：校验旧 18 个文件原 pin 后更新原 addon、新增普通脚本资源 `derived_library.gd`，以新 manifest 的 19 文件摘要安装。继续唯一原模块 ZIP、两个原请求、原配置，更新 algorithm-package 的版本/ZIP SHA/source commit/release head。包的源码 commit 与含 ZIP 的提交分开记录，release head 使用本轮 PR 的实际含包提交。

3. 固定 gunman-rush `46eb3960a592374b5fb99d7df588962a3680f86b` 的版本准入尚写死 0.4.0：

   | 文件 | 位置/动作 |
   | --- | --- |
   | `tools/install_mapgen_candidate.py` | 固定 archive/实现/package 与 addon pins；旧升级分支仅支持 0.3.0→0.4.0，需明确增加 0.4.0→0.4.1 换锁 |
   | `experiments/generation/runtime_map_generation_job.gd:340` | lock version 准入同步 0.4.1，保留与 Protocol 的相互校验 |
   | `game/world/levels/providers/runtime_map_v2_provider.gd:143` | implementation 准入同步 `mapgen/gdscript-candidate-0.4.1` |
   | 同 Provider `:151` | algorithm package version 准入同步 0.4.1 |

   原 blob、准确 URL、只读行摘录见 [host_calls.json](upstream/host_calls.json)。这些版本锁值必须跟随显式升级；当前 head 只换 JSON 锁会拒绝。调度循环、Provider 转换函数、bindings/source_record 和地图结构没有新增接口要求。本仓库未改主游戏，也未声称其固定 head 已装载新包。

4. API 继续 `PreloadJob.create(path, sha)`，逐帧 `advance(1)`，通过后复用 library 调用 `GenerationJob.create(request, library, config)`。维持原 128 单位上限/软 8ms；单位为 16 检查点，不是毫秒。进度用 progress，终态才用 result；失败无可用 map/content_store。宿主仍守卫 run/stage/actor lifetime、opaque ticket，装配留主线程。可选第三参数 `false` 强制原 JSON 解码；普通调用无需更改。

5. 原样运行下游原请求及原双 fresh/300 秒 consumer，分开记录 preload、SDK active/tick/wall、validate/assemble/physics 和工具图像时间。不得沿用旧实现指纹或旧宿主内容身份；完整新结果未移除任何实例、Route、封口、奖励或其他内容。实际来源的 fingerprint 由新 Protocol 生成：

   | seed | 新 fingerprint | 展开数 |
   | --- | --- | ---: |
   | 930001 | `f1d24aa1d5d8f3087202b3e933708d4f42a74cb1465947413e40e5037391caf8` | 87175 |
   | 930007 | `84d94b05e86a00a507ef0de8cac9f407a6dbd9dd7662a505ac182402c8ead918` | 88856 |

包内 `samples/success/`、`samples/gears-930007/` 包含原 request/config、完整 result/map/content_store 及每个 ref 对应文件；`samples/failure/` 是原真实失败请求及 SEARCH_EXHAUSTED 空结果。样例是验收向量，运行时必须真实生成。

## 实测及边界

| 独立真实 Web | 0.4.0 墙钟 | 0.4.1 墙钟 |
| --- | ---: | ---: |
| 预载 | 26.374s | 4.246s |
| 930001 | 57.561s | 34.501s |
| 930007 | 51.814s | 27.192s |

原生对应生成 active 降低约 36%；Web active 降低约 39%/47%。第二独立 fresh 的 930001 为 35.238s。冷/热完整预载、库复用、结果复制、真实 Web 失败及输入取消均有原件。搜索 trusted 输入到取消完成约 11.8ms，预载约 23.8ms，包含排队；仅为观测值。

47 完整对照通过（含原 40 seed、失败、批次及三阶段取消），所有正常终态只差实现身份及耗时。另有 1/17/128/4096 批次、完整结果快照、共享库取消隔离、409 decimal/4 seed/1005 hypot、123 foundation、13 geometry、预算负例、Python 接口14/参考7、prototype 和旧20 seed replay 通过。首轮测试的两项问题及修正保留在报告，不删除失败原件。

保留的限制：Web 单次推进最大约 32ms，原生冷缓存脚本加载约 75ms；总耗时改善未消除长原子步骤。完整主游戏 218MB PCK、主游戏双 fresh 300 秒、全部物理/跨模块 Motor、手机和硬帧时限未验证。固定下游旧约72s与本地旧约58s的差距未因果归因，不全算算法 CPU，也不泛称宿主故障。包仍为 candidate。

map-edit 本轮无需补字段或改库；没有切换1.1.1。全图玩法锚点/机制/实际物理准入和旧 helper 与合法封口的宿主适配缺口仍由后续独立验证承担，性能修订没有改变这些地图内容。本轮不增加随机危险/随机布怪，不自动合并或部署。
