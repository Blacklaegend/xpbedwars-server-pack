# BedWars1058 修改版

本目录记录本整合包对 **BedWars1058** 的修改。

上游项目：<https://github.com/andrei1058/BedWars1058>  
上游许可证：GNU GPL v3（见本目录 `LICENSE`）

## 修改内容

| 补丁 | 说明 |
|---|---|
| `Patch1144v2.java` | 修复最终击杀相关后台空指针（上游 #1144） |
| `Patch1142.java` / `Patch1142b.java` | 修复蠹虫/铁傀儡生成相关兼容问题（上游 #1142 方向） |
| `PatchParticle.java` + `ParticleFix.java` | 修复 TNT 提示粒子在 Paper 1.21.4 的 NMS 报错 |
| `StackBuy.java` + `InventoryListener.java` | Shift+左键购买一组可堆叠物品，Shift+右键保留快捷购买 |
| `PatchArmorGate.java` | 护甲购买限制：不能购买同等级或更低等级护甲 |
| `PatchArmorReset.java` / `PatchArmorRepeat.java` | 死亡后护甲清空与重复购买处理 |
| `PatchArmorStrict.java` | 护甲判断加强 |
| `PatchHealth.java` | 进服/重生后保持 28 血上限 |
| `JarPatcher.java` | ASM 补丁基础工具 |
| `VerifyBasic.java` | 补丁后字节码校验 |

## 说明

- 这些文件是**补丁源码/工具源码**，不是编译后的 BedWars1058 jar。
- 实际发布版本基于 BedWars1058 25.5-SNAPSHOT 构建。
- 修改通过 ASM 字节码补丁和辅助类完成；如果要构建完整源码版本，需要把对应修改合并到上游同版本源码中。
- **发布修改后的 BedWars1058 jar 时，请同时公开完整的对应源码**，以符合 GPLv3 的要求。只公开补丁文件不能完全替代“对应源码”。

## 构建提示

1. 从上游获取与目标 jar 相同版本的 BedWars1058 源码。
2. 将本目录的修改合并到源码，或使用对应的 ASM 补丁工具生成 jar。
3. 保留上游版权头和 GPLv3 许可证。
4. 在发布页标注：

```text
Modified by xpbedwars-server-pack
Date: 2026-11
Based on BedWars1058 25.5-SNAPSHOT
```

## 许可证

BedWars1058 及其修改版遵循 GNU GPL v3。  
上游作者版权归 Andrei1058 及贡献者所有。
