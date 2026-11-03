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

[结果、确定性与性能报告](docs/RESULTS.md)。独立候选包和单独的Web测试导出位于[releases/0.3.0](releases/0.3.0/)，均附SHA。解压候选包后安装`addons/mapgen/`到项目的同名路径；配置、模块ZIP由调用者明确提供，测试样例不参与求解。

在仓库外解压验证（只需要Godot Standard，不运行Python）：

```sh
godot --headless --path /absolute/mapgen-godot-candidate-0.3.0 \
  --script res://tests/verify_bundle.gd -- \
  /absolute/mapgen-godot-candidate-0.3.0/tests/dependencies/modules.zip
```

独立包manifest记录所有文件SHA、算法/实现/输入输出版本、模块锁、seed支持域及验证证据；外部ZIP SHA同时覆盖manifest。`tests/samples`保存未修改的Python0.2.0完整成功/失败原件，仅供对照，不是生成器的地图缓存。单独Web ZIP是同一组件的真实导出测试宿主，按包内README在localhost运行，不是可玩的主游戏或部署站点。
