# map-gen 工作约定

- 地图生成、验证、Seed 评估和可视化在本仓库工作。真实 Module 来源是 <https://github.com/zhipijun1996/map-edit>；当前正迁移新格式，接入时先读取其最新契约和仓库说明。
- 基础模型见 `docs/MAP_FOUNDATION.md`，算法和规模建议见 `docs/MAP_GENERATION_GUIDE.md`。Module 占用为整数 Block 矩形；Port 位于选定边界 Block 的外侧边中心，不要求位于 Module 边中点。
- `prototype/` 的 52 模板库是未做物理认证的测试夹具，不是 map-edit 的正式 Module 格式。`experiments/seed-study/source/` 是原实验的冻结源码，保留源文件哈希。
- 保留全部成功、失败、固定 Seed、配置和选择规则。旧批次结果原样保存，新实验另建版本目录；不得筛掉失败后报告成功率。
- 初始实际图必须区分实例和 Port，包含全部有效 Route；未声明的 Route 不得自动补齐。镜像不转置 Route；单向接口按初始权限建图；未用 Port 需要合法封口。
- 几何/静态图通过不等于 Godot 动作、接缝、镜像或封口认证。未认证、UNKNOWN 和迁移中的 Module 不宣称可正式拼装。
- 修改后运行 `python prototype/verify.py` 和 `python tools/verify_progress.py`。涉及生成行为时再运行 `python tools/verify_progress.py --replay`，核对全部 20 个固定 Seed 的地图或拒绝结果。
- 当前已知 4 个 Seed 因奖励可达/回程问题被拒绝；验证脚本接受这些已记录的失败，不表示生产生成器已经无失败。修复时另建实验，保留本次原件。
