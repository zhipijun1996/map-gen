# 0.4.2 速度与多样性候选交接

分支 `feature/runtime-speed-variety`，基线 main `b15c32e045347e0fcf282d541ea3eaa4661f0835`。本轮优化 map-gen，为后续正式接入准备；没有修改主游戏/map-edit，也没有自动合并或部署。

- 独立包：[mapgen-godot-candidate-0.4.2.zip](../runtime_packages/releases/0.4.2/mapgen-godot-candidate-0.4.2.zip)，4,925,854 字节。
- 不可变 URL：<https://raw.githubusercontent.com/zhipijun1996/map-gen/0b7c83091e3bc2b051cc66980868a9f4335ba189/runtime_packages/releases/0.4.2/mapgen-godot-candidate-0.4.2.zip>
- ZIP SHA-256：`da68a3e12fef1554c0eb6e6fc5451b4fedcc28470d4e9079cee75c48b4b853b4`。
- 实际源码：`5d128a207c1532354a11b0995d4a34b1c9168dfa`；产物提交 / release head：`0b7c83091e3bc2b051cc66980868a9f4335ba189`。后续 PR head 或 main merge 不替换这两个身份。
- [独立解压及重建校验](../runtime_packages/releases/0.4.2/verification.json)：411 项通过，重新构建 ZIP 逐字节一致，19 个运行文件与受测源码相等，8 组样例的275个内容引用全部解析。

算法仍 `stable-v3-reward-space`，实现为 `mapgen/gdscript-candidate-0.4.2`；继续 request/config/result v1 与 runtime-map/v2。模块仍1.1.0，SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`。0.4.1及所有旧包、默认配置与证据未改。

## 两种明确选择

| 配置 | 行为与验收 |
| --- | --- |
| `profiles/stable-v3-reward-space.json` | 原默认配置；47例完整结果除声明身份/耗时外与0.4.1相同，含原40seed、失败、批次和取消 |
| `profiles/stable-v3-varied-v1.json` | 可选；仅 `scoring.repeat_module` 从5改为8。原40和另外预先固定的20个新seed均生成PASS并通过独立源内容/图/封口/所有奖励检查；另有失败、批次、取消 |

没有添加隐藏配置、随机流或新算法协议。新配置会真正改变布局、源模块选择、随机状态和搜索计数，配置本来就参与确定性指纹；它不是纯计算优化的同结果证明。不会在失败时隐式换回旧配置。原32/6/3目标、形态/封口检查、90秒/500000预算及其他搜索参数不变。

先以原默认配置升级SDK，再由主游戏明确决定是否选varied-v1，并锁定对应配置文件。不要仅为减少等待而减少目标/内容或放宽预算。

## 实测效果

[40张同seed交互对照](comparisons/index.html) · [完整报告](REPORT.md) · [机器证据](../validation/runtime-iteration-20261104/report.json)。视图可切换模块布局与静态平台/封口/领奖区域，保留整批40张；完整生成结果独立保存，不以视图替代地图协议。

原40图普通模块种类均值17.3→21.475（约24%增加）；合并镜像后的Port/Route源结构类型15.3→19.4；重复邻接13.7→9.5（约31%减少），跨seed邻接相似度0.206→0.151。宏观占用相似度0.332→0.337未改善，旧/新精确重复布局都为0。本轮减少局部模块/邻接重复，未证明玩家主观重复感或宏观探索结构已解决。

同一4.7.2 custom的独立真实threaded Web：

| 请求 | 0.4.1默认 | 0.4.2默认 | 0.4.2 varied-v1 |
| --- | ---: | ---: | ---: |
| 930001 | 29.432s | 27.097s | 29.062s |
| 930007 | 25.621s | 23.177s | 23.108s |

默认同结果提速与新配置不同地图的耗时分开。新配置不是每seed更快；额外20个seed的尾部存在变慢，详见报告逐seed表。预载实现未改，不能宣称预载提速；已验证library可复用。原生和Web分别实测，不代签主游戏200MB以上PCK、装配/物理/审图或整段收益。

真实trusted Escape输入到取消完成：预载约22.3ms、生成约20.5ms，包含排队。长原子步骤仍存在，软8ms与16检查点单位不是硬帧保证。readiness保持candidate/production_ready=false。

原生还重放了主游戏实际历史controller请求：jump/shot_recoil、净空12.0/18.0，准确复现旧指纹214cdc2359984f665e7b4a2609f3f055df155e10c13cd46b57dd983e13b23b74；新默认与旧完整结果只差身份/时间，新配置也通过。没有授予双跳/钩索，没有重新执行主游戏消费者。数值/随机向量、8001项正反可达/整数key检查、缓存/共享库隔离、预算、Python接口14/参考7、原型和旧20seed保护均通过。

## 主游戏0.4.1→0.4.2升级

实际只读核对 gunman-rush main `48cddb6a70983b0a0206304d18c98d274a9a7549`。普通出发仍是旧Plains/Forest Provider，0.4.1在开发入口；本轮不是正式切换。

1. 按上面的不可变URL/SHA校验包，解压后运行：

   ```sh
   GODOT --headless --path PACK --script res://tests/verify_bundle.gd -- PACK/tests/dependencies/modules.zip
   ```

   已实测引擎 `4.7.2.stable.custom_build.gunman_sd1.ed1daf0bf`，二进制SHA `eeaec2b65dc3234168be1e1cbcc89731514bbb78dfb2c1b502920c50830a0638`。工具链锁随包，运行不依赖Python或仓库实验目录。

2. 安装器校验旧0.4.1的19文件pin后，再安装新manifest的完整19文件；同步archive URL/SHA、implementation、package version、source commit、release head和输出锁。保留路径安全/旧版本拒绝，不盲覆写或混装；不用把参考包、证据、对照页复制进主游戏PCK。
3. 对上述主游戏固定head，`tools/install_mapgen_candidate.py` 的0.4.1锁/准入同步0.4.2；`experiments/generation/runtime_map_generation_job.gd:416` 的lock version同步0.4.2；`game/world/levels/providers/runtime_map_v2_provider.gd:159` 的implementation与`:167`的package version同步0.4.2。算法名保持stable-v3-reward-space，所有来源互校验保留。
4. API仍为 `PreloadJob.create(path,sha)` → `advance/progress/cancel/result` → library复用 → `GenerationJob.create(request,library,config)`。同owner串行推进，节点装配由主线程；run/stage/actor token留宿主信封。主游戏无需重写求解器、调度或装载架构，也不复制算法。
5. 先用原默认配置验证旧切片/机制准入，再明确选可选配置。新配置不保证原固定seed仍含某个机制或原实例编号，不能沿用旧M编号/固定邻接/出生选择或“930007必有gears”的假设；应沿实际模板/版本/连接解析，并对未支持内容保持拒绝。
6. 新实现身份及配置都参与指纹；不得沿用旧request_fingerprint、map_id或恢复/宿主内容身份。完整map/content_store及实际输入都保留，失败仍无可用地图。主游戏继续使用真实能力快照，不把全能力参考请求当作能力授予。

原0.4.1 ZIP SHA仍为 `f5c84e5e51dff01d16429783b957c0d5214056b9d2fea47a830baac12ecedb4e`，回退应恢复整套旧SDK/配置/来源身份，避免混版本。

## 原件与剩余边界

两个未采用的配置完整保留：首组38/40、第二组39/40，原预算内没有找到合法Boss/奖励组合，未删失败或放宽检查。历史目录`varied-final`是第二组失败试验，最终采用的是`varied-v3`，以summary/report状态和配置SHA为准。

map-edit本轮无需增加字段或升级1.1.1。保留所有被选模块的原机制、敌人和奖励；没有新增地图级随机危险或随机布怪。全图动作、跨缝、出生、真实奖励/敌人/Boss消费者、设备与玩家认可仍待后续主游戏验证。完成本候选交付后等待明确反馈，不自动展开新架构、合并或部署。
