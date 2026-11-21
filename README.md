# xp_bedwars_server_pack

高仿布吉岛的高版本经验起床服务器整合包（开源版）。

<img src="docs/images/server-icon.png" width="96" alt="BedWars Server Logo">

> 版本：**v2.2.0**  
> 核心：Paper 1.21.4 + BedWars1058 + 233BedWars  
> 支持：Java 1.12 ~ 1.26.3、基岩版互通、Via 高低版本兼容

本仓库是本整合包的**原创代码、配置示例和文档**仓库，不包含第三方插件 jar、Paper 核心、地图文件和玩家数据。  
开服请使用 Release 中的整合包，或将本仓库配置与官方插件自行组合。

---

## 项目简介

这套整合包面向高版本经验起床服务器，保留布吉岛经典玩法的同时，加入了地雷、烟花、毒液球、幸运方块、重锤等高版本道具，并配套独立开服面板、队伍选择器、白名单、封禁、登录、语音和指南针等功能。

服务器不是固定玩法：BedWars1058 负责核心规则、商店、生成器和升级，233BedWars 负责计分板、ActionBar、开局动画和扩展玩法，面板负责开服、配置、玩家管理和插件更新。

---

## 功能与特色

### 经验起床玩法

- 4队8人 / 8队4人模式
- 适合 4~32 名玩家
- 内置 4 张 4队8人地图 + 2 张 8队4人地图
- 地雷、烟花、毒液球、幸运方块
- 重锤等高版本武器
- 魔王杯模式

### 队伍与组队

- 可视队伍选择器，开局前查看人数并选队
- `/zd` 组队指令，用法与布吉岛基本一致
- 输入 `/zd` 查看完整说明

### 开服面板

- 免 Python 独立版，解压即用
- 一键开服 / 关服
- Paper 1.21.4 核心下载
- EULA 检测与同意
- 内置控制台
- 玩家管理：BW 等级、经验、白名单、封禁/解封
- 插件更新：Geyser、Floodgate、ViaVersion、ViaBackwards
- 服务器配置：端口、MOTD、server-ip、最大人数、视距、基岩版端口、语音端口
- Java 环境检测 / 切换 / Temurin 21 下载
- 资源生成器、商店、地图管理
- 自动识别解压目录
- 单实例运行，不重复占用端口
- 关闭页面退出面板（只关面板不关服）
- 配置未保存提醒
- 内置使用说明和常见问题

### 白名单与权限

- IpacWhitelist / IpacEL 白名单
- 面板直接添加，或执行 `/wl add <玩家名>`
- LuckPerms + Vault 管理组别和权限
- BETag 提供基岩版前缀和称号

### 封禁与登录

- AdvancedBanZ 封禁系统，已接入面板
- 支持封禁、解封和处罚记录
- AuthMe 5.7.0 注册 / 登录 / 中文提示
- 账号数据保存在 `plugins/AuthMe/authme.db`

### 游戏体验

- 进服与重生后保持 28 血上限
- 指南针自动定位最近敌人并显示距离
- 快捷通讯：敌人在这里、需要支援、速速回家等
- Shift+左键一次买满一组可堆叠物品
  - 末影珍珠 16 个
  - 羊毛、箭、TNT、金苹果等 64 个
- Shift+右键保留快捷购买添加 / 移除
- 护甲购买规则：不能购买同等级或更低等级护甲
- 铁锻炉等队伍升级正常生效
- BE 玩家显示 `[BE]` 前缀
- BE 玩家 UI 支持（实验性）

### 语音与社交

- Simple Voice Chat 局部语音
- `/tell` 私聊
- 已修复全局聊天权限问题
- 中文语言已补齐 Tab、结算、快捷通讯等

---

## 仓库结构

```text
.
├─ panel/                       # 面板源码
│  ├─ ServerPanel.py            # 面板主程序
│  ├─ PanelLauncher.cs          # 根目录启动器
│  ├─ logo.png / logo.ico       # 面板图标
│  ├─ panel_assets/             # 面板静态资源
│  ├─ panel_config.example.json # 配置示例
│  └─ README.md                 # 面板说明
├─ configs/
│  ├─ BedWars1058/              # BedWars1058 配置示例
│  │  ├─ config.yml
│  │  ├─ shop.yml
│  │  ├─ generators.yml
│  │  ├─ upgrades2.yml
│  │  ├─ Languages/
│  │  └─ Addons/
│  └─ 233BedWars/               # 233BedWars 配置示例
│     ├─ config.yml
│     └─ addons/
├─ docs/
│  ├─ server-intro.md           # 服务器介绍页
│  ├─ configuration.md          # BW1058 / 233 配置说明
│  ├─ faq.md                    # 常见问题
│  └─ changelog.md              # 更新日志
├─ scripts/
│  └─ start.bat                 # 手动启动服务器
├─ server.properties.example    # 服务器配置示例
├─ LICENSE                      # GNU GPL v3
├─ NOTICE                       # 版权与来源说明
├─ THIRD_PARTY_LICENSES.md      # 第三方许可证说明
└─ README.md
```

> 本仓库刻意不包含：第三方插件 jar、Paper 核心、地图文件、玩家数据、日志、备份文件。  
> 这些内容请从各自官方发布页获取，或使用 Release 整合包。

---

## 快速开始

### 使用 Release 整合包

1. 下载 Release 中的整合包并解压（路径不要包含中文）
2. 安装 Java 21
3. 双击根目录 `启动面板.exe`
4. 面板会自动识别解压目录
5. 在面板中下载 Paper 1.21.4 核心
6. 同意 EULA
7. 点击「开服」
8. 控制台输出 `Done` 后进入游戏

详细步骤见 [docs/faq.md](docs/faq.md)。

### 从源码运行面板（开发）

面板源码只需要 Python 3.10+，无需额外第三方库：

```powershell
cd panel
python ServerPanel.py
```

默认地址：

```text
http://127.0.0.1:8765/
```

### 构建免 Python 独立面板

推荐使用 PyInstaller：

```powershell
cd panel
python -m pip install pyinstaller
pyinstaller --noconfirm --onedir --noconsole --name ServerPanel --icon logo.ico ServerPanel.py
```

构建完成后，将 `dist/ServerPanel/` 中的内容放到 `panel/` 目录即可。

---

## 配置

核心配置分为两部分：

- **BedWars1058**：玩法、商店、资源生成、队伍升级、地图
- **233BedWars**：计分板、ActionBar、开局动画、扩展玩法

详细说明见：

- [docs/configuration.md](docs/configuration.md)
- [docs/server-intro.md](docs/server-intro.md)

常用配置路径：

```text
plugins/BedWars1058/config.yml
plugins/BedWars1058/shop.yml
plugins/BedWars1058/generators.yml
plugins/BedWars1058/upgrades2.yml
plugins/BedWars1058/Arenas/
plugins/BedWars1058/Languages/messages_zh_cn.yml
plugins/233BedWars/config.yml
plugins/233BedWars/addons/
```

修改配置前建议备份整个插件目录。面板保存配置时会自动生成 `.bak-时间戳` 文件。

---

## 第三方插件与版权

本仓库**不包含**以下第三方插件 jar：

- BedWars1058
- 233BedWars
- BedWarsTeamSelector
- Geyser-Spigot / Floodgate
- AuthMe
- LuckPerms / Vault / BETag
- ViaVersion / ViaBackwards
- PlaceholderAPI / ProtocolLib
- Simple Voice Chat
- Essentials
- AdvancedBanZ
- IpacWhitelist
- OldCombatMechanics

请从各自官方发布页下载，并遵守对应许可证。第三方插件版权归各自原作者所有。

地图文件可能涉及第三方地图作者版权，本仓库不附带地图，请在获得授权后自行使用。

---

## 已知问题

- 指南针偶发抽风，后续继续修复
- BE UI 为实验性功能，建议在测试服验证
- 1.8 仅为理论兼容，实际以 Via 支持为准
- 基岩版必须使用独立端口，不能与 Java 版共用
- 面板关闭页面会退出面板，但不会关闭服务器

更多问题见 [docs/faq.md](docs/faq.md)。

---

## 贡献

欢迎提交 Issue 和 Pull Request。

提交前请确认：

1. 不包含玩家数据、日志、服务器密钥等敏感信息
2. 不包含未经授权的第三方插件 jar 或地图
3. 配置修改先在测试环境验证
4. 说明复现步骤和 Java/客户端版本

---

## 许可证

本整合包原创部分基于 **GNU GPL v3** 开源，完整协议见 [LICENSE](LICENSE)。

第三方插件、地图、资源版权归各自原作者所有，详见 [NOTICE](NOTICE) 和 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)。

本项目与 Mojang、Microsoft、PaperMC、BedWars1058、233BedWars 官方无隶属关系。

---

## 鸣谢

- 233BedWars 插件作者 **Serendipity**
- 布吉岛经验起床服务器（玩法参考）
- BedWars1058 及所有第三方插件作者
- 所有通过积分支持过本整合包的用户
- 所有提供反馈与测试的玩家

发布页：<https://www.minebbs.com/resources/10218/>
