# BWCompass

BedWars1058 指南针扩展插件源码。

## 功能

- 自动锁定最近敌人
- 主手持指南针时显示距离
- 磁石指南针持续更新方向
- Shift+右键打开快捷通讯菜单
- 快捷消息包含：敌人在这里、需要支援、速速回家等
- 与 BedWars1058 的商店护甲规则配合

## 构建

需要 Java 21。

准备两个依赖 jar：

- `paper-api-1.21.4.jar`
- `bedwars-plugin-25.5.jar`（或对应 BedWars1058 版本）

在 PowerShell 中执行：

```powershell
$paper = "paper-api.jar"
$bw = "bedwars-plugin.jar"

javac -encoding UTF-8 -cp "$paper;$bw" -d classes src\com\bwcompass\BWCompass.java
Copy-Item plugin.yml classes\plugin.yml
jar cf BWCompass-1.1.0.jar -C classes .
```

把生成的 `BWCompass-1.1.0.jar` 放入服务器的 `plugins/` 目录。

## 配置

`plugin.yml`：

```yaml
name: BWCompass
version: 1.1.0
main: com.bwcompass.BWCompass
api-version: '1.21'
author: bwteam
description: BedWars1058 compass - automatic nearest enemy tracking with action bar distance + quick team messages
depend: [BedWars1058]
```

## 许可

本插件源码随整合包以 GNU GPL v3 开源，详见仓库根目录 `LICENSE`。

BedWars1058 API 版权归 Andrei1058 及贡献者所有。
