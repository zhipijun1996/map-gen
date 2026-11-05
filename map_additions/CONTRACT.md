# map-additions/v1 调用与宿主边界

## 安装与运行

将交付包的`addons/mapgen_additions/`完整安装到项目中，锁定9个文件及manifest中的摘要。算法核心仍由原有包提供，主游戏无需复制求解代码。addon仅继承RefCounted，不引用SceneTree、LevelPlan、玩家、钱包或Factory。Node2D预览仅是独立审图工具。

```gdscript
const ADDITIONS = preload("res://addons/mapgen_additions/job.gd")
var job = ADDITIONS.create(generation_result, explicit_config, shop_anchors)
# 宿主自行让帧；一个job只有一个非重入owner。
var advance_result = job.advance(1) # 1..4096操作；每操作16个检查点
var progress = job.progress()
# 可在两次advance之间取消；完成后cancel是无操作。
job.cancel()
if job.is_done():
    var annotations = job.result() # 深拷贝；不返回原map的可变引用
```

必须先取得`status=PASS`的、已校验的完整`mapgen/runtime-map/v2`及完整content_store，坐标已物化。当前入口检查基本结构和引用，不重复提供完整v2协议校验器；JSON必须由包内Data.parse或保持int64/binary64类型的等价解析器读取。原始JSON超int64拒绝，不截断；新组件没有另加seed选择，派生随机流使用整个源摘要再取32位种子，与原生成RNG分离。测量范围为冻结两能力/24×36请求及模块1.1.0；其他请求未完整验收。

完整配置和Schema见profiles/default.json与schemas/。没有隐含配置路径。完整请求净空取自原map.inputs.request；run/stage/actor token仅在宿主信封，不加入本组件输入。商店列表默认空，每项必须恰为：

```json
{"id":"actual-shop-id","kind":"shop","instance_id":"M12","node_id":"n0123","position_pixels":[128,256]}
```

世界位置必须在实例矩形内、节点属于同实例；调用者负责该节点代表真实商店的可达语义，不可随便绑定邻近节点。当前真实模块无此标记，包内商店样例明确为合成夹具。

## 结果与身份

输出独立sidecar，**不得将字段直接塞入additionalProperties=false的旧runtime-map/v2**，也不把附加物重新塞进原module content。宿主同时保留原map/content_store和sidecar，绑定source_map_id与source_sha256。

- `implementation`：独立`mapgen/additions-gdscript-0.1.0+<源码摘要>`；不替代生成核心身份。
- `source_sha256`：包内Data.canonical编码的`{map,content_store}`完整摘要。该编码与Python canonical JSON不同，不能混用。
- `fingerprint`：Data.canonical([source_sha256,implementation,config,按id排序的shop_anchors])的SHA256。
- 稳定牌/齿轮/决策ID基于源摘要及几何/实例上下文。缓存、恢复必须同时绑定源和组件实现/配置指纹，不能沿用旧算法或旧组件恢复身份。
- 批次推进不额外消耗随机数，不改变坐标、内容、缺口、工作计数或结果。仅metrics和profile包含非确定性计时。
- `PASS`：本次已建模的到达决策无缺口；不是全物理世界分叉识别或可玩性认证。
- `PARTIAL`：返回安全候选及完整gaps；宿主必须显式接受部分牌位覆盖，不能当作完整验收。
- `INVALID_INPUT / BUDGET_EXHAUSTED / CANCELLED`：targets为空，signs/moving_saws/gaps为空；不交出未完成候选。

`targets`包含已在保留图里出现的普通/目标奖励和Boss、显式商店。`chest`是本轮约定的奖励提示类别，不能仅据此选择某个宝箱资产或发放内容；具体奖励仍绑定原site和宿主原有规则。现有源reward_sites未进入保留图的，不凭位置补边，按实例/模块/site列在对照报告。`signs[].views`按arrival_port_id选择，不可把所有视图合并为玩家当前可走方向；不确定来向时由宿主展示来向选择/保守提示。`shared_targets`表示各出口等距可达的共有目标，不重复装到每个方向。箭头是世界x右y下、物化镜像后的作者路径切向，路线权限不反转；八方向枚举是示意，不是导航轨迹。

`position_pixels`：告示牌底部中心；非碰撞装饰，不改变原路线。floor的actor_stand_position_pixels有静态支撑候选；suspended为null，interaction_position_pixels仅为作者路径附近的候选交互点。需要主游戏确认视距、触发范围、玩家状态以及悬挂交互形式。

`moving_saws[]`沿origin→origin+travel往返，radius为像素半径，period为完整来回秒数，initial_phase为周期[0,1)。本组件预览使用三角波：t=(time/period+initial_phase)%1，position=origin+travel*(1-abs(2*t-1))。所有运动相位共享同一完整包络保护；宿主可绑定原生运动组件，但若运动范围超出包络必须重新验证。数据不规定伤害数值，复用宿主既有齿轮规则；生命周期、碰撞层、伤害节流和卸载属于宿主。新增齿轮不得替代原Port封口。原map.bounds_blocks不改写；宿主的剔除/显示范围需并入新增齿轮包络与告示牌矩形，不能仅使用原矩形裁掉边界附加物。

## 调度、数值与未验证域

搜索/后处理使用Array中的int64/binary64，不依赖Vector2精度。预览才用Vector2渲染。create同步快照与哈希，export同步深拷贝和哈希，结果提取也同步深拷贝；这些是已知原子步骤。按阶段记录advance耗时，但操作数不保证毫秒上限。当前export通常在同次advance结束，不向宿主暴露可取消的独立窗口；不能宣称中途打断一次字典拷贝。cancel只能在宿主调度重新取得控制后生效。输入到完成延迟需包含宿主等待，Web报告同时提供实际输入及浏览器往返测量。

每个job独立快照和可变状态，取消一个不影响其他job。没有共享可变派生库、外部缓存或隐式模块下载。端点、完整扫掠、作者Route/Port/奖励/终端和牌位保护是静态保守约束；动态敌人AI、运动平台的实际接驳动作、机关状态、物理跨界、镜像与整图可玩性仍需主游戏验收。未知形状/缺失Route锚点不构成安全或可达证明。
