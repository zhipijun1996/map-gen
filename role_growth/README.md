# v8 / 0.9.0：路线职责生长实验

独立于v7/0.8.0及地图附加物0.1.0的新算法实验，`experimental-v8-role-aware-growth`。纯数据GDScript，模块1.1.0和runtime-map/v2；不是正式替换版本。

当前作用范围：普通生长和填充。保留v7的联合奖励归并、闭环、五条多模块折返，以及原有全部Route、封口、奖励净空检查。32/6/3、90秒/500000候选预算保持原样。

- 主路结构尚未完成时，保留分叉供给职责；结构完成后普通延伸只奖励必要的后续出口。
- 首个生长位置优先考虑面积≥24Block²、至多两Port的普通挑战模块；结构完成后的填充可补足大型挑战数量。是显式偏好，不虚报硬保证，也不是按面积认定玩法时长。
- 在入围位置上构造实际有向图：从START可达的来向具有至少两个不同已连接非原路出口，才算声明图分叉。惩罚新增的分叉相邻连接，保留构造必需主路线的例外。
- 逐模块记录索引命中、权限/对齐/重叠/入口路线淘汰、生长排名、合法性和入围/提交次数；计数包括回退与失败尝试，最终使用次数另外统计。

当前是阶段职责和实例父节点记录，尚不是每条路线具有持久任务状态的完整规划器；大型挑战只实际提前放置首个候选，并没有实现任意多段的空间预留系统。分叉间距采用实际相邻实例作为首轮指标，尚未按动作时长计量；宏构造/奖励阶段也未加入相同惩罚。

独立包使用见[PACKAGE_USAGE.md](PACKAGE_USAGE.md)，以下为仓库开发复现：

```sh
python -m role_growth.tools.setup --out /tmp/mapgen-role-v8
python -m role_growth.tools.run --project /tmp/mapgen-role-v8 \
  --out /tmp/mapgen-role-results --godot /absolute/locked-godot-4.7.2 \
  --controller --seeds 930001,930007
```

[预登记计划](plan.json)、[冻结配置/源码锁](../validation/role-growth-20261105/selection.json)、[效果报告](REPORT.md)、[同seed地图与模块漏斗](comparison/index.html)。所有校准失败、正式40seed及全新10seed原件保留在validation/role-growth-20261105；禁用growth_roles.enabled的配置用于带观察计数的v7对照，不作为失败回退。

不改主游戏/map-edit、不升级模块、不更改旧包/预期、不自动合并或部署。地图级齿轮和告示牌不参与本轮核心算法评估。静态生成与数据校验不等于整图物理或主游戏可玩认证。
