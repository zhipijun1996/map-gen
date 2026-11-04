# 每个源模块的实际使用频率

完整结果：[可搜索、排序表格](index.html) · [全部115行CSV](usage.csv) · [计数与输入SHA](usage.json) · [Godot局部组合穷举](local-census.json)。不修改算法、SDK或已有包。

## 样本与结论

同一批60个seed：271028–271047、930001–930020为已用于选配置的40个回归seed；930021–930040为提前固定的额外20个seed。全部原始结果保留，本次只读取已有结果，没有重跑挑选。40/20分组数据同时保存，不能把60个当成全部未见样本。

| 指标 | 默认配置 | 可选varied-v1（repeat=8） |
| --- | ---: | ---: |
| 地图数 | 60 | 60 |
| 全部模块实例 | 2711 | 2739 |
| 使用过的源模块 / 库总数 | 70 / 115 | 75 / 115 |
| 零使用 | 45 | 40 |
| 有使用，但仅出现在1–3张地图 | 31 | 27 |
| 前5个普通源模块占普通实例 | 51.95% | 39.97% |

默认40张取自0.4.2默认，默认额外20张取自0.4.1原结果；前者已与0.4.1完整行为对照一致。varied60张全部来自0.4.2。算法为stable-v3-reward-space；模块固定1.1.0，SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`。

按真实`module_id`计数，合并镜像与T/Q内部别名；同模块在同地图重复出现，实例次数多次累加，seed覆盖只计一次。分别保留start/boss/traversal/target_reward角色。起点和Boss每图各1个是请求绑定，不是随机偏好。普通模块也可以有真实奖励；target_reward是生成角色，不能当成“模块有无宝箱”。

### 最常用普通模块

下表次数仅统计traversal角色；完整表还包含奖励角色和每个模块的地图覆盖。

| 源模块 | 名称 | 默认次数 | 新配置次数 | 新配置覆盖地图 |
| --- | --- | ---: | ---: | ---: |
| idea-interface-s12-001 | 错时交叉换乘：一趟车，四个去向 | 298 | 218 | 60/60 |
| idea-spec02-s12-001 | 横台稳住，再择高台去向 | 287 | 204 | 60/60 |
| game-plains-fork-paths | 分岔路径 | 225 | 175 | 60/60 |
| workshop-macro-gate-brake-return-0 | 四口错层中庭 | 197 | 156 | 60/60 |
| game-route-junction | 路线枢纽 | 152 | 150 | 60/60 |
| batch30-block-n04-0-2 | 穿过的门，回来接住你 | 142 | 147 | 60/60 |
| b31-n06-fourport-two-low-ingress | 中庭双翼换桥 | 145 | 134 | 60/60 |

## 为什么有的用不上

用锁定Godot4.7.2及当前实际solver执行局部诊断：115模块、两种镜像、每个非终端T/Q模板的全部非空连接Port子集。先按当前候选规则检查可入方向、能力、无需邻居夹具的向前/奖励Route，再调用原`configuration_ok`检查作者路径和所有奖励空间与封口。复用实际实现，不用另一套Python规则判断。

四能力回归请求下：109个非终端模块存在至少一个合法局部组合，2个固定终端，4个没有候选路线。新配置零使用40个中，36个局部可行，4个无候选路线；没有出现“有候选路线但所有局部子集都被封口拒绝”的模块。

4个明确障碍（完整ID和Route证据见usage.json）：

| 源模块 | 名称 | 原因 |
| --- | --- | --- |
| generated-09efd9583360ae3e414d7430c9b0e7e12a730b0fe8a5f19a90fc98c9b80c2ac2 | 左射开门，蹬墙折返 | 唯一路线entry-to-exit要求wall_climb；本批请求没有该能力 |
| generated-75b420621682d36fc3b7262784c347f0acea7e55422f7e0abaebbc285fa89198 | wall-slide-launch-window-v5-0 | 全部6条路线要求wall_climb |
| idea-0363f85c-16c0-4b5f-b3b0-461335608db7-enemies-3 | 左右交替命中，反冲接力上升·3怪 | A-to-B依赖testNeighborFixtures；另一条A-to-A仅返回本入口，不是普通模块的向前路线 |
| idea-96ba6bf1-9b60-470a-9128-54ae7ea44af3 | 错相升井：四台换乘，三道横锯 | 同上，向前路线依赖邻居测试夹具 |

其余36个不能因此说“模块坏了”。例如斜射开高门、摆渡上升挑战、长距离跨越、双钩连续腾空、侧钩刺口均有合法局部组合，但本批新地图零使用。局部存在组合不保证能在当前地图找到合适邻居或空间，也没有证明它满足全图回程、Boss路径和最终目标。评分、接口几何、全图约束或有限候选搜索可能影响选择；本次没有逐个隔离这些原因，不能归咎于其中某一项。

稀有模块也会随seed/配置变化：原默认零使用的13个在新配置中出现，另8个原来用过的变为零，净增5个。反冲深沟、齿轮溪流、尖刺缺口等新配置各出现1次；奖励/能力/接口条件并未放宽。60图零使用是观察值，不是全seed永远不会使用的证明。

### 与主游戏能力的区别

这60图请求有jump/double_jump/shot_recoil/grapple、净空12×18半尺寸。主游戏已捕获controller请求只有jump/shot_recoil，同净空。本次另外对该两能力请求做相同局部诊断：99个非终端局部可行、2个固定终端、14个无候选路线，比四能力请求多排除10个（包括双钩连续腾空、树腹空腔、回望果实宝藏、反冲深沟等）。

两能力上下文仅是局部能力诊断，没有60图频率样本；表格中单列controller_eligibility，不将四能力频率冒充正式游戏频率。Route的availableAbilities现被现有算法作为整组所需能力处理，此处按现行语义报告，没有改为猜测最低能力集。

本次不证明实际物理、跨缝或完整领奖可玩；全连Port子集可能无法找到真实邻居，亦不承诺每个可行模块都应该被强制使用。分析不修改模块内容、能力、封口或生成目标。

## 重现

先用现有安装方式将当前19个addon文件安装到独立Godot项目，将`runtime_iteration/library_census.gd`复制到该项目根目录。用锁定Godot4.7.2执行（替换实际路径）：

```sh
godot --headless --path /tmp/mapgen-census --script res://library_census.gd -- \
  /absolute/modules-1.1.0.zip \
  /absolute/map-gen/godot_runtime/tests/request.json \
  /absolute/map-gen/godot_runtime/tests/config.json \
  /absolute/map-gen/runtime_iteration/upstream/controller-request.json \
  /tmp/local-census.json
python -m runtime_iteration.tools.module_usage \
  --modules /absolute/modules-1.1.0.zip --census /tmp/local-census.json
```

Python命令在map-gen根目录运行，模块ZIP必须SHA匹配；诊断入口验证ZIP和成员，再复用库。`usage.json`记录120份不重叠原始结果文件SHA、当前19个实现文件SHA和局部诊断SHA；60汇总只合并各自40+20，没有计入批次重放、取消、失败用例或被淘汰配置。每组验证实例数守恒、角色数守恒、覆盖数不超过seed数、所有源ID属于115模块库。固定数据期望PASS，若有失败会报错，不会跳过。
