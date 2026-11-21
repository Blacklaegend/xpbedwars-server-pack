package com.bwteam.selector;

import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

/**
 * /zd party command:
 * /zd            help
 * /zd i <player> invite
 * /zd q          leave
 * /zd l          list members and owner
 * /zd p <player> transfer ownership
 * /zd r <player> kick
 * /zd a <player> accept invite
 * /zd d          disband
 */
public final class PartyCommand implements CommandExecutor, TabCompleter {

    private static final List<String> SUBCOMMANDS = List.of("c", "i", "q", "l", "p", "r", "a", "d");

    private final TeamSelectorPlugin plugin;
    private final PartyManager parties;
    private final Messages messages;

    public PartyCommand(TeamSelectorPlugin plugin) {
        this.plugin = plugin;
        this.parties = plugin.parties();
        this.messages = plugin.messages();
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage(messages.get("player-only"));
            return true;
        }
        if (!player.hasPermission("bwteam.party")) {
            messages.send(player, "no-permission");
            return true;
        }
        if (args.length == 0) {
            help(player);
            return true;
        }
        switch (args[0].toLowerCase(Locale.ROOT)) {
            case "c" -> create(player);
            case "i" -> invite(player, args);
            case "a" -> accept(player, args);
            case "q" -> quit(player);
            case "l" -> list(player);
            case "p" -> promote(player, args);
            case "r" -> remove(player, args);
            case "d" -> disband(player);
            default -> help(player);
        }
        return true;
    }

    private void help(Player player) {
        for (String line : messages.list("party-help")) {
            player.sendMessage(line);
        }
    }

    private void create(Player player) {
        if (parties.inParty(player.getUniqueId())) {
            messages.send(player, "party-already-in-party");
            return;
        }
        parties.create(player.getUniqueId());
        messages.send(player, "party-created");
    }

    private void invite(Player player, String[] args) {
        Player target = target(player, args, 1);
        if (target == null) {
            return;
        }
        if (target.getUniqueId().equals(player.getUniqueId())) {
            messages.send(player, "party-invite-self");
            return;
        }
        if (parties.inParty(target.getUniqueId())) {
            messages.send(player, "party-target-in-party", "player", target.getName());
            return;
        }
        if (!parties.inParty(player.getUniqueId())) {
            parties.create(player.getUniqueId());
            messages.send(player, "party-created");
        } else if (!parties.isOwner(player.getUniqueId())) {
            messages.send(player, "party-only-owner");
            return;
        }
        int max = plugin.getConfig().getInt("party.max-size", 8);
        if (max > 0 && parties.size(player.getUniqueId()) >= max) {
            messages.send(player, "party-full", "max", String.valueOf(max));
            return;
        }
        parties.invite(player.getUniqueId(), target.getUniqueId());
        messages.send(player, "party-invite-sent", "player", target.getName());
        messages.send(target, "party-invite-received",
                "player", player.getName(),
                "command", "/zd a " + player.getName(),
                "seconds", String.valueOf(plugin.getConfig().getLong("party.invite-expire-seconds", 60L)));
    }

    private void accept(Player player, String[] args) {
        Player inviter = target(player, args, 1);
        if (inviter == null) {
            return;
        }
        if (parties.inParty(player.getUniqueId())) {
            messages.send(player, "party-already-in-party");
            return;
        }
        PartyManager.Invite invite = parties.pendingInvite(player.getUniqueId());
        if (invite == null || !invite.inviter.equals(inviter.getUniqueId())) {
            messages.send(player, "party-invite-none", "player", inviter.getName());
            return;
        }
        if (!parties.isOwner(inviter.getUniqueId())) {
            messages.send(player, "party-invite-invalid", "player", inviter.getName());
            parties.clearInvite(player.getUniqueId());
            return;
        }
        int max = plugin.getConfig().getInt("party.max-size", 8);
        if (max > 0 && parties.size(inviter.getUniqueId()) >= max) {
            messages.send(player, "party-full", "max", String.valueOf(max));
            return;
        }
        if (!parties.join(player.getUniqueId(), inviter.getUniqueId())) {
            messages.send(player, "party-invite-invalid", "player", inviter.getName());
            return;
        }
        parties.clearInvite(player.getUniqueId());
        messages.send(player, "party-joined", "owner", inviter.getName());
        broadcastParty(player.getUniqueId(), "party-join-notify", player.getName());
    }

    private void quit(Player player) {
        if (!parties.inParty(player.getUniqueId())) {
            messages.send(player, "party-not-in-party");
            return;
        }
        if (parties.isOwner(player.getUniqueId())) {
            if (plugin.getConfig().getBoolean("party.disband-on-owner-leave", true)) {
                for (UUID id : parties.disband(player.getUniqueId())) {
                    Player member = PartyManager.player(id);
                    if (member == null) {
                        continue;
                    }
                    messages.send(member, member.getUniqueId().equals(player.getUniqueId())
                            ? "party-disbanded"
                            : "party-disbanded-owner-left");
                }
                return;
            }
            messages.send(player, "party-owner-cannot-leave");
            return;
        }
        List<UUID> remaining = parties.membersOf(player.getUniqueId());
        parties.leave(player.getUniqueId());
        messages.send(player, "party-left");
        for (UUID id : remaining) {
            Player member = PartyManager.player(id);
            if (member != null && !member.getUniqueId().equals(player.getUniqueId())) {
                messages.send(member, "party-left-notify", "player", player.getName());
            }
        }
    }

    private void list(Player player) {
        if (!parties.inParty(player.getUniqueId())) {
            messages.send(player, "party-not-in-party");
            return;
        }
        List<UUID> members = parties.membersOf(player.getUniqueId());
        UUID owner = parties.ownerOf(player.getUniqueId());
        player.sendMessage(messages.format("party-list-header", "size", String.valueOf(members.size())));
        Player ownerPlayer = PartyManager.player(owner);
        player.sendMessage(messages.format("party-list-owner", "player", ownerPlayer == null ? "?" : ownerPlayer.getName()));
        for (UUID id : members) {
            if (id.equals(owner)) {
                continue;
            }
            Player member = PartyManager.player(id);
            if (member != null) {
                player.sendMessage(messages.format("party-list-member", "player", member.getName()));
            }
        }
        if (members.size() == 1) {
            player.sendMessage(messages.get("party-list-empty"));
        }
    }

    private void promote(Player player, String[] args) {
        if (!requireOwner(player)) {
            return;
        }
        Player target = target(player, args, 1);
        if (target == null) {
            return;
        }
        if (!parties.membersOf(player.getUniqueId()).contains(target.getUniqueId()) || target.equals(player)) {
            messages.send(player, "party-target-not-member", "player", target.getName());
            return;
        }
        if (parties.promote(player.getUniqueId(), target.getUniqueId())) {
            for (UUID id : parties.membersOf(target.getUniqueId())) {
                Player member = PartyManager.player(id);
                if (member != null) {
                    messages.send(member, "party-promoted-notify", "player", target.getName());
                }
            }
            messages.send(target, "party-promoted");
        }
    }

    private void remove(Player player, String[] args) {
        if (!requireOwner(player)) {
            return;
        }
        Player target = target(player, args, 1);
        if (target == null) {
            return;
        }
        if (!parties.membersOf(player.getUniqueId()).contains(target.getUniqueId()) || target.equals(player)) {
            messages.send(player, "party-target-not-member", "player", target.getName());
            return;
        }
        if (parties.remove(player.getUniqueId(), target.getUniqueId())) {
            messages.send(target, "party-removed");
            for (UUID id : parties.membersOf(player.getUniqueId())) {
                Player member = PartyManager.player(id);
                if (member != null) {
                    messages.send(member, "party-removed-notify", "player", target.getName());
                }
            }
        }
    }

    private void disband(Player player) {
        if (!requireOwner(player)) {
            return;
        }
        for (UUID id : parties.disband(player.getUniqueId())) {
            Player member = PartyManager.player(id);
            if (member != null) {
                messages.send(member, "party-disbanded");
            }
        }
    }

    private boolean requireOwner(Player player) {
        if (!parties.inParty(player.getUniqueId())) {
            messages.send(player, "party-not-in-party");
            return false;
        }
        if (!parties.isOwner(player.getUniqueId())) {
            messages.send(player, "party-only-owner");
            return false;
        }
        return true;
    }

    private Player target(Player player, String[] args, int index) {
        if (args.length <= index) {
            messages.send(player, "party-usage", "usage", "/zd " + args[0] + " <玩家>");
            return null;
        }
        Player target = Bukkit.getPlayerExact(args[index]);
        if (target == null) {
            target = Bukkit.getPlayer(args[index]);
        }
        if (target == null || !target.isOnline()) {
            messages.send(player, "party-target-offline", "player", args[index]);
            return null;
        }
        return target;
    }

    private void broadcastParty(UUID member, String path, String playerName) {
        for (UUID id : parties.membersOf(member)) {
            Player online = PartyManager.player(id);
            if (online != null) {
                messages.send(online, path, "player", playerName);
            }
        }
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) {
            List<String> result = new ArrayList<>();
            for (String sub : SUBCOMMANDS) {
                if (sub.startsWith(args[0].toLowerCase(Locale.ROOT))) {
                    result.add(sub);
                }
            }
            return result;
        }
        if (args.length == 2 && List.of("i", "a", "r", "p").contains(args[0].toLowerCase(Locale.ROOT))) {
            List<String> names = new ArrayList<>();
            for (Player online : Bukkit.getOnlinePlayers()) {
                if (online.getName().toLowerCase(Locale.ROOT).startsWith(args[1].toLowerCase(Locale.ROOT))) {
                    names.add(online.getName());
                }
            }
            return names;
        }
        return Collections.emptyList();
    }
}
