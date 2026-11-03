# Godot Standard 纯数据候选 0.3.0

独立实现 `mapgen/gdscript-candidate-0.3.0`，算法基准 `stable-v2`，输入仍为 request/v1、config/v1、模块包1.1.0；目标输出仍为 runtime-map/v2。Python 参考0.2.0和旧交付文件不变。**这是迁移候选，不是生产就绪包。**

组件包含纯 RefCounted 协议校验、精确JSON数值、CPython MT19937、稳定排序、真实模块读取、生长/回退/预留/闭环/AIR/Boss/奖励求解、原装配门禁、独立审计及完整map/content_store导出。未加载模块包的脚本或场景。镜像不改变 Route 方向，原有机制、敌人与奖励完整保留。

seed 支持 `[-9007199254740991,9007199254740991]`。超出明确拒绝；0.2.0中的两个大整数向量属于不支持域，不算通过。整数原点额外支持±10^9。请使用 `data_json.gd.parse()` 读取算法JSON，不能先用会舍入大整数的宿主JSON读取再声称输入无损；Dictionary输入必须使用真正的int种子。宿主run/stage/actor token不进入请求。

指纹使用新实现身份和确定性 `data_json.gd.canonical()`；这个保留数值类型的Godot全精度编码**不冒充Python canonical**。跨实现比较必须分别核身份和实际布局/图/内容/计数。

原生基础检查：

```sh
godot --headless --path godot_candidate --script res://tests/foundation.gd -- /absolute/modules.zip
python godot_candidate/tools/verify_foundation.py --module-zip /absolute/modules.zip --out /tmp/mapgen-foundation-new
```

Python命令是开发时对照工具；GDScript组件不调用Python，不读取参考地图。模块ZIP显式输入，不下载最新版本。安装、创建/推进/取消/结果调用见 [HOST_API](docs/HOST_API.md)，检查分层和未验证边界见 [ACCEPTANCE](docs/ACCEPTANCE.md)。实际结果以交接报告及独立包manifest为准，不把数据生成通过当作地图可玩认证。
