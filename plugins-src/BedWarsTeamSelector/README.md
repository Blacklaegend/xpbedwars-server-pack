# BedWarsTeamSelector

给 BedWars1058（25.6 / impl-1031，Paper 1.21.4）用的**队伍选择器 + /zd 组队系统**。独立插件，不改 BedWars1058 本体。

## 功能

### 选队
- 玩家进入等待大厅，自动在快捷栏收到「选择队伍」物品（默认第 9 格，可配）。
- 右键物品，或输入 `/bwteam` 打开选队界面。
- 界面按地图自己的队伍生成：4 队、8 队、2 队都自动适配，不写死。
- 每格显示队伍羊毛图标、队名、`人数 x/y`、状态（可点 / 已满 / 已锁定 / 已选择）。
- 点一下即记录选择，切换队伍直接再点另一队。
- 开局倒计时最后 10 秒锁定（可配），满员禁止加入，可一键随机分队。
- 队长选队时，同房间的队伍成员一起过去（支持 `/zd` 队伍与 BedWars1058 自带 `/party`）。
- 游戏开始时由插件接管分队，按大家选的队伍落地；没选队的人自动均衡分配。

### 组队 `/zd`
| 指令 | 作用 |
| --- | --- |
| `/zd` | 查看帮助 |
| `/zd c` | 创建队伍（自己成为队长） |
| `/zd i <玩家>` | 邀请玩家加入队伍 |
| `/zd a <玩家>` | 接受队伍邀请 |
| `/zd q` | 离开当前队伍 |
| `/zd l` | 查看队伍成员和队长 |
| `/zd p <玩家>` | 转让队长 |
| `/zd r <玩家>` | 移除队员 |
| `/zd d` | 解散队伍 |

队伍是插件自己维护的（UUID 记录），队长选队会整队跟随；同时兼容 BedWars1058 自带 `/party` 创建的队伍（选队器会优先认 `/zd` 队伍）。队伍数据存在内存里，服务器重启后会清空。

## 安装

1. 把 `BedWarsTeamSelector.jar` 丢进 `plugins/`。
2. 重启服务器。第一次启动会生成 `plugins/BedWarsTeamSelector/config.yml` 与 `messages.yml`。
3. 确认 `plugins/BedWars1058/config.yml` 里：
   ```yaml
   experimental-team-assigner: true
   ```
   25.6 默认就是 `true`。如果被改成 `false`，插件启动时会打印警告，组队跟随会失效（单人选择仍可用）。

## 命令与权限

| 命令 | 说明 |
| --- | --- |
| `/bwteam` | 打开队伍选择界面 |
| `/bwteam reload` | 重载 config.yml 与 messages.yml |
| `/zd ...` | 组队指令（见上表） |

| 权限 | 默认 | 说明 |
| --- | --- | --- |
| `bwteam.use` | 所有人 | 使用选队界面 |
| `bwteam.party` | 所有人 | 使用 `/zd` |
| `bwteam.admin` | OP | 重载配置 |

## 配置要点（config.yml）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `item.slot` | `8` | 选队物品放在快捷栏第几格（0-8）；该格被别的插件占用时会自动找空位 |
| `item.disable-in-solo` | `true` | 每队 1 人的模式不发物品 |
| `lock-seconds` | `10` | 开局倒计时剩余多少秒锁定；`<=0` 不锁 |
| `block-full-team` | `true` | 满员禁止加入 |
| `party-leader-only` | `true` | 只有队长能选队 |
| `party.max-size` | `8` | `/zd` 队伍人数上限，`0` 不限制 |
| `party.invite-expire-seconds` | `60` | 邀请有效期 |
| `party.disband-on-owner-leave` | `true` | 队长 `/zd q` 直接解散队伍；`false` 则提示先转让或解散 |
| `gui.team-slot-start` | `10` | 队伍格子起始槽位 |
| `gui.random-slot` | `-1` | 随机分队按钮槽位，`-1` 自动放在最后一行 |

文案全部在 `messages.yml`，颜色用 `&`。

## 实现说明（给后续维护）

- 选队结果存在内存里（`SelectionStore`），按 `arenaName -> uuid -> teamName`。
- 进房时把该地图的 `ITeamAssigner` 换成 `PreferenceAssigner`，开局 `GameStartingTask` 调用它：
  先按队伍分组，再按「有人选的队伍」落地，剩下的人按空位最多的队伍均衡。
- 触发 `TeamAssignEvent` 前会先发事件，别的插件仍可取消。
- 万一服主关了 `experimental-team-assigner`，退回 `TeamAssignEvent` 兜底：单个玩家选择仍生效，组队跟随失效。
- `/zd` 队伍由 `PartyManager` 维护；选队分组时优先用 `/zd` 队伍，其次回退到 BedWars1058 的 Party。
- 离开房间 / 退出 / 地图重启都会清理选择记录；玩家退出时自动退出队伍（队长退出则解散）。

## 构建

本机无外网时用 `build.ps1`（javac + 本地 `.m2` 里的 `bedwars-api-25.6`、`paper-api-1.20.1`）：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
# 产物: build\BedWarsTeamSelector.jar
```

有网环境可以直接 `mvn package`（`pom.xml` 已配好 PaperMC 与 andrei1058 仓库）。
