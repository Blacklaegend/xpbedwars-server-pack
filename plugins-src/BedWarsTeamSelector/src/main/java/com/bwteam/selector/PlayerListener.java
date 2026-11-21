package com.bwteam.selector;

import com.andrei1058.bedwars.api.arena.IArena;
import com.andrei1058.bedwars.api.arena.team.ITeam;
import com.andrei1058.bedwars.api.events.gameplay.TeamAssignEvent;
import com.andrei1058.bedwars.api.events.player.PlayerJoinArenaEvent;
import com.andrei1058.bedwars.api.events.player.PlayerLeaveArenaEvent;
import com.andrei1058.bedwars.api.events.server.ArenaRestartEvent;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;

import java.util.List;
import java.util.UUID;

public final class PlayerListener implements Listener {

    private final TeamSelectorPlugin plugin;
    private final SelectionService service;

    public PlayerListener(TeamSelectorPlugin plugin) {
        this.plugin = plugin;
        this.service = new SelectionService(plugin);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoinArena(PlayerJoinArenaEvent event) {
        IArena arena = event.getArena();
        if (arena == null) {
            return;
        }
        arena.setTeamAssigner(plugin.assigner());

        Player player = event.getPlayer();
        if (arena.isSpectator(player)) {
            return;
        }
        if (!plugin.getConfig().getBoolean("item.enabled", true)) {
            return;
        }
        if (plugin.getConfig().getBoolean("item.disable-in-solo", true) && arena.getMaxInTeam() <= 1) {
            return;
        }
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (player.isOnline() && arena.isPlayer(player) && !arena.isSpectator(player)) {
                ItemFactory.giveOrUpdate(plugin, player, arena);
            }
        }, 10L);
    }

    @EventHandler
    public void onLeaveArena(PlayerLeaveArenaEvent event) {
        if (event.getArena() != null) {
            plugin.store().remove(event.getArena().getArenaName(), event.getPlayer().getUniqueId());
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        plugin.store().removeEverywhere(player.getUniqueId());

        PartyManager parties = plugin.parties();
        if (parties.inParty(player.getUniqueId())) {
            boolean owner = parties.isOwner(player.getUniqueId());
            List<UUID> members = parties.membersOf(player.getUniqueId());
            parties.onQuit(player.getUniqueId());
            for (UUID id : members) {
                if (id.equals(player.getUniqueId())) {
                    continue;
                }
                Player online = Bukkit.getPlayer(id);
                if (online != null) {
                    if (owner) {
                        plugin.messages().send(online, "party-disbanded-owner-left");
                    } else {
                        plugin.messages().send(online, "party-left-notify", "player", player.getName());
                    }
                }
            }
        } else {
            parties.onQuit(player.getUniqueId());
        }
    }

    @EventHandler
    public void onRestart(ArenaRestartEvent event) {
        plugin.store().clear(event.getArenaName());
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onAssign(TeamAssignEvent event) {
        plugin.assigner().applyFallback(event);
    }

    @EventHandler
    public void onInteract(PlayerInteractEvent event) {
        if (event.getHand() != EquipmentSlot.HAND) {
            return;
        }
        if (event.getAction() != Action.RIGHT_CLICK_AIR && event.getAction() != Action.RIGHT_CLICK_BLOCK) {
            return;
        }
        Player player = event.getPlayer();
        if (!ItemFactory.isSelector(plugin, event.getItem())) {
            return;
        }
        event.setCancelled(true);
        service.open(player);
    }

    @EventHandler
    public void onInventoryClick(InventoryClickEvent event) {
        Inventory top = event.getView().getTopInventory();
        if (top.getHolder() instanceof TeamGui gui) {
            event.setCancelled(true);
            if (event.getClickedInventory() != top || !(event.getWhoClicked() instanceof Player player)) {
                return;
            }
            int slot = event.getRawSlot();
            String teamName = gui.teamSlots().get(slot);
            if (teamName != null) {
                ITeam team = gui.arena().getTeam(teamName);
                if (team != null && service.select(player, gui.arena(), team)) {
                    gui.refresh();
                }
                return;
            }
            if (slot == gui.randomSlot() && service.random(player, gui.arena())) {
                gui.refresh();
            }
            return;
        }
        if (ItemFactory.isSelector(plugin, event.getCurrentItem()) || ItemFactory.isSelector(plugin, event.getCursor())) {
            event.setCancelled(true);
        }
    }

    @EventHandler
    public void onDrag(InventoryDragEvent event) {
        if (event.getView().getTopInventory().getHolder() instanceof TeamGui) {
            event.setCancelled(true);
            return;
        }
        for (int raw : event.getRawSlots()) {
            if (raw >= event.getView().getTopInventory().getSize()) {
                continue;
            }
            if (ItemFactory.isSelector(plugin, event.getView().getTopInventory().getItem(raw))) {
                event.setCancelled(true);
                return;
            }
        }
    }

    @EventHandler
    public void onSwapHands(PlayerSwapHandItemsEvent event) {
        if (ItemFactory.isSelector(plugin, event.getMainHandItem())
                || ItemFactory.isSelector(plugin, event.getOffHandItem())) {
            event.setCancelled(true);
        }
    }

    @EventHandler
    public void onDrop(PlayerDropItemEvent event) {
        if (ItemFactory.isSelector(plugin, event.getItemDrop().getItemStack())) {
            event.setCancelled(true);
        }
    }

}
