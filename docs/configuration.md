# BedWars1058 与 233BedWars 配置说明

服务器由 **BedWars1058 + 233BedWars** 双核心驱动，玩法、商店、地图、计分板、ActionBar、开局动画等都可以按需调整。

## 一、BedWars1058：玩法核心

负责经验起床的基础规则、商店、资源生成、队伍升级和地图。

| 配置文件 | 作用 |
|---|---|
| `plugins/BedWars1058/config.yml` | 大厅、NPC、计分板、加入界面、语言、游戏基础设置 |
| `plugins/BedWars1058/shop.yml` | 商店分类、商品、价格、购买数量 |
| `plugins/BedWars1058/generators.yml` | 铁、金、钻石、绿宝石生成速度和上限 |
| `plugins/BedWars1058/upgrades2.yml` | 队伍升级内容与价格 |
| `plugins/BedWars1058/Arenas/*.yml` | 地图出生点、队伍、资源点、NPC 等 |
| `plugins/BedWars1058/Languages/messages_zh_cn.yml` | 中文语言与提示文本 |
| `plugins/BedWars1058/Addons/Compass/config.yml` | 指南针相关配置 |
| `plugins/BedWars1058/Addons/TeamSelector/config.yml` | 队伍选择器配置 |

面板中可以直接操作：

- 首页修改服务器端口、MOTD、server-ip、最大人数、视距
- 资源生成器修改铁/金/钻石/绿宝石速度
- 商店编辑修改商品和价格
- 地图管理修改地图基础信息
- 插件配置修改 BedWars1058 常用项
- 文本编辑修改 `shop.yml`、`upgrades2.yml` 等原始配置

保存时面板会自动生成 `.bak-时间戳` 备份。

## 二、233BedWars：HUD 与扩展

负责 BedWars1058 之外的界面和扩展功能，例如计分板、ActionBar、开局动画、快捷指令、全局事件和经验模式。

| 配置文件 | 作用 |
|---|---|
| `plugins/233BedWars/config.yml` | 233 总开关与基础设置 |
| `addons/scoreboard.yml` | 计分板显示内容 |
| `addons/actionBar.yml` | 动作栏显示 |
| `addons/gameStartAnimation.yml` | 开局动画 |
| `addons/generatorEditor.yml` | 资源生成器编辑 |
| `addons/shopItemAddon.yml` | 商店物品扩展 |
| `addons/balancedAdjustments.yml` | 平衡性调整 |
| `addons/combatDetails.yml` | 战斗信息显示 |
| `addons/dalaoWarning.yml` | 大佬提示 |
| `addons/extraPlaceHolder.yml` | 额外 Placeholder 变量 |
| `addons/fastCommands.yml` | 快捷指令 |
| `addons/globalEvents.yml` | 全局事件 |
| `addons/xpResMode.yml` | 经验模式相关 |
| `addons/teamNameThemes.yml` | 队伍名称主题 |

233 的 `addons` 建议用文本编辑器修改，改之前先备份对应文件。

## 三、配置建议

- BedWars1058 负责“玩法”，233BedWars 负责“显示和扩展”，两边职责尽量分开
- 计分板、ActionBar 不要同时由两个插件重复接管，避免重叠显示
- 修改商店、生成器、升级后，执行 `/bw reload` 或重启服务器
- 修改 233 的配置后，按 233 的指令重载，或直接重启服务器
- 每次大改前备份整个 `plugins/BedWars1058` 和 `plugins/233BedWars`
- 地图、NPC、计分板配置建议先在小号/测试地图验证，再应用到正式服

## 四、仓库中的示例配置

本仓库的 `configs/` 目录只提供配置示例：

```text
configs/BedWars1058/
configs/233BedWars/
```

使用时把里面的文件复制到服务器对应的 `plugins/BedWars1058` 和 `plugins/233BedWars` 目录。

`config.yml` 中的服务器名、端口、NPC、地址等字段可能与本机环境不同，请按实际情况修改。
