package com.bwteam.selector;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class SelectCommand implements CommandExecutor, TabCompleter {

    private final TeamSelectorPlugin plugin;
    private final SelectionService service;

    public SelectCommand(TeamSelectorPlugin plugin) {
        this.plugin = plugin;
        this.service = new SelectionService(plugin);
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length > 0 && args[0].equalsIgnoreCase("items")) {
            if (!(sender instanceof Player player)) {
                sender.sendMessage(plugin.messages().get("player-only"));
                return true;
            }
            if (!player.hasPermission("bwteam.admin")) {
                player.sendMessage(plugin.messages().get("prefix") + plugin.messages().get("no-permission"));
                return true;
            }
            java.util.List<Integer> slots = ItemFactory.selectorSlots(plugin, player);
            player.sendMessage(plugin.messages().format("items-report",
                    "count", String.valueOf(slots.size()),
                    "slots", slots.toString()));
            return true;
        }
        if (args.length > 0 && args[0].equalsIgnoreCase("reload")) {
            if (!sender.hasPermission("bwteam.admin")) {
                sender.sendMessage(plugin.messages().get("prefix") + plugin.messages().get("no-permission"));
                return true;
            }
            plugin.reloadConfig();
            plugin.messages().reload();
            sender.sendMessage(plugin.messages().get("prefix") + plugin.messages().get("reloaded"));
            return true;
        }
        if (!(sender instanceof Player player)) {
            sender.sendMessage(plugin.messages().get("player-only"));
            return true;
        }
        service.open(player);
        return true;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) {
            List<String> result = new ArrayList<>();
            for (String sub : List.of("reload", "items")) {
                if (sub.startsWith(args[0].toLowerCase())) {
                    result.add(sub);
                }
            }
            return result;
        }
        return Collections.emptyList();
    }
}
