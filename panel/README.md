# BedWars 服务器面板

版本：**v2.2.0**
作者：**黑色的传说**
开源协议：**GNU GPL v3（GPL-3.0）**
版权：Copyright (C) 2024-2026 黑色的传说
项目主页：https://www.minebbs.com/resources/10218/

## 启动
双击 `启动面板.exe`（或 `panel\ServerPanel.exe`），会自动打开浏览器：
http://127.0.0.1:8765/

本版本为免 Python 独立版，不需要安装 Python，双击即用。

## 功能

### 状态 / 控制
- 运行状态、PID、端口、EULA、server.jar、内存
- 一键开服 / 关服（优雅 stop，超时强杀）
- 首页「⬇ 下载核心」按钮（缺少 server.jar 时会有提示）
- 首页右侧「服务器基本配置」：Java 端口、MOTD、服务器地址（{serverIp}）、最大玩家数、视距、基岩版端口、语音端口
- 首页右侧「Java 环境」：检测当前版本/路径、切换候选 Java；「⬇ 下载 Java」按钮在首页顶部「⬇ 下载核心」旁边
- 首页「🖥 打开原版控制台」：用 start.bat 在新窗口启动服务器，可使用原版控制台（面板将无法捕获其输出）
- 首页「最近日志 / 控制台」：可直接输入服务器指令，或点「打开控制台」

### 插件更新（Geyser / Floodgate / Via 系列）
- **必须先点「检查更新」**，确认有新版本后「更新选中插件」按钮才会启用
- 显示 当前版本 → 最新版本，无更新的插件不可勾选
- Geyser / Floodgate 来自 GeyserMC 官方 API（Modrinth 上 Floodgate 只有 NeoForge/Fabric，没有 Spigot 版）
- ViaVersion / ViaBackwards 来自 Modrinth
- 下载失败会自动重试 3 次；更新前需关服，旧 jar 备份到 `plugins/_disabled/plugin-updates/`
- 更新后需要重启服务器

### 使用说明
- 左侧菜单最后一项「📖 使用说明」：开服流程、控制台、配置修改、插件更新、常见问题

### 首页
- 顶部标题栏中间「💬 一言」随机语句，可选中复制，双击换一句

### 玩家管理
- 玩家列表：合并 usercache、BedWars 统计、白名单、封禁数据
- **BW 等级**：读取 `plugins/BedWars1058/Cache/shop.db` 的 `player_levels`（等级/经验/升级所需）
- **白名单**：读取和操作 IpacWhitelist（IpacEL），显示是否已加白
- **封禁**：读取和操作 AdvancedBanZ，封禁/解封后自动 reload 插件
- 白名单/封禁操作需要面板启动的服务器

### 控制台
- 实时查看服务器输出（GBK 已正确解码，中文不乱码）
- 日志按级别着色：ERROR 红色、WARN 黄色、INFO 绿色、面板指令蓝色
- **可以直接输入服务器指令**：`list`、`bw reload`、`authme reload`、`ocm reload` 等
- 只有用面板启动的服务器可以输入指令

### 下载核心（在「面板设置」页）
- 从 PaperMC 官方 API 下载
- Paper 版本 / 构建号已锁定（防止乱改下载失败）
- 自动命名 `server.jar`，旧核心自动备份
- 首页「⬇ 下载核心」按钮会跳转到面板设置里的下载卡片

### 插件配置（表单）
- **AuthMe**：登录/注册超时、未登录限制、会话、正版免密、语言、验证码、封 IP
- **OldCombatMechanics**：攻击速度、攻击频率、击退、暴击、回血、附魔金苹果、模式权限
- **BedWars1058**：全服聊天、公屏喊话冷却、重连时间、侧边栏
- **Geyser**：基岩版端口、验证方式、MOTD、服务器名
- **server.properties**：Java 端口、MOTD、最大玩家数、视距、正版验证
- **Simple Voice Chat**：语音端口、最大语音距离、绑定地址
- 保存自动生成 `.bak-时间戳` 备份

### Java 环境
- 自动检测当前 Java 路径和版本
- 列出本机所有 Java 候选
- 一键下载 Temurin 21 JDK（约 190MB）并自动切换

### 其他
- 资源生成器表单、商店 UI（中文/新增物品）、地图按分组管理
- 首页最近日志
- 所有保存自动备份

## 注意
- 面板只监听 127.0.0.1
- 8765 被占用会自动尝试 8766、8767...
- 改端口/验证方式后需要重启服务器
- 改插件配置后按对应插件的 reload 指令或重启

### Logo / 图标
- 面板顶部 logo、浏览器 favicon：`panel_assets/logo.png`
- 面板 EXE 图标：`ServerPanel.exe`（已嵌入 `logo.ico`）
- 服务器列表图标：服务器根目录 `server-icon.png`（64×64，重启服务器生效）
