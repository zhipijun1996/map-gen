# 0.8.0：真实路线联合构造实验

算法`experimental-v7-joint-route-construction`，实现`mapgen/gdscript-experiment-0.8.0+2271b5d4da0d`。基线PR #11 head 4aaa1fdf09c639b64228347e4b20760ce0d06668；旧0.7.0和全部历史版本原样保留。本轮不替换默认或正式游戏锁。

已执行的三个优化项：

1. 将分叉、真实奖励Route、未来汇合房、普通主线绕行和Boss落点联合构造，先处理稀缺归并结构，不等随机骨架完成再寻找匹配。
2. 从真实模块能力/镜像/封口配置推导534条有向单段位移签名，用端点精确查询和中间相遇匹配1–2模块连接段；没有虚构连接模块或补反向Route。
3. 闭环只接受实际提高START→Boss核心路线数量的候选；奖励支路不计入这三条核心路线。保留legacy策略作8例校准消融，非失败回退。

仍为纯数据GDScript，模块1.1.0、runtime-map/v2、32/6/3、90秒/500000、128终端状态、8修复、128生长回退/深度3和原净空/seed不变。目标风格严格为一条forward_merge＋五条multi_return，没有单房回退。比较同风格0.7.0而非以降低目标换通过。

[效果报告](REPORT.md)、[版本登记](VERSIONS.md)、[优化项与边界](OPTIMIZATIONS.md)、[地图和全部模块频率对照](comparison/index.html)、[调用合同](HANDOFF.md)。既统计目标成功/耗时，也统计Boss路线长度与模块在有向图上能否访问后抵达Boss，避免把快速局部达标误当整图质量提升。

开发复现：

```sh
python -m route_construction.tools.setup --out /tmp/mapgen-joint-route
python -m route_construction.tools.run --project /tmp/mapgen-joint-route \
  --out /tmp/mapgen-cases --godot /absolute/godot --controller --seeds 930001,930007
```

所有实际请求、配置、成功/失败及源码快照在validation/joint-route-construction-20261105。单独包位于runtime_packages/experiments/0.8.0-experiment，仓库外可运行verify_bundle及CLI，来源commit与SHA见receipt。样例不是运行时地图查询库。

状态research-prototype。静态声明路径及奖励空间检查不等于完整物理或动作认证；正式主游戏未运行。没有修改map-edit/主游戏、升级模块1.1.1、新增随机危险或布怪，也没有自动合并/部署。
