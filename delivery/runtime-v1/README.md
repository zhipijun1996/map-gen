# Godot 0.1.0 下载与安装

本目录的小型 addon ZIP 是纯 GDScript 运行核心和配置；保持主游戏自己的 project.godot、Player 和服务。完整资源在开发/构建阶段通过仓库 tools/runtime/install.py 按固定 SHA 安装，游戏运行时无 Python/网络依赖。

```sh
python3 tools/runtime/install.py --target godot
Godot_v4.7.2-stable_linux.x86_64 --headless --path godot --editor --import
Godot_v4.7.2-stable_linux.x86_64 --path godot
```

完整独立离线项目 ZIP 可用 tools/runtime/build.py 重建，交付工作区位于 dist/mapgen-godot-0.1.0-offline.zip；SHA256.json 同时记录完整离线包与小包。

主游戏调用与边界见 ../../docs/GODOT_RUNTIME.md；录屏在 ../../reports/runtime-v1/continuous-play-final.mp4。GitHub Release 附件上传端点在本次交付返回 401，故小包和录屏使用固定提交的仓库原始下载链接，而非空的发行附件。

此为接入候选：24 张随机地图通过生成与装配，小图连续路径通过；随机大图整图物理、严格冷帧预算、最新主游戏宿主路线复验和 Web 导出尚未完成。
