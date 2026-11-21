package com.bwteam.selector;

import com.andrei1058.bedwars.api.arena.IArena;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory preferences: arena -> player -> team name.
 * Cleared when the game starts (assigner) or the arena restarts.
 */
public final class SelectionStore {

    private final Map<String, Map<UUID, String>> data = new ConcurrentHashMap<>();

    private Map<UUID, String> map(String arena) {
        return data.computeIfAbsent(arena, k -> new ConcurrentHashMap<>());
    }

    public String get(String arena, UUID uuid) {
        Map<UUID, String> map = data.get(arena);
        return map == null ? null : map.get(uuid);
    }

    public String get(IArena arena, UUID uuid) {
        return get(arena.getArenaName(), uuid);
    }

    public void set(String arena, UUID uuid, String team) {
        map(arena).put(uuid, team);
    }

    public void remove(String arena, UUID uuid) {
        Map<UUID, String> map = data.get(arena);
        if (map != null) {
            map.remove(uuid);
        }
    }

    /**
     * Count how many players in this arena picked the given team, ignoring one player.
     */
    public int count(String arena, String team, UUID ignore) {
        Map<UUID, String> map = data.get(arena);
        if (map == null) {
            return 0;
        }
        int count = 0;
        for (Map.Entry<UUID, String> entry : map.entrySet()) {
            if (ignore != null && ignore.equals(entry.getKey())) {
                continue;
            }
            if (team.equalsIgnoreCase(entry.getValue())) {
                count++;
            }
        }
        return count;
    }

    public void clear(String arena) {
        data.remove(arena);
    }

    public void removeEverywhere(UUID uuid) {
        for (Map<UUID, String> map : data.values()) {
            map.remove(uuid);
        }
    }

    public void clearAll() {
        data.clear();
    }
}
