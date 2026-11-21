package com.bwteam.selector;

import com.andrei1058.bedwars.api.arena.IArena;
import com.andrei1058.bedwars.api.arena.team.ITeam;
import com.andrei1058.bedwars.api.arena.team.ITeamAssigner;
import com.andrei1058.bedwars.api.events.gameplay.TeamAssignEvent;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Replaces BedWars1058's team assigner so the picked teams are respected at game start.
 * Requires experimental-team-assigner: true (BedWars1058 default).
 */
public final class PreferenceAssigner implements ITeamAssigner {

    private final TeamSelectorPlugin plugin;

    public PreferenceAssigner(TeamSelectorPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public void assignTeams(IArena arena) {
        plugin.setAssigning(true);
        try {
            int max = arena.getMaxInTeam();
            List<ITeam> teams = new ArrayList<>(arena.getTeams());
            List<List<Player>> groups = groups(arena);

            // parties first, bigger groups first
            groups.sort(Comparator.comparingInt((List<Player> list) -> list.size()).reversed());

            for (List<Player> group : groups) {
                ITeam target = pick(arena, teams, group.get(0), group.size(), max);
                if (target != null) {
                    for (Player player : group) {
                        if (arena.getTeam(player) == null) {
                            assign(arena, player, target);
                        }
                    }
                    continue;
                }
                // party too big for one team: split it, preferred team first
                for (Player player : group) {
                    if (arena.getTeam(player) != null) {
                        continue;
                    }
                    ITeam single = pick(arena, teams, player, 1, max);
                    if (single != null) {
                        assign(arena, player, single);
                    }
                }
            }
        } finally {
            plugin.store().clear(arena.getArenaName());
            plugin.setAssigning(false);
        }
    }

    private boolean assign(IArena arena, Player player, ITeam team) {
        TeamAssignEvent event = new TeamAssignEvent(player, team, arena);
        Bukkit.getPluginManager().callEvent(event);
        if (event.isCancelled()) {
            return false;
        }
        player.closeInventory();
        team.addPlayers(player);
        return true;
    }

    /**
     * Party owners are grouped first so their members are never treated as solo players.
     */
    private List<List<Player>> groups(IArena arena) {
        List<List<Player>> groups = new ArrayList<>();
        Set<UUID> handled = new HashSet<>();
        List<Player> all = new ArrayList<>(arena.getPlayers());
        all.removeIf(arena::isSpectator);

        for (Player player : all) {
            if (handled.contains(player.getUniqueId()) || !plugin.isAnyOwner(player)) {
                continue;
            }
            List<Player> group = new ArrayList<>();
            group.add(player);
            handled.add(player.getUniqueId());
            for (Player member : plugin.partyGroup(player, arena)) {
                if (handled.add(member.getUniqueId())) {
                    group.add(member);
                }
            }
            groups.add(group);
        }
        for (Player player : all) {
            if (handled.add(player.getUniqueId())) {
                List<Player> solo = new ArrayList<>();
                solo.add(player);
                groups.add(solo);
            }
        }
        return groups;
    }

    private ITeam pick(IArena arena, List<ITeam> teams, Player leader, int size, int max) {
        String preferredName = plugin.store().get(arena.getArenaName(), leader.getUniqueId());
        if (preferredName != null) {
            for (ITeam team : teams) {
                if (team.getName().equalsIgnoreCase(preferredName) && team.getSize() + size <= max) {
                    return team;
                }
            }
        }
        ITeam best = null;
        int bestFree = -1;
        for (ITeam team : teams) {
            int free = max - team.getSize();
            if (free >= size && free > bestFree) {
                best = team;
                bestFree = free;
            }
        }
        return best;
    }

    /**
     * Fallback for servers that disabled experimental-team-assigner:
     * cancel the random assignment and apply the preference ourselves.
     */
    public void applyFallback(TeamAssignEvent event) {
        if (plugin.isAssigning()) {
            return;
        }
        Player player = event.getPlayer();
        IArena arena = event.getArena();
        if (arena.getTeam(player) != null) {
            // already placed by us or by BedWars
            event.setCancelled(true);
            return;
        }
        String preferredName = plugin.store().get(arena.getArenaName(), player.getUniqueId());
        if (preferredName == null) {
            return;
        }
        ITeam target = arena.getTeam(preferredName);
        if (target == null) {
            return;
        }
        List<Player> group = new ArrayList<>();
        group.add(player);
        for (Player member : plugin.partyGroup(player, arena)) {
            if (!member.getUniqueId().equals(player.getUniqueId())) {
                group.add(member);
            }
        }
        if (target.getSize() + group.size() > arena.getMaxInTeam()) {
            return;
        }
        event.setCancelled(true);
        for (Player member : group) {
            if (arena.getTeam(member) == null) {
                member.closeInventory();
                target.addPlayers(member);
            }
        }
    }
}
