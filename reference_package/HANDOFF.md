# 三仓第一轮最终交接

## 实际来源与产物

| 项目 | 精确身份 |
|---|---|
| 起始 main | `178c40164c2f7371ce1c8a56cde658e84a4f42c2` |
| 工作分支 | `feature/python-reference-package-v1`，完成 PR 后等待审查，不自动合并 |
| 包的实际代码源 commit | `1b20031c60ee0269d03c1e89eb52f0a0f0fc70bf`；完整 source.files 在包内 manifest |
| 交付路径 | `reference_package/releases/0.2.0/mapgen-python-reference-0.2.0.zip` |
| ZIP SHA-256 | `25f05861b68a99eee1e9d588eb2cab761e30c85b7cc109b0536292fcc98867f6` |
| 包/算法/实现 | `0.2.0` / `stable-v2` / `mapgen/interface-v1` |
| 运行目标 | `python-reference`；Godot/Web/桌面游戏算法均未实现 |
| 模块输入 | map-edit 1.1.0，SHA `5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723` |
| 只读主游戏核对 | main `30e36c9abe223f26e666ceaf796e3fe9cb58e10f`，17 个实际源码/文档文件身份见 [host-review.json](host-review.json) |
| 只读模块仓核对 | main `9b712fe814ef228b368c0eb9adf660e39de29e37`；没有自动升级测试模块 ZIP |

打包代码与冻结输入先提交，再由该 commit 构建 ZIP，归档/验证记录在其后的提交中加入。这使包内源身份真实且避免 ZIP 哈希/提交哈希自引用；最终 PR head 是完整交付的提交，不应与包内代码源 commit 混称。

## 协议与样例入口

- API：`mapgen.generate(request, library, config, hooks=...)`；完整契约见 [PROTOCOL.md](docs/PROTOCOL.md)。
- 原请求 v1、配置 v1、结果 v1 与 runtime-map/v2 均复用，只补齐原结果 Schema 和外层参考包 manifest。
- [成功样例](fixtures/success/)保留默认 seed 930001、原默认 request/config、模块锁、result/map/content_store/逐引用内容和来源指纹。确定性结果哈希 `b879cef87bae22354d6f11c2db73cf729ff2d3d52c05a6a8a362bbd170219ac0`，map+store 哈希 `682c82d8cd53c3803175641b50de9acf2729d5febf6ba9f59a040f2c143756b4`。
- [失败样例](fixtures/failure/)仍用 930001 和同一默认目标/模块，仅将请求能力设为 jump，真实返回 SEARCH_EXHAUSTED；map 为 null、store 为空且没有 map/content 文件。不是删目标、换 seed 或物理无解证明。

## gunman-rush 的准确使用方法

解压参考包后：

```sh
python reference.py verify --module-zip dependencies/map-edit-modules-1.1.0.zip
python reference.py replay --case all --module-zip dependencies/map-edit-modules-1.1.0.zip
```

先用 `samples/success/result.json` 的公共 map **和完整 content_store** 实现新来源 Provider，转换到主游戏现有 LevelPlan；map-gen 不导入该内部类型。字符串种子、区域/能力、内容哈希、Factory 身份及旧 Stage 来源/恢复适配由主游戏明确实现，不能伪造旧 Manifest 或用零点默认值掩盖缺失出生点。实际接线和字段差异见 [HOST_HANDOFF.md](docs/HOST_HANDOFF.md)。Python 在开发机/CI 作参考，不能当作 Web 游戏内算法。

## 检查结果与边界

[验收记录](../validation/reference-package-0.2.0/acceptance.json)：原接口 14 项、新参考契约 7 项、独立目录实际 ZIP 11 项检查通过；原单图与保护脚本及全部20 seed旧结果重放通过。12 个原算法 Python 文件逐字节保持基线，默认成功样例完整确定性结果与旧接口基线一致。

实际解压验证和重放不依赖原仓库/实验目录，拒绝缺件、伪造 readiness、失败带可用图、错误 RNG 向量和不符锁的模块 ZIP；相同源/输入在本轮构建环境重复构建 ZIP 字节一致。[完整检查](../validation/reference-package-0.2.0/release/report.json)保留每项结果。固定地图包0.1.0的v1产物及历史证据没有修改。

参考包运行没有新增 map-edit 字段阻塞。实际玩法接入仍需 M01 安全出生及到出口的证据、具体奖励关联缺口的确认、原生实体/奖励身份及领取语义、当前宿主和镜像/部分Port/封口/接缝的资格范围。已有字段或缺证据不能靠重复注册表、猜测或新布尔开关代替；具体五个奖励关联模块列在 HOST_HANDOFF。Boss 本体/战后流程、商人政策及内部 Plan/Stage 适配属于主游戏。

Godot Standard/Web/桌面的纯数据 GDScript 生成组件本轮未实现；未来要验证 RNG、binary64、稳定排序、输入指纹、计数、切片/取消以及实际导出，标准见 [GODOT_RUNTIME.md](docs/GODOT_RUNTIME.md)。不能保持旧布局/语义时建立新实现/算法版本和独立预期，不改旧结果冒充一致。地图级移动齿轮和随机布怪未实现，也未预造未使用字段。
