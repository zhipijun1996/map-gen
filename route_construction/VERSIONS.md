# 算法版本边界

| 包 | 算法 | 本轮角色 |
|---|---|---|
| 0.5.1 | stable-v4-reward-branches | 旧性能候选，保持原样 |
| 0.6.0-experiment | stable-v5-joint-reward-plans | 原基础成功率参照；不保证新归并风格 |
| 0.7.0-experiment | experimental-v6-structure-first | 先骨架后奖励；merge配置为同硬风格主对照，returns配置为另一风格参照 |
| 0.8.0-experiment | experimental-v7-joint-route-construction | 新联合构造、端点索引与目标驱动闭环 |

0.8.0精确实现：mapgen/gdscript-experiment-0.8.0+2271b5d4da0d，28运行文件。源码锁和选择时间见selection.json。新布局/随机调用/搜索计数/配置/指纹独立，不保留旧地图假装性能补丁。source commit以独立包manifest/receipt为准；交付文档或PR head不能冒充包内源码。

core_loop_policy=path_gain是预先确定的主方案；legacy是显式消融，同一实现的不同配置，不是另一算法或失败后回退。校准8例用于发现实现问题；冻结后新增40+20+20，全部保留。最末20为新预列970001–970020，0.7.0 merge亦同批重放。

旧0.2.0/0.3.x/0.4.x/0.5.x/0.6.0/0.7.0源码、包、冻结预期与失败均保持原样，不升级模块1.1.1、不合并或部署。
