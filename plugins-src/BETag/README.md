# BETag

为基岩版（Floodgate）玩家显示彩色 `[BE]` 前缀的 BedWars1058 扩展插件。

## 功能

- 读取 Floodgate 玩家标识
- 通过 LuckPerms 设置前缀
- 由 BedWars1058 的 `{vPrefix}` 在 Tab 中显示
- 前缀显示在队伍之后、玩家名之前
- 不影响 Java 版玩家

## 构建

需要 Java 21，以及以下依赖：

- `paper-api-1.21.4.jar`
- `floodgate-spigot.jar`
- `LuckPerms.jar`

```powershell
javac -encoding UTF-8 -cp "paper-api.jar;floodgate.jar;luckperms.jar" -d classes src\com\betag\BETag.java
Copy-Item resources\plugin.yml classes\plugin.yml
jar cf BETag-1.0.0.jar -C classes .
```

把 `BETag-1.0.0.jar` 放入服务器 `plugins/` 目录。

## 配置

相关配置：

- `plugins/BedWars1058/config.yml` 中的 Tab / `{vPrefix}`
- `plugins/233BedWars/addons/scoreboard.yml`
- LuckPerms 前缀组

## 许可

本插件源码随整合包以 GNU GPL v3 开源，详见仓库根目录 `LICENSE`。
