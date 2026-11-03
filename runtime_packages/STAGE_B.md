# 阶段B：0.4.0 封口—奖励兼容候选

算法独立版本`stable-v3-reward-space`，实现`mapgen/gdscript-candidate-0.4.0`。基于阶段A的调度组件，**改变生成行为**；A的结果一致性证据不用于宣称B一致。模块仍锁1.1.0，runtime-map/v2及请求/配置/结果v1不升级。新profile与stable-v2只差algorithm标识，seed、目标、评分、搜索/墙钟预算、原模块内容不改。0.3.0、0.3.1和Python参考产物原样保留。

本轮补的是充分的静态排除检查，不是完整领奖可玩认证。依据map-edit PR78固定head `2ec243842567a56a49b84fc93ce4aa750b11ff5f`与1.1.0原运行代码：领取要求落地且角色中心在reward_sites.region。把每个未连接Port的实体封口按请求半身净空膨胀，得到禁止中心区域；只有其开区域并集覆盖整个领奖矩形（连边界也覆盖的更强充分条件），才拒绝。部分相交、仅相切、缺少资料均不能据此证明不可领取；其他站立、路径、能力、机制与物理仍UNKNOWN/NOT_RUN。

确认案例idea-orbit-choice-001的C封口[256,0,128,32]，半身[12,18]得到禁止区域[244,-18,152,68]，完全排除region[300,-10,80,56]。检查遍历每个模板的全部原reward_sites，包括没有Route奖励关联的普通奖励与Q目标奖励；镜像及源bounds偏移按同一物化规则处理，不移动/删除奖励，不打开未连接Port。每个实际封口配置仍须通过原Route/作者路径等检查。新充分冲突在configuration_ok缓存中拒绝，使用原候选预算继续搜索；预算/搜索未完成按协议失败，不换seed、不降目标。最终独立审计再检查所有实例的所有site。

诊断reward_seal_conflicts列出模块/内容版本、奖励ID、镜像、连接/封口Port、请求净空和区域证明。仅检查当前配置；拒绝一个已封死区域的部分搜索状态可能更保守，不是宣称模块永远不能使用。C开放配置保留可选性。新增检查不把包的全口原向证据提升为任意镜像/封口资格。

安装与预载/生成API同阶段A：`PreloadJob.create(zip,sha)`、advance/progress/cancel/result，完成库可复用；`GenerationJob.create(request,library,config)`，仅PASS有完整map/content_store。同一拥有者串行调度，退出先取消，宿主token不进请求。一个单位16检查点，不能解释为毫秒。seed±(2^53−1)、整数原点±10^9、距离分量±2×10^9，超范围拒绝。性能与输入到取消完成的实测以B自身evidence为准，不借A结果代签。

主游戏Provider当前签名仍是`load_level(request,map,content_store,selected_ids,spawn,source_sha256,bindings,source_record,binding_id="seam")`，已读PR127 head `e7d703f47c97f09bd5c5d48e24f0a400c958ad40`实际代码。bindings、source_record、选择范围、能力来源、生命周期信封及节点装配是宿主责任，算法不依赖LevelRequest/LevelPlan等类型。source_record的SHA必须对应实际验证的map、bindings、selection及content字节；新版本布局与实例选择可能改变，不能沿用旧固定实例选择或旧map_id。完整未知内容仍拒绝，不删除后冒充已接入。

包内samples是B新预期，生成器从不查询这些地图。独立解压验证：`godot --headless --path <包根目录> --script res://tests/verify_bundle.gd -- <显式ZIP>`。原始旧/新结果、逐seed差异、所有普通/目标site的独立源内容/几何审计、真实失败、预算/取消及实际Web均保留在对应B证据中。readiness=candidate；不签主游戏整图物理、可玩性、稳定帧时间或手机。

本轮无需改module包。map-edit后续若补领奖关联或配置资格，须显式选定源版本与兼容范围，本仓不自动切换1.1.1。安全出生/Boss绑定仍未解决；没有新增地图级移动齿轮、随机危险或随机布怪。

本次实际结果：40个历史seed全部生成PASS，连同冻结成功/失败、批次及取消共47例通过B自身检查；40张图全部发生布局变化。旧40图中33张被独立检查发现至少一个完整领奖区域被封口排除；新40图检查全部493个site，完整排除数为0。其余7张旧图也会变化，因为检查在前瞻/预留与当前候选阶段统一执行，原本不会出现在最终图的冲突候选也会改变可选项、排序及后续随机调用；这不是只替换最终图中的环岛模块。

默认930001：46实例不变，连接55→58，求值90,831→87,175，原site总数11→12，目标仍6/主路仍3。拒绝证明同时涉及idea-orbit-choice-001/reward及batch30-n19-west-high-east-low/folded-cache；没有改源奖励区域，而是选择了其他合法组合。独立Python审计对源内容、实际图及所有普通/目标奖励逐项检查；旧/新原始结果和拒绝证明完整保留。

13项几何/真实模块检查覆盖原向/镜像、普通无关联奖励、真实Q目标奖励、C开放、部分相交、相切及封口并集。候选预算1在第2次拒绝、墙钟原检查间隔、错误算法不回退等负例通过。真实Web重复完整生成/失败并按Escape取消：预载输入到完成27.5ms（排队26.5ms），生成21.9ms（排队20.5ms）。Web默认advance(1)最大26.2ms，仍未达到4ms p99/8ms最大值目标；不能把不同布局下的总用时当纯性能优化对照。
