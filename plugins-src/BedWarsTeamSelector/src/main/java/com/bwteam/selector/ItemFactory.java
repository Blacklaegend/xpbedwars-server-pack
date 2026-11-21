package com.bwteam.selector;

import com.andrei1058.bedwars.api.arena.IArena;
import com.andrei1058.bedwars.api.arena.team.ITeam;
import com.andrei1058.bedwars.api.arena.team.TeamColor;
import com.andrei1058.bedwars.api.language.Language;
import org.bukkit.ChatColor;
import org.bukkit.DyeColor;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.List;

public final class ItemFactory {

    private ItemFactory() {
    }

    public static NamespacedKey selectorKey(TeamSelectorPlugin plugin) {
        return new NamespacedKey(plugin, "selector");
    }

    public static boolean isSelector(TeamSelectorPlugin plugin, ItemStack item) {
        if (item == null || item.getType() == Material.AIR) {
            return false;
        }
        ItemMeta meta = item.getItemMeta();
        return meta != null && meta.getPersistentDataContainer().has(selectorKey(plugin), PersistentDataType.BYTE);
    }

    /**
     * The lobby item, lore shows the current selection.
     */
    public static ItemStack selectorItem(TeamSelectorPlugin plugin, Player player, IArena arena) {
        Material material = Material.matchMaterial(plugin.getConfig().getString("item.material", "NETHER_STAR"));
        if (material == null || !material.isItem()) {
            material = Material.NETHER_STAR;
        }
        ItemStack item = new ItemStack(material);
        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return item;
        }
        String current = plugin.store().get(arena.getArenaName(), player.getUniqueId());
        ITeam selected = current == null ? null : arena.getTeam(current);
        String display = selected == null
                ? Messages.color("&7未选择")
                : selected.getColor().chat() + selected.getDisplayName(Language.getPlayerLanguage(player));

        meta.setDisplayName(Messages.color(plugin.getConfig().getString("item.name", "&b选择队伍")));
        List<String> lore = new ArrayList<>();
        for (String line : plugin.getConfig().getStringList("item.lore")) {
            lore.add(Messages.color(line.replace("%team%", display)));
        }
        meta.setLore(lore);
        meta.getPersistentDataContainer().set(selectorKey(plugin), PersistentDataType.BYTE, (byte) 1);
        item.setItemMeta(meta);
        return item;
    }

    public static List<Integer> selectorSlots(TeamSelectorPlugin plugin, Player player) {
        List<Integer> slots = new ArrayList<>();
        for (int i = 0; i < player.getInventory().getSize(); i++) {
            if (isSelector(plugin, player.getInventory().getItem(i))) {
                slots.add(i);
            }
        }
        return slots;
    }

    /**
     * Keeps exactly one selector item in the inventory: updates the existing one in
     * place, deletes duplicates, and only gives a new item when none is present.
     */
    public static void giveOrUpdate(TeamSelectorPlugin plugin, Player player, IArena arena) {
        ItemStack fresh = selectorItem(plugin, player, arena);
        List<Integer> found = selectorSlots(plugin, player);
        if (!found.isEmpty()) {
            player.getInventory().setItem(found.get(0), fresh);
            for (int i = 1; i < found.size(); i++) {
                player.getInventory().setItem(found.get(i), null);
            }
            if (found.size() > 1) {
                plugin.getLogger().warning("清理重复的选队物品: " + player.getName() + " slots=" + found);
            }
            return;
        }

        int slot = plugin.getConfig().getInt("item.slot", 8);
        if (slot < 0 || slot > 8) {
            slot = 8;
        }
        // do not overwrite another plugin's waiting lobby item
        ItemStack existing = player.getInventory().getItem(slot);
        if (existing != null && existing.getType() != Material.AIR && !isSelector(plugin, existing)) {
            int free = -1;
            for (int i = 8; i >= 0; i--) {
                ItemStack item = player.getInventory().getItem(i);
                if (item == null || item.getType() == Material.AIR) {
                    free = i;
                    break;
                }
            }
            if (free >= 0) {
                slot = free;
            }
        }
        player.getInventory().setItem(slot, fresh);
    }

    public static boolean isSelectorSlot(TeamSelectorPlugin plugin, Player player) {
        int slot = plugin.getConfig().getInt("item.slot", 8);
        return slot >= 0 && slot <= 8 && isSelector(plugin, player.getInventory().getItem(slot));
    }

    /**
     * One team entry inside the GUI.
     */
    public static ItemStack teamItem(TeamSelectorPlugin plugin, Player viewer, IArena arena, ITeam team,
                                     boolean selected, boolean locked) {
        TeamColor color = team.getColor();
        DyeColor dye = color.dye();
        Material material = Material.matchMaterial(dye.name() + "_WOOL");
        if (material == null) {
            material = Material.WHITE_WOOL;
        }
        String display = team.getDisplayName(Language.getPlayerLanguage(viewer));

        ItemStack item = new ItemStack(material);
        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return item;
        }
        meta.setDisplayName(plugin.messages().format("team-item-name",
                "color", color.chat().toString(),
                "team", display));

        int max = arena.getMaxInTeam();
        int current = Math.min(max, team.getSize() + plugin.store().count(arena.getArenaName(), team.getName(), null));
        String statusKey;
        if (selected) {
            statusKey = "status-selected";
        } else if (locked) {
            statusKey = "status-locked";
        } else if (plugin.getConfig().getBoolean("block-full-team", true) && current >= max) {
            statusKey = "status-full";
        } else {
            statusKey = "status-available";
        }

        List<String> lore = new ArrayList<>();
        for (String line : plugin.messages().list("team-lore")) {
            lore.add(line.replace("%current%", String.valueOf(current))
                    .replace("%max%", String.valueOf(max))
                    .replace("%status%", plugin.messages().get(statusKey)));
        }
        meta.setLore(lore);
        item.setItemMeta(meta);
        return item;
    }

    public static ItemStack randomItem(TeamSelectorPlugin plugin) {
        Material material = Material.matchMaterial(plugin.getConfig().getString("gui.random-material", "NETHER_STAR"));
        if (material == null || !material.isItem()) {
            material = Material.NETHER_STAR;
        }
        ItemStack item = new ItemStack(material);
        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return item;
        }
        meta.setDisplayName(Messages.color(plugin.getConfig().getString("gui.random-name", "&e&l随机分队")));
        List<String> lore = new ArrayList<>();
        for (String line : plugin.getConfig().getStringList("gui.random-lore")) {
            lore.add(Messages.color(line));
        }
        meta.setLore(lore);
        item.setItemMeta(meta);
        return item;
    }

    public static String coloredName(ITeam team, Player viewer) {
        ChatColor chat = team.getColor().chat();
        return chat + team.getDisplayName(Language.getPlayerLanguage(viewer));
    }
}
