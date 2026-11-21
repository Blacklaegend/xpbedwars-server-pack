package com.bwteam.selector;

import com.andrei1058.bedwars.api.arena.GameState;
import com.andrei1058.bedwars.api.arena.IArena;
import com.andrei1058.bedwars.api.arena.team.ITeam;
import com.andrei1058.bedwars.api.tasks.StartingTask;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

public final class SelectionService {

    private final TeamSelectorPlugin plugin;

    public SelectionService(TeamSelectorPlugin plugin) {
        this.plugin = plugin;
    }

    /**
     * Open the selector GUI for a player that is waiting in an arena.
     */
    public void open(Player player) {
        Messages messages = plugin.messages();
        if (!player.hasPermission("bwteam.use")) {
            messages.send(player, "no-permission");
            return;
        }
        IArena arena = plugin.api().getArenaUtil().getArenaByPlayer(player);
        if (arena == null || arena.isSpectator(player)) {
            messages.send(player, "not-in-arena");
            return;
        }
        if (arena.getMaxInTeam() <= 1) {
            messages.send(player, "solo-mode");
            return;
        }
        new TeamGui(plugin, player, arena).open();
    }

    public static boolean isLocked(TeamSelectorPlugin plugin, IArena arena) {
        int lock = plugin.lockSeconds();
        if (lock <= 0) {
            return false;
        }
        StartingTask task = arena.getStartingTask();
        return task != null && task.getCountdown() <= lock;
    }

    public boolean select(Player player, IArena arena, ITeam team) {
        return select(player, arena, team, true);
    }

    public boolean select(Player player, IArena arena, ITeam team, boolean announce) {
        Messages messages = plugin.messages();

        if (!arena.isPlayer(player)) {
            messages.send(player, "not-in-arena");
            return false;
        }
        if (arena.getStatus() == GameState.playing || arena.getStatus() == GameState.restarting) {
            messages.send(player, "game-started");
            return false;
        }
        if (isLocked(plugin, arena)) {
            messages.send(player, "locked", "seconds", String.valueOf(plugin.lockSeconds()));
            return false;
        }

        boolean inParty = plugin.inAnyParty(player);
        boolean owner = plugin.isAnyOwner(player);
        if (inParty && !owner && plugin.getConfig().getBoolean("party-leader-only", true)) {
            messages.send(player, "party-only-leader");
            return false;
        }

        String current = plugin.store().get(arena.getArenaName(), player.getUniqueId());
        if (current != null && current.equalsIgnoreCase(team.getName())) {
            messages.send(player, "already-selected", "team", ItemFactory.coloredName(team, player));
            return false;
        }

        List<Player> group = new ArrayList<>();
        group.add(player);
        if (owner) {
            for (Player member : plugin.partyGroup(player, arena)) {
                if (!member.getUniqueId().equals(player.getUniqueId())) {
                    group.add(member);
                }
            }
        }

        if (plugin.getConfig().getBoolean("block-full-team", true)) {
            int max = arena.getMaxInTeam();
            int taken = plugin.store().count(arena.getArenaName(), team.getName(), null);
            for (Player member : group) {
                String picked = plugin.store().get(arena.getArenaName(), member.getUniqueId());
                if (picked != null && picked.equalsIgnoreCase(team.getName())) {
                    taken--;
                }
            }
            if (taken + group.size() > max) {
                messages.send(player, "team-full",
                        "team", ItemFactory.coloredName(team, player),
                        "current", String.valueOf(Math.max(0, taken)),
                        "max", String.valueOf(max));
                return false;
            }
        }

        for (Player member : group) {
            plugin.store().set(arena.getArenaName(), member.getUniqueId(), team.getName());
        }

        String display = ItemFactory.coloredName(team, player);
        if (announce) {
            if (group.size() > 1) {
                for (Player member : group) {
                    messages.send(member, "party-moved", "team", display);
                }
            } else {
                messages.send(player, "joined-team", "team", display);
            }
        }

        for (Player member : group) {
            if (member.isOnline() && arena.isPlayer(member)) {
                ItemFactory.giveOrUpdate(plugin, member, arena);
            }
        }
        return true;
    }

    public boolean random(Player player, IArena arena) {
        Messages messages = plugin.messages();
        if (!arena.isPlayer(player) || isLocked(plugin, arena)
                || arena.getStatus() == GameState.playing || arena.getStatus() == GameState.restarting) {
            messages.send(player, "no-team-available");
            return false;
        }

        int max = arena.getMaxInTeam();
        List<ITeam> candidates = new ArrayList<>();
        int best = Integer.MAX_VALUE;
        for (ITeam team : arena.getTeams()) {
            int taken = team.getSize() + plugin.store().count(arena.getArenaName(), team.getName(), null);
            if (taken >= max) {
                continue;
            }
            if (taken < best) {
                best = taken;
                candidates.clear();
                candidates.add(team);
            } else if (taken == best) {
                candidates.add(team);
            }
        }
        if (candidates.isEmpty()) {
            messages.send(player, "no-team-available");
            return false;
        }
        ITeam target = candidates.get(ThreadLocalRandom.current().nextInt(candidates.size()));
        if (select(player, arena, target, false)) {
            messages.send(player, "random-picked", "team", ItemFactory.coloredName(target, player));
            return true;
        }
        return false;
    }
}
