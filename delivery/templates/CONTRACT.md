# 运行时地图契约 v1

版本：`mapgen/runtime-map/v1`，交付版本 `0.1.0`。未知 schema 必须明确拒绝；以后不兼容变更升级 schema，旧包不覆盖。

## 坐标、变换与实例化

- 1 Block = 128 像素，X 向右、Y 向下。`origin_blocks` 是模块占用矩形左上角；`size_blocks` 是占用尺寸。位置和尺寸均为整数 Block，位置允许负数。
- 所有 `content_ref` 内容、Port、作者路径和封口矩形均处于**所属模块占用矩形左上角为零点的像素坐标**。模块放置后 `world_pixel = origin_blocks * 128 + local_pixel`。第一版地图根节点放在世界原点，不缩放、不旋转。
- `transform.mirror_x` 仅记录该实例来自镜像选择；`content_is_materialized` 恒为 true。内容、Port、Route 路径、方向机制和封口均已变换，消费者不得再次镜像。镜像不交换 Route 的 from/to，不修改 Port ID 和对象 ID。
- `content.source_affine`、原目录中的 `sceneOriginOffsetPixels`、`source_bounds` 等是来源信息，**不得再应用到已物化内容**。Route 的 `source_validation` 和 `capability_requirements` 保留原契约/证据，其中来源坐标也不作为当前场景几何使用。
- 使用 `content_ref` 生成该实例的唯一一份地形、碰撞、机关、敌人和奖励。原 `source_scene_ref` / `source_compiled_ref` 是行为复用和追溯入口，不能与物化内容重复实例化。

原场景加载器在 `_ready()` 中读取原 `compiled-content.json`、核验原哈希并构建节点。给已经 ready 的原场景更换 `content` 变量，不能替换先前生成的碰撞和机关。主游戏应在独立适配目录提供接受物化数据的构建入口，在创建节点前供入 `content_ref`，复用原生运行时机制。保持原模块包不变，物化数据按交付 manifest 校验，不修改原模块哈希来冒充认证。

不得用只翻转美术或对父节点施加负 scale 的方式替代完整数据装配。必须支持内容中的单向平台、荆棘偏移、弹丸方向、移动平台轨迹、椭圆 `ellipse_x_sign`、配对机关、敌人和奖励；不支持的内容要报告实例/模块/字段，不能忽略。

## 地图字段

| 字段 | 语义 |
|---|---|
| `map_id` / `seed` / `generator` | 固定地图身份、seed、生成提交、配置和原结构签名 |
| `module_package` | 原模块包版本、SHA-256 和包内根目录 |
| `instances[].id` | 地图内稳定实例 ID，如 M01；不是数组下标 |
| `module_id` / `content_version` | catalog 中的真实稳定模块 ID 和精确内容版本，无 T:/Q:/START/BOSS 内部模块别名 |
| `role` | start、boss、target_reward、traversal；是生成职责，不改变模块原生内容 |
| `content_ref` | 相对交付根目录的完整编译 JSON；保留 `pcg/compiled-module-content/v1` schema |
| `ports` | 全部物理 Port 的真实 ID、变换后 face、surface、初始 permission、`local_position_pixels` |
| `connected_port_ids` | 实际接入的子集；其余 Port 必须各有一份 seal |
| `seals` | `gear-seal/1`，局部像素 `rect_pixels=[x,y,w,h]`，128px 开口、32px 向内厚度，物理尚未认证 |
| `routes` | 本配置保留的显式有向 Route；from_port/to_port 均为真实 Port ID，不能自动补逆向 |
| `required_services` | 模块需要的宿主服务；具体声明及宿主条件可按模块 ID 查原 catalog |
| `connections` | a/b 为 `{instance_id,port_id}`，绝对像素接缝位置和 surface；a/b 只是端点排序，不表示移动方向 |
| `anchors` | 起点出发 Port、Boss 到达 Port、六个目标奖励实例及尚未完成的玩法绑定 |
| `graph` | 由实际 Route 和初始 Port 权限构成的静态图，含三条参考主路 |

Port permission 取 `INPUT/OUTPUT/INOUT`；连接时分别判断出发方 out 与到达方 in 权限。face 取 `LEFT/RIGHT/TOP/BOTTOM`。surface 必须一致，边界必须精确重合。Port ID 在镜像后保持身份，ID 为 L 的接口镜像后可以朝右，不能从 ID 猜 face。

`seals` 是额外的实体齿轮封口组件，不仅是红色调试图形，也不是删除一个节点。消费其最终矩形与朝向，不再镜像；它必须实际阻挡玩家。碰撞、伤害及接缝容差在宿主里验证，未验证的伤害数值不由交付包杜撰。

## 怪物、奖励与稳定身份

怪物种类、位置、初始配置和奖励点、金额均来自所选模块，完整保留于 content。不能重新抽怪、删宝箱、替换机关相关敌人或把普通房奖励抵扣六个目标奖励。奖励 ID 在本实例内有效。

主游戏将对象身份限定为 `run_id / map_id / instance_id / local_object_id`。同一模块出现多次，其机关、敌人伤害注册和领取事务必须独立；重载同一次游玩时保持身份和已领取状态。按原生服务绑定接口生成 transaction/actor key，不允许在两个实例中复用同一奖励事务 ID。

全图共享主游戏创建的一名玩家及 policy、lifetime、wallet；需要时再注入 meta、region_state 等声明的服务。不在模块切换时重置玩家或补充资源。能力字段使用模块原生名 `shot_recoil`，不输出生成器内部的 `recoil` 简写。最低能力、路线资源接续和调参档位仍以原 scoped 声明及宿主验证为准。

## 图、锚点及未验证项

`graph.nodes[].id` 为不透明引用，不解析字符串。节点 kind 为 start、boss、port_arrive、port_depart 或 reward，端点通过结构化实例/Port 字段关联。reward 节点保留原 Route ID、奖励 ID 及 target 标记；`graph.edges` 和 `main_paths` 使用节点 ID。实际图只帮助核对生成契约，不替代 Godot 碰撞、动作或战斗。

第一张图起点为 M01 的真实 `exit`，Boss 到达口为 M40 的真实 `entry`；后者已镜像为朝右。生成器内部的 R/L 别名已还原，不得再转换一次。

`player_spawn.position_pixels=null`，状态为 UNRESOLVED。起点的未用 entry 已封口；不能使用源编译数据里的 entry_port 直接生玩家。宿主需要找到并验证实际落点及到起点出发口的路径，把结果记录在主仓库适配配置，不改写原生成数据。

Boss arena 只提供战场与入口标记，不包含 Boss 本体或已验证战斗。Boss 的未用 exit 也已封口；胜利事件、结算/传送或战后出口由宿主明确实现。若需要开封口作为战后动态行为，必须显式记录该玩法方案并实测，不能把初始封闭口写成生成阶段的开放连接。

未知项集中在 `reference/validation.json` 和 `physical-notes.json`。数据/静态验证为 PASS，`whole_map_physics` 与 `playable_in_host` 为 NOT_RUN。任何首次装配不兼容都应记录具体实例、原始模块 ID、Port/机制和复现步骤，不降低目标或伪造 Route。

## 文件校验和宿主接入顺序

manifest 的 `files` 为除 manifest 自身外的完整文件清单与 SHA-256；ZIP 自身哈希在外层 `.sha256`。在执行或导入包内脚本之前校验来源 ZIP；解压后、产生 Godot 导入缓存前运行 `verify_delivery.py`。该脚本检查完整清单，添加缓存后的目录不再是原始交付目录。

原模块包完整保留，宿主游戏的外部依赖未打包。使用原 runtime 锁逐项检查已有资源；发现不兼容时记录差异，不覆盖主游戏 project.godot、玩家、调参和全局服务。先完成固定地图的单图端到端验收，再扩展其他 seed；本轮不需要移植生成算法。
