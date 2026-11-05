# 整图后处理：移动齿轮与路线告示牌 0.1.0

实现：`mapgen/additions-gdscript-0.1.0+65eb9d88fd06`。状态：`research-prototype`。独立纯数据GDScript组件，不替换0.8.0或其他生成核心；`runtime-map/v2`与模块1.1.0保持原样。已经输出真实地图的移动齿轮数据，并提供可动画、可点选告示牌的审图工具。主游戏伤害、碰撞、玩家交互和整图可玩性尚未认证。

[效果与算法选择](REPORT.md) · [同批40 seed交互对照](comparison/index.html) · [调用合同](CONTRACT.md) · [交付说明](DELIVERY.md) · [冻结选择与源码锁](../validation/map-additions-20261105/selection.json)。

输入为已成功生成、完整且已校验的`map + content_store`。输出是独立`mapgen/map-additions/v1` sidecar，保留原地图、敌人、奖励、Port封口和生成随机流。失败生成结果不能进入后处理；后处理取消/预算失败不交出部分可用附加物。

- **移动齿轮**：共享边界去重分段，优先内部接缝，其余边界独立随机抽样。默认最多8组；新增组间距至少384px，640px邻域最多2组。检查完整运动包络，再加请求玩家半尺寸和8px余量，避让已知碰撞、机关、Port、作者路线、普通/目标奖励领取区及牌位。不能定位出生/Boss精确活动范围时，保守保护整个终端房间。未知hook/危险形状排除整个实例。已有封口/齿轮进入避让和密集惩罚；局部数量硬上限仅统计**新增组**，并非把源模块的危险删到2个。
- **告示牌**：整图完成后从有向Port–Route图推导决策，以进入Port区分可用方向。只显示`chest / shop / boss`。同一区域可共享实体牌，但保留不同到达视图。排除“先退回本岔口再去另一路”造成的错误提示。Boss优先公共`graph.main_paths`的对应方向；奖励按可达图跳数分配，等距共有奖励单列。不是实际行进时间估算。
- **自动落点**：优先已有静态平台；附近找不到位置时，允许非碰撞悬挂牌，交互点位于作者路线。悬挂牌不宣称有站立地面。缺口具体列入`gaps`并返回`PARTIAL`，不能当作“所有岔路都有牌”。同一出口内部的物理分流不能由当前Port图完整识别。

真实1.1.0输入没有标准商店目标；调用者可显式传入已绑定图节点的真实商店锚点。合成测试证明商店分类/引用逻辑，没有把合成商店当作真实模块。源奖励点缺少Route节点的清单见comparison/metrics.json，未擅自补路线。

复现（Python仅用于开发装配和校验；Godot运行不启动Python）：

```sh
python -m map_additions.tools.setup --out /tmp/map-additions
# 路径必须为绝对路径；input.json是已成功生成的完整结果。
godot --headless --path /tmp/map-additions --script res://tests/run.gd -- \
  /absolute/input.json /absolute/config.json /absolute/annotations.json 1
python -m map_additions.tools.preview --out /tmp/map-additions-review
godot --path /tmp/map-additions-review
```

审图项目键1–4切换算法，滚轮缩放、拖动平移，点青色告示牌查看方向，Escape取消正在推进的后处理。图来自原冻结样本，附加物实时计算。也可直接打开comparison/index.html查看全部40seed并排对照；HTML动画是数据审阅，不代替Godot/Web实测。
