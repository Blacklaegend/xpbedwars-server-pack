package com.betag;

import net.luckperms.api.LuckPerms;
import net.luckperms.api.LuckPermsProvider;
import net.luckperms.api.model.user.User;
import net.luckperms.api.node.Node;
import net.luckperms.api.node.types.PrefixNode;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.geysermc.floodgate.api.FloodgateApi;

/**
 * Adds a coloured "[BE]" prefix for Floodgate (Bedrock) players through LuckPerms,
 * which BedWars1058 renders in chat and the tab list through {vPrefix}.
 *
 * Java players never match FloodgateApi#isFloodgatePlayer, so the tag cannot be obtained
 * by simply renaming a Java account (Java usernames cannot contain '[' or ']' either).
 */
public class BETag extends JavaPlugin implements Listener {

    private static final String PREFIX = "\u00a7b[BE]\u00a7r ";
    private static final int PRIORITY = 1000;
    private static final String KEY_PREFIX = "prefix." + PRIORITY + ".";

    private FloodgateApi floodgate;
    private LuckPerms luckPerms;

    @Override
    public void onEnable() {
        try {
            floodgate = FloodgateApi.getInstance();
            luckPerms = LuckPermsProvider.get();
        } catch (Throwable t) {
            getLogger().severe("Floodgate or LuckPerms API is not available: " + t);
            getServer().getPluginManager().disablePlugin(this);
            return;
        }
        Bukkit.getPluginManager().registerEvents(this, this);
        getLogger().info("BETag enabled (prefix " + PREFIX.replace("\u00a7", "&") + " for Floodgate players)");
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        // LuckPerms may still be loading the user data at join time
        Bukkit.getScheduler().runTaskLater(this, () -> apply(player), 20L);
    }

    private void apply(Player player) {
        if (!player.isOnline()) return;
        boolean bedrock;
        try {
            bedrock = floodgate.isFloodgatePlayer(player.getUniqueId());
        } catch (Throwable t) {
            getLogger().warning("Could not query Floodgate for " + player.getName() + ": " + t);
            return;
        }
        User user = luckPerms.getUserManager().getUser(player.getUniqueId());
        if (user == null) {
            getLogger().warning("LuckPerms user not loaded for " + player.getName());
            return;
        }

        boolean changed = false;
        for (Node node : user.data().toCollection()) {
            if (node.getKey().startsWith(KEY_PREFIX + "\u00a7b[BE]")) {
                user.data().remove(node);
                changed = true;
            }
        }
        if (bedrock) {
            user.data().add(PrefixNode.builder(PREFIX, PRIORITY).build());
            changed = true;
        }
        if (changed) {
            luckPerms.getUserManager().saveUser(user);
        }
    }
}
