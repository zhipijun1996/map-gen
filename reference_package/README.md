# 版本化 Python 参考交付包

本轮从 main `178c40164c2f7371ce1c8a56cde658e84a4f42c2` 开始，分支 `feature/python-reference-package-v1`。只读核对主游戏 main `30e36c9abe223f26e666ceaf796e3fe9cb58e10f` 的实际架构及 LevelRequest/Provider/LevelPlan/Stage/LevelRuntime，路径及内容身份见 [host-review.json](host-review.json)。

[包内使用说明](docs/README.md) · [公共契约](docs/PROTOCOL.md) · [主游戏交接](docs/HOST_HANDOFF.md) · [Godot 实现与验收建议](docs/GODOT_RUNTIME.md)

[下载参考包 0.2.0](releases/0.2.0/mapgen-python-reference-0.2.0.zip) · [ZIP SHA](releases/0.2.0/mapgen-python-reference-0.2.0.zip.sha256) · [构建校验](releases/0.2.0/receipt.json)

算法 `stable-v2`、实现 `mapgen/interface-v1` 与 runtime-map/v2 语义不变。新增包版本/readiness、原结果 v1 的 JSON Schema、完整结果验证与引用解析、可重放真实成功/失败样例，以及跨实现 RNG/数值向量。旧 0.1.0 固定地图包和所有历史证据原样保留。

## 产物和证据

- [冻结成功样例](fixtures/success/provenance.json)：原样 seed 930001、默认配置及真实模块，完整确定性结果与接口基线一致。
- [冻结真实失败](fixtures/failure/provenance.json)：同 seed、同配置和原模块，jump-only 请求不能按声明路线继续生长；失败无可用地图，不是物理无解证明。
- [完整独立解压、重放、拒绝反例和二次构建记录](../validation/reference-package-0.2.0/release/report.json)。
- [参考契约测试](../validation/reference-package-0.2.0/contract-tests.log)、[原接口测试](../validation/reference-package-0.2.0/interface-tests.log)和[仓库保护检查](../validation/reference-package-0.2.0/original-checks.log)。

`runtime_target=python-reference`，readiness 明确为 reference-only；Godot/Web/桌面游戏运行时算法未实现、主游戏接入未验证、全图物理未运行。文档和 source review 不代替引擎结果，不发布网站，不自动合 main。

## 开发复现

模块 ZIP 必须明确提供，不自动获取最新。先签出 manifest.source.commit 指定的实际构建源，再使用一个新输出目录：

```sh
python reference_package/build.py \
  --module-zip /path/to/map-edit-modules-1.1.0.zip \
  --module-lock examples/library-lock.json --source-commit HEAD --out /tmp/new-reference-release

MAPGEN_REFERENCE_MODULE_ZIP=/path/to/map-edit-modules-1.1.0.zip \
  python -m unittest discover -s tests/reference -v

python tests/reference/validate_release.py \
  --archive /tmp/new-reference-release/mapgen-python-reference-0.2.0.zip \
  --module-zip /path/to/map-edit-modules-1.1.0.zip --out /tmp/new-reference-check
```

build 拒绝未提交/不匹配的输入和覆盖旧发布目录，按冻结 fixtures 构建，固定 ZIP 时间戳并生成 sidecar SHA。输入文件相同且在本轮验证的构建环境中，重复构建 ZIP 完全一致。新环境重建仍应核对压缩器/运行时差异，不能仅凭源 commit 宣称二进制哈希必然相同。

冻样脚本 freeze.py 只用于明确新版本样例，拒绝覆盖。它逐文件检查原算法基线及默认 request/config，并且成功必须匹配既有接口基线；未通过结果原样留下，不改 seed 或目标找替代。
