# 地图级附加物与算法对照交接

源分支：experiment/signage-postprocess，依赖PR #12 experiment/joint-route-construction；不自动合入或部署。

- 组件实际源码commit：`77c4bb1093ca7f19c3c53c5fe484576302d77244`。
- 产物commit：`e43c01adfba9d8521e19d6c377f3b61b39b0629b`。
- 实现：`mapgen/additions-gdscript-0.1.0+65eb9d88fd06`，9个运行文件。
- [不可变ZIP下载](https://raw.githubusercontent.com/zhipijun1996/map-gen/e43c01adfba9d8521e19d6c377f3b61b39b0629b/runtime_packages/experiments/map-additions-0.1.0/mapgen-map-additions-candidate-0.1.0.zip)。
- ZIP SHA256：`24bd78a776b44688de4442d784721a84b5025c400c8c0659d72209507edb2970`。
- manifest SHA256：`54048701c3e356c736c3ad51b195a97ef7becd35e86923f6c417e1fbc6dce200`。
- runtime_target：`godot-standard-pure-gdscript`；readiness：`research-prototype`。
- 输入继续为完整runtime-map/v2＋content_store，测试模块1.1.0 SHA256 `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723`。

本轮完成：真实地图上的稀疏移动齿轮布置、完整扫掠保护、按来向的宝箱/商店/Boss路线牌及自动地面/悬挂落点；独立可取消job、版本化sidecar和调用合同；同40seed四候选地图比较；真实Godot/Web动画、点选与可信DOM取消；仓库外独立解压校验通过。

[调用合同](CONTRACT.md)、[完整效果及性能报告](REPORT.md)、[交互对照](comparison/index.html)、[包与独立验证日志](../runtime_packages/experiments/map-additions-0.1.0)、[全部证据](../validation/map-additions-20261105)。包内verify_bundle逐项文件摘要、9文件锁、两张真实地图＋商店合成夹具重放、43项合同均通过。旧13个交付ZIP摘要及20seed历史地图/原拒绝保持原样，原生成核心未修改。

127张成功基图都生成了8组候选移动齿轮；新增组优先共享边界，非全边界铺满。告示牌4381/5376个已建模到达视图有候选位置，所有结果PARTIAL，完整995个缺口保留。原33个生成失败也保留，不因后处理重新抽seed。没有将放置缺口或不可用输入改报为完整成功。

总体判断：v5/0.6.0是最近四配置中更稳的结构基线；v7/0.8.0具有更好的源模块多样性和严格归并＋多模块折返风格，但最短Boss路线更短、核心流程覆盖下降。继续保留v7视觉候选，不能用移动齿轮掩盖这类图结构差距。本轮没有切正式0.4.1或修改旧预期。

主游戏接入需安装9文件锁，按CONTRACT创建/推进附加物job并显式处理PARTIAL，主线程绑定牌和齿轮节点。原求解/地图转换合同不重写，旧runtime-map/v2不塞新增字段；新组件指纹、源摘要与恢复身份独立绑定。组件只输出数据，实际碰撞、伤害、牌面/交互、资产与生命周期由主游戏执行，当前均未作整图物理认证。

map-edit暂不强制升级：优先核对comparison/metrics.json中441条实例级奖励点缺失Route节点记录（模块源/site/seed逐项列出）；若这些奖励应参与导航，需明确其真实可领取Route绑定，不能由本组件补假边。真实商店尚无标准目的地，可由宿主先提供严格绑定图节点的锚点；需作者支持时再约定必要语义。牌位反复失败的模块可补**可选**安全交互点，同出口内部物理分流可补实际决策语义；不要求一次性增加大量未使用字段。

未完成：主游戏实际接入与可玩性、伤害/跨界难度、所有物理分流和全部牌位覆盖、不同动作/净空/设备、非线程Web。候选不标生产就绪；没有改gunman-rush/map-edit，没有升级1.1.1、随机布怪、部署或自动合并。后续算法实验与主游戏验收另行记录，旧结果不改写。
