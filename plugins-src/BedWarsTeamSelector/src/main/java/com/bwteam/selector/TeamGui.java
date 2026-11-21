package com.bwteam.selector;

import com.andrei1058.bedwars.api.arena.IArena;
import com.andrei1058.bedwars.api.arena.team.ITeam;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TeamGui implements InventoryHolder {

    private final TeamSelectorPlugin plugin;
    private final Player player;
    private final IArena arena;
    private final Inventory inventory;
    private final Map<Integer, String> teamSlots = new LinkedHashMap<>();
    private final int randomSlot;

    public TeamGui(TeamSelectorPlugin plugin, Player player, IArena arena) {
        this.plugin = plugin;
        this.player = player;
        this.arena = arena;

        List<ITeam> teams = arena.getTeams();
        int start = plugin.getConfig().getInt("gui.team-slot-start", 10);
        int last = start + teams.size() - 1;
        int rows = Math.max(3, Math.min(6, last / 9 + 2));
        int size = rows * 9;

        int configuredRandom = plugin.getConfig().getInt("gui.random-slot", -1);
        this.randomSlot = configuredRandom >= 0 ? Math.min(configuredRandom, size - 1) : size - 5;

        this.inventory = Bukkit.createInventory(this, size,
                Messages.color(plugin.getConfig().getString("gui.title", "&8队伍选择")));

        for (int i = 0; i < teams.size(); i++) {
            int slot = start + i;
            if (slot >= size) {
                break;
            }
            if (slot == randomSlot) {
                slot++;
            }
            if (slot >= size) {
                break;
            }
            teamSlots.put(slot, teams.get(i).getName());
        }
        refresh();
    }

    public void open() {
        player.openInventory(inventory);
    }

    public void refresh() {
        String selected = plugin.store().get(arena.getArenaName(), player.getUniqueId());
        boolean locked = plugin.lockSeconds() > 0
                && arena.getStartingTask() != null
                && arena.getStartingTask().getCountdown() <= plugin.lockSeconds();
        for (Map.Entry<Integer, String> entry : teamSlots.entrySet()) {
            ITeam team = arena.getTeam(entry.getValue());
            if (team == null) {
                continue;
            }
            boolean isSelected = selected != null && selected.equalsIgnoreCase(team.getName());
            inventory.setItem(entry.getKey(), ItemFactory.teamItem(plugin, player, arena, team, isSelected, locked));
        }
        if (randomSlot >= 0 && randomSlot < inventory.getSize()) {
            inventory.setItem(randomSlot, ItemFactory.randomItem(plugin));
        }
    }

    public Map<Integer, String> teamSlots() {
        return teamSlots;
    }

    public int randomSlot() {
        return randomSlot;
    }

    public IArena arena() {
        return arena;
    }

    public Player player() {
        return player;
    }

    @Override
    public Inventory getInventory() {
        return inventory;
    }
}
